#################### START OF FILE: enemy_network_handler.py ####################

# enemy_network_handler.py
# -*- coding: utf-8 -*-
"""
Handles network data serialization and deserialization for the Enemy class (PySide6).
"""
# version 2.0.1 (PySide6 Refactor - Corrected player.state to enemy.state)

import os 
from typing import Dict, Any 

# PySide6 imports
from PySide6.QtCore import QPointF
from PySide6.QtGui import QPixmap, QColor 

# Game imports
import constants as C
from assets import load_all_player_animations 
from enemy import Enemy 

try:
    from logger import debug, error, warning
except ImportError:
    def debug(msg): print(f"DEBUG_ENET: {msg}")
    def error(msg): print(f"ERROR_ENET: {msg}")
    def warning(msg): print(f"WARNING_ENET: {msg}")

try:
    import pygame
    get_current_ticks = pygame.time.get_ticks
except ImportError:
    import time
    _start_time_enemy_net = time.monotonic()
    def get_current_ticks(): 
        return int((time.monotonic() - _start_time_enemy_net) * 1000)


def get_enemy_network_data(enemy) -> Dict[str, Any]:
    pos_x = enemy.pos.x() if hasattr(enemy.pos, 'x') else 0.0
    pos_y = enemy.pos.y() if hasattr(enemy.pos, 'y') else 0.0
    vel_x = enemy.vel.x() if hasattr(enemy.vel, 'x') else 0.0
    vel_y = enemy.vel.y() if hasattr(enemy.vel, 'y') else 0.0

    data = {
        'enemy_id': enemy.enemy_id, '_valid_init': enemy._valid_init, 
        'pos': (pos_x, pos_y), 'vel': (vel_x, vel_y), 
        'facing_right': enemy.facing_right, 'state': enemy.state, 
        'current_frame': enemy.current_frame, 'last_anim_update': enemy.last_anim_update, 
        'current_health': enemy.current_health, 'is_dead': enemy.is_dead,
        'death_animation_finished': enemy.death_animation_finished,
        'is_attacking': enemy.is_attacking, 'attack_type': enemy.attack_type, 
        'is_taking_hit': enemy.is_taking_hit, 'hit_timer': getattr(enemy, 'hit_timer', 0),
        'post_attack_pause_timer': enemy.post_attack_pause_timer, 
        'color_name': getattr(enemy, 'color_name', 'unknown'),
        'is_stomp_dying': getattr(enemy, 'is_stomp_dying', False), 
        'stomp_death_start_time': getattr(enemy, 'stomp_death_start_time', 0),
        'original_stomp_facing_right': getattr(enemy, 'original_stomp_facing_right', True),
        'is_frozen': getattr(enemy, 'is_frozen', False),
        'is_defrosting': getattr(enemy, 'is_defrosting', False),
        'frozen_effect_timer': getattr(enemy, 'frozen_effect_timer', 0),
        'is_aflame': getattr(enemy, 'is_aflame', False),
        'aflame_timer_start': getattr(enemy, 'aflame_timer_start', 0),
        'is_deflaming': getattr(enemy, 'is_deflaming', False),
        'deflame_timer_start': getattr(enemy, 'deflame_timer_start', 0),
        'has_ignited_another_enemy_this_cycle': getattr(enemy, 'has_ignited_another_enemy_this_cycle', False),
        'is_petrified': getattr(enemy, 'is_petrified', False),
        'is_stone_smashed': getattr(enemy, 'is_stone_smashed', False),
        'stone_smashed_timer_start': getattr(enemy, 'stone_smashed_timer_start', 0),
        'facing_at_petrification': getattr(enemy, 'facing_at_petrification', True),
    }
    return data

def set_enemy_network_data(enemy, network_data: Dict[str, Any]): 
    if network_data is None: return 
    from enemy_state_handler import set_enemy_state

    enemy._valid_init = network_data.get('_valid_init', enemy._valid_init)
    if not enemy._valid_init:
        if enemy.alive(): enemy.kill()  
        return 

    pos_data = network_data.get('pos')
    if pos_data and len(pos_data) == 2: enemy.pos.setX(pos_data[0]); enemy.pos.setY(pos_data[1])
    vel_data = network_data.get('vel')
    if vel_data and len(vel_data) == 2: enemy.vel.setX(vel_data[0]); enemy.vel.setY(vel_data[1])
    enemy.facing_right = network_data.get('facing_right', enemy.facing_right) 
    enemy.current_health = network_data.get('current_health', enemy.current_health)
    new_is_dead_net = network_data.get('is_dead', enemy.is_dead)
    enemy.death_animation_finished = network_data.get('death_animation_finished', enemy.death_animation_finished)
    new_is_petrified_net = network_data.get('is_petrified', enemy.is_petrified)
    new_is_smashed_net = network_data.get('is_stone_smashed', enemy.is_stone_smashed)
    enemy.facing_at_petrification = network_data.get('facing_at_petrification', enemy.facing_at_petrification)
    
    state_changed_by_priority = False
    if new_is_petrified_net:
        if not enemy.is_petrified: enemy.is_petrified = True; state_changed_by_priority = True
        enemy.is_aflame = False; enemy.is_deflaming = False; enemy.is_frozen = False; enemy.is_defrosting = False
        if new_is_smashed_net:
            if not enemy.is_stone_smashed: enemy.is_stone_smashed = True; state_changed_by_priority = True
            enemy.stone_smashed_timer_start = network_data.get('stone_smashed_timer_start', enemy.stone_smashed_timer_start)
            enemy.is_dead = True 
            enemy.death_animation_finished = network_data.get('death_animation_finished', enemy.death_animation_finished)
            if enemy.state != 'smashed': set_enemy_state(enemy, 'smashed')
        else: 
            if enemy.is_stone_smashed: enemy.is_stone_smashed = False; state_changed_by_priority = True
            enemy.is_dead = False 
            enemy.death_animation_finished = True 
            if enemy.state != 'petrified': set_enemy_state(enemy, 'petrified')
    elif enemy.is_petrified: 
        enemy.is_petrified = False; enemy.is_stone_smashed = False; state_changed_by_priority = True

    if not enemy.is_petrified:
        if new_is_dead_net != enemy.is_dead: 
            enemy.is_dead = new_is_dead_net
            state_changed_by_priority = True 
            if enemy.is_dead:
                enemy.current_health = 0 
                if enemy.state not in ['death', 'death_nm']: set_enemy_state(enemy, 'death')
            else: 
                if enemy.state in ['death', 'death_nm']: set_enemy_state(enemy, 'idle')
                enemy.death_animation_finished = False 
        else: enemy.is_dead = new_is_dead_net

    can_sync_other_statuses = not enemy.is_petrified and not (enemy.is_dead and enemy.death_animation_finished)
    if can_sync_other_statuses:
        new_is_aflame = network_data.get('is_aflame', enemy.is_aflame)
        if new_is_aflame and not enemy.is_aflame: enemy.aflame_timer_start = network_data.get('aflame_timer_start', get_current_ticks())
        enemy.is_aflame = new_is_aflame
        new_is_deflaming = network_data.get('is_deflaming', enemy.is_deflaming)
        if new_is_deflaming and not enemy.is_deflaming: enemy.deflame_timer_start = network_data.get('deflame_timer_start', get_current_ticks())
        enemy.is_deflaming = new_is_deflaming
        new_is_frozen = network_data.get('is_frozen', enemy.is_frozen)
        if new_is_frozen and not enemy.is_frozen: enemy.frozen_effect_timer = network_data.get('frozen_effect_timer', get_current_ticks())
        enemy.is_frozen = new_is_frozen
        new_is_defrosting = network_data.get('is_defrosting', enemy.is_defrosting)
        if new_is_defrosting and not enemy.is_defrosting: enemy.frozen_effect_timer = network_data.get('frozen_effect_timer', get_current_ticks())
        enemy.is_defrosting = new_is_defrosting
        new_is_stomp_dying_net = network_data.get('is_stomp_dying', False)
        if new_is_stomp_dying_net and not enemy.is_stomp_dying:
            enemy.is_stomp_dying = True
            enemy.stomp_death_start_time = network_data.get('stomp_death_start_time', get_current_ticks())
            enemy.original_stomp_facing_right = network_data.get('original_stomp_facing_right', enemy.facing_right)
            if hasattr(enemy, 'animate') and hasattr(enemy, 'image'): 
                original_facing_for_stomp_img = enemy.facing_right
                enemy.facing_right = enemy.original_stomp_facing_right
                _temp_stomp_flag = enemy.is_stomp_dying; enemy.is_stomp_dying = False
                enemy.animate()
                enemy.is_stomp_dying = _temp_stomp_flag
                enemy.original_stomp_death_image = enemy.image.copy() if enemy.image and not enemy.image.isNull() else None
                enemy.facing_right = original_facing_for_stomp_img
            if enemy.state != 'stomp_death': set_enemy_state(enemy, 'stomp_death') 
        elif not new_is_stomp_dying_net and enemy.is_stomp_dying:
            enemy.is_stomp_dying = False
            enemy.original_stomp_death_image = None

    can_sync_actions = can_sync_other_statuses and not \
                       (enemy.is_aflame or enemy.is_deflaming or enemy.is_frozen or enemy.is_defrosting or enemy.is_stomp_dying)
    if can_sync_actions:
        enemy.is_attacking = network_data.get('is_attacking', enemy.is_attacking)
        enemy.attack_type = network_data.get('attack_type', enemy.attack_type)
        new_is_taking_hit = network_data.get('is_taking_hit', enemy.is_taking_hit)
        new_hit_timer = network_data.get('hit_timer', enemy.hit_timer)
        if new_is_taking_hit != enemy.is_taking_hit or (new_is_taking_hit and enemy.hit_timer != new_hit_timer):
            enemy.is_taking_hit = new_is_taking_hit
            enemy.hit_timer = new_hit_timer
            # Corrected: Use enemy.state
            if enemy.is_taking_hit and enemy.state != 'hit' and not enemy.is_dead: set_enemy_state(enemy, 'hit')
            elif not enemy.is_taking_hit and enemy.state == 'hit' and not enemy.is_dead: set_enemy_state(enemy, 'idle')
        enemy.post_attack_pause_timer = network_data.get('post_attack_pause_timer', enemy.post_attack_pause_timer)

    if not state_changed_by_priority:
        new_logical_state_from_net = network_data.get('state', enemy.state)
        is_current_state_priority = enemy.state in ['aflame','deflame','frozen','defrost','petrified','smashed','death','death_nm','stomp_death']
        if not is_current_state_priority and enemy.state != new_logical_state_from_net:
            set_enemy_state(enemy, new_logical_state_from_net)
        else: 
            enemy.current_frame = network_data.get('current_frame', enemy.current_frame)
            enemy.last_anim_update = network_data.get('last_anim_update', enemy.last_anim_update)
    
    if hasattr(enemy, '_update_rect_from_image_and_pos'): enemy._update_rect_from_image_and_pos()
    elif hasattr(enemy, 'rect') and hasattr(enemy, 'pos'): 
        enemy.rect.moveCenter(enemy.pos); enemy.rect.moveBottom(enemy.pos.y())

    new_color_name_from_net = network_data.get('color_name', enemy.color_name)
    if hasattr(enemy, 'color_name') and enemy.color_name != new_color_name_from_net:
        warning(f"Client Enemy {enemy.enemy_id}: Color changed by server from '{enemy.color_name}' to '{new_color_name_from_net}'. Reloading animations.")
        enemy.color_name = new_color_name_from_net
        new_asset_folder = os.path.join('characters', enemy.color_name)
        enemy.animations = load_all_player_animations(relative_asset_folder=new_asset_folder)
        if enemy.animations is None:
            error(f"Client CRITICAL: Failed to reload animations for enemy {enemy.enemy_id} with new color {enemy.color_name} from '{new_asset_folder}'")
            enemy._valid_init = False 
            if hasattr(C, 'BLUE') and hasattr(enemy, 'image') and hasattr(enemy, 'rect'): 
                qcolor_blue = QColor(*C.BLUE)
                enemy.image = QPixmap(30,40); enemy.image.fill(qcolor_blue)
                if hasattr(enemy, '_update_rect_from_image_and_pos'): enemy._update_rect_from_image_and_pos()

    if enemy._valid_init and enemy.alive():
        if hasattr(enemy, 'animate'): enemy.animate()

#################### END OF FILE: enemy_network_handler.py ####################