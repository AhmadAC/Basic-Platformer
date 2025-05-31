# enemy_network_handler.py
# -*- coding: utf-8 -*-
"""
Handles network data serialization and deserialization for the Enemy class (PySide6).
MODIFIED: Added zapped attributes (version 2.0.3)
MODIFIED: Added EnemyKnight specific attributes for network sync (version 2.0.4)
MODIFIED: Addressed circular import by using TYPE_CHECKING for EnemyKnight.
MODIFIED: Ensured float conversion for pos/vel in set_enemy_network_data.
"""
# version 2.0.6 (Float conversion for set_network_data, robust class_type check)

import os
import time # For monotonic timer
from typing import Dict, Any, TYPE_CHECKING, Optional # Added Optional

# PySide6 imports
from PySide6.QtCore import QPointF
from PySide6.QtGui import QPixmap, QColor

# Game imports
import main_game.constants as C
from assets import load_enemy_animations # For client-side re-creation of generic enemy if color changes

# --- Use TYPE_CHECKING to avoid circular import with enemy_knight.py ---
if TYPE_CHECKING:
    from enemy import Enemy # For type hints if Enemy methods were directly called
    from enemy_knight import EnemyKnight # For isinstance checks or specific attribute access
# --- END MODIFICATION ---

try:
    from logger import debug, error, warning
except ImportError:
    def debug(msg, *args, **kwargs): print(f"DEBUG_ENET: {msg}")
    def error(msg, *args, **kwargs): print(f"ERROR_ENET: {msg}")
    def warning(msg, *args, **kwargs): print(f"WARNING_ENET: {msg}")

_start_time_enemy_net_monotonic = time.monotonic()
def get_current_ticks_monotonic() -> int:
    return int((time.monotonic() - _start_time_enemy_net_monotonic) * 1000)

def get_enemy_network_data(enemy: Any) -> Dict[str, Any]:
    pos_x = getattr(getattr(enemy, 'pos', None), 'x', lambda: 0.0)()
    pos_y = getattr(getattr(enemy, 'pos', None), 'y', lambda: 0.0)()
    vel_x = getattr(getattr(enemy, 'vel', None), 'x', lambda: 0.0)()
    vel_y = getattr(getattr(enemy, 'vel', None), 'y', lambda: 0.0)()

    data = {
        'enemy_id': getattr(enemy, 'enemy_id', None),
        '_valid_init': getattr(enemy, '_valid_init', False),
        'pos': (pos_x, pos_y),
        'vel': (vel_x, vel_y),
        'facing_right': getattr(enemy, 'facing_right', True),
        'state': getattr(enemy, 'state', 'idle'),
        'ai_state': getattr(enemy, 'ai_state', 'patrolling'), # Sync AI state for better client prediction
        'current_frame': getattr(enemy, 'current_frame', 0),
        'last_anim_update': getattr(enemy, 'last_anim_update', 0),
        'current_health': getattr(enemy, 'current_health', 0),
        'max_health': getattr(enemy, 'max_health', 0), # Send max_health for UI
        'is_dead': getattr(enemy, 'is_dead', True),
        'death_animation_finished': getattr(enemy, 'death_animation_finished', True),
        'is_attacking': getattr(enemy, 'is_attacking', False),
        'attack_type': getattr(enemy, 'attack_type', "none"), # Knight uses string, generic uses int (0)
        'attack_timer': getattr(enemy, 'attack_timer', 0),
        'attack_cooldown_timer': getattr(enemy, 'attack_cooldown_timer', 0),
        'is_taking_hit': getattr(enemy, 'is_taking_hit', False),
        'hit_timer': getattr(enemy, 'hit_timer', 0),
        'post_attack_pause_timer': getattr(enemy, 'post_attack_pause_timer', 0),
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
        'overall_fire_effect_start_time': getattr(enemy, 'overall_fire_effect_start_time', 0),
        'has_ignited_another_enemy_this_cycle': getattr(enemy, 'has_ignited_another_enemy_this_cycle', False),
        'is_petrified': getattr(enemy, 'is_petrified', False),
        'is_stone_smashed': getattr(enemy, 'is_stone_smashed', False),
        'stone_smashed_timer_start': getattr(enemy, 'stone_smashed_timer_start', 0),
        'facing_at_petrification': getattr(enemy, 'facing_at_petrification', True),
        'is_zapped': getattr(enemy, 'is_zapped', False),
        'zapped_timer_start': getattr(enemy, 'zapped_timer_start', 0),
        'zapped_damage_last_tick': getattr(enemy, 'zapped_damage_last_tick', 0),
        'class_type': enemy.__class__.__name__,
        'on_ground': getattr(enemy, 'on_ground', False), # Important for physics prediction
        'patrol_target_x': getattr(enemy, 'patrol_target_x', pos_x), # For client-side visual sync of patrol
        'properties': getattr(enemy, 'properties', {}).copy() # Send properties for client-side creation if needed
    }

    if enemy.__class__.__name__ == 'EnemyKnight':
        # Knight-specific attributes
        data['patrol_jump_chance'] = getattr(enemy, 'patrol_jump_chance', 0.015)
        data['patrol_jump_cooldown_ms'] = getattr(enemy, 'patrol_jump_cooldown_ms', 2500)
        data['last_patrol_jump_time'] = getattr(enemy, 'last_patrol_jump_time', 0)
        data['_is_mid_patrol_jump'] = getattr(enemy, '_is_mid_patrol_jump', False)
        # Attack damages and durations for knight are often derived from properties or constants,
        # if they are part of 'properties' dict, they are already sent.
        # If not, and client needs them (e.g., for predictive hit effects or detailed UI), send them:
        # data['knight_attack_damage_map'] = getattr(enemy, 'attack_damage_map', {})
        # data['knight_attack_duration_map'] = getattr(enemy, 'attack_duration_map', {})

    return data

def set_enemy_network_data(enemy: Any, network_data: Dict[str, Any]):
    if network_data is None: return
    # Ensure enemy_state_handler is available. If not, log error and proceed cautiously.
    try:
        from enemy_state_handler import set_enemy_state
    except ImportError:
        error("CRITICAL ENEMY_NETWORK_HANDLER: Failed to import set_enemy_state. Enemy state transitions will be incorrect on client.")
        def set_enemy_state(e, ns, t=None): # Dummy fallback
            if hasattr(e, 'state'): e.state = ns

    enemy._valid_init = network_data.get('_valid_init', getattr(enemy, '_valid_init', False))
    if not enemy._valid_init:
        if hasattr(enemy, 'alive') and enemy.alive() and hasattr(enemy, 'kill'): enemy.kill()
        return

    pos_data = network_data.get('pos')
    if hasattr(enemy, 'pos') and pos_data and len(pos_data) == 2:
        if hasattr(enemy.pos, 'setX'): enemy.pos.setX(float(pos_data[0]))
        if hasattr(enemy.pos, 'setY'): enemy.pos.setY(float(pos_data[1]))

    vel_data = network_data.get('vel')
    if hasattr(enemy, 'vel') and vel_data and len(vel_data) == 2:
        if hasattr(enemy.vel, 'setX'): enemy.vel.setX(float(vel_data[0]))
        if hasattr(enemy.vel, 'setY'): enemy.vel.setY(float(vel_data[1]))
    
    enemy.facing_right = network_data.get('facing_right', getattr(enemy, 'facing_right', True))
    enemy.ai_state = network_data.get('ai_state', getattr(enemy, 'ai_state', 'patrolling'))
    enemy.current_health = network_data.get('current_health', getattr(enemy, 'current_health', 0))
    enemy.max_health = network_data.get('max_health', getattr(enemy, 'max_health', 0)) # Sync max_health
    new_is_dead_net = network_data.get('is_dead', getattr(enemy, 'is_dead', True))
    enemy.death_animation_finished = network_data.get('death_animation_finished', getattr(enemy, 'death_animation_finished', True))
    new_is_petrified_net = network_data.get('is_petrified', getattr(enemy, 'is_petrified', False))
    new_is_smashed_net = network_data.get('is_stone_smashed', getattr(enemy, 'is_stone_smashed', False))
    enemy.facing_at_petrification = network_data.get('facing_at_petrification', getattr(enemy, 'facing_at_petrification', True))
    enemy.on_ground = network_data.get('on_ground', getattr(enemy, 'on_ground', False))
    enemy.patrol_target_x = network_data.get('patrol_target_x', getattr(enemy, 'patrol_target_x', enemy.pos.x() if hasattr(enemy, 'pos') else 0.0))
    
    # Properties might be needed if the enemy was just created on the client
    # and needs its configuration (like attack damages if not hardcoded).
    # For existing enemies, server is authoritative on behavior, not necessarily properties.
    # However, if properties change mid-game (e.g. enemy picks up a power-up), they'd need to sync.
    # For now, assume properties are mostly static after creation from map data.
    # If properties from network_data are present and enemy has a properties dict, update it.
    if 'properties' in network_data and hasattr(enemy, 'properties') and isinstance(enemy.properties, dict):
        enemy.properties.update(network_data['properties'])


    state_changed_by_priority = False
    # Petrified state has highest visual priority
    if new_is_petrified_net:
        if not getattr(enemy, 'is_petrified', False): enemy.is_petrified = True; state_changed_by_priority = True
        enemy.is_aflame = False; enemy.is_deflaming = False; enemy.is_frozen = False; enemy.is_defrosting = False; enemy.is_zapped = False
        if new_is_smashed_net:
            if not getattr(enemy, 'is_stone_smashed', False): enemy.is_stone_smashed = True; state_changed_by_priority = True
            enemy.stone_smashed_timer_start = network_data.get('stone_smashed_timer_start', getattr(enemy, 'stone_smashed_timer_start', 0))
            enemy.is_dead = True
            enemy.death_animation_finished = network_data.get('death_animation_finished', getattr(enemy, 'death_animation_finished', False))
            if getattr(enemy, 'state', 'idle') != 'smashed': set_enemy_state(enemy, 'smashed', get_current_ticks_monotonic())
        else: # Petrified but not smashed
            if getattr(enemy, 'is_stone_smashed', False): enemy.is_stone_smashed = False; state_changed_by_priority = True
            enemy.is_dead = True; enemy.death_animation_finished = True # Petrified means cannot animate further "death"
            if getattr(enemy, 'state', 'idle') != 'petrified': set_enemy_state(enemy, 'petrified', get_current_ticks_monotonic())
    elif getattr(enemy, 'is_petrified', False): # Was petrified, now server says it's not
        enemy.is_petrified = False; enemy.is_stone_smashed = False; state_changed_by_priority = True

    # is_dead state (only if not petrified)
    if not getattr(enemy, 'is_petrified', False):
        if new_is_dead_net != getattr(enemy, 'is_dead', True):
            enemy.is_dead = new_is_dead_net
            state_changed_by_priority = True # Mark that state was changed by a priority status
            if enemy.is_dead:
                enemy.current_health = 0
                if getattr(enemy, 'state', 'idle') not in ['death', 'death_nm']: # Check for death_nm too
                    set_enemy_state(enemy, 'death', get_current_ticks_monotonic()) # Server dictates death
            else: # Revived by server (unlikely for enemies, but for completeness)
                if getattr(enemy, 'state', 'idle') in ['death', 'death_nm']:
                    set_enemy_state(enemy, 'idle', get_current_ticks_monotonic())
                enemy.death_animation_finished = False # Reset death animation
        else: # No change in is_dead, just sync it
            enemy.is_dead = new_is_dead_net

    # Sync other status effects if not petrified or fully dead-animated
    can_sync_other_statuses = not getattr(enemy, 'is_petrified', False) and \
                              not (getattr(enemy, 'is_dead', False) and getattr(enemy, 'death_animation_finished', False))

    if can_sync_other_statuses:
        current_ticks_val = get_current_ticks_monotonic() # Use consistent time for timer starts
        
        new_is_aflame = network_data.get('is_aflame', getattr(enemy, 'is_aflame', False))
        if new_is_aflame and not getattr(enemy, 'is_aflame', False): # Transitioning to aflame
            enemy.aflame_timer_start = network_data.get('aflame_timer_start', current_ticks_val) # Sync start time
            enemy.overall_fire_effect_start_time = network_data.get('overall_fire_effect_start_time', current_ticks_val)
        enemy.is_aflame = new_is_aflame

        new_is_deflaming = network_data.get('is_deflaming', getattr(enemy, 'is_deflaming', False))
        if new_is_deflaming and not getattr(enemy, 'is_deflaming', False):
            enemy.deflame_timer_start = network_data.get('deflame_timer_start', current_ticks_val)
            # overall_fire_effect_start_time should carry over from aflame
            enemy.overall_fire_effect_start_time = network_data.get('overall_fire_effect_start_time', getattr(enemy, 'overall_fire_effect_start_time', 0))
        enemy.is_deflaming = new_is_deflaming

        if not new_is_aflame and not new_is_deflaming and getattr(enemy, 'overall_fire_effect_start_time', 0) != 0:
            enemy.overall_fire_effect_start_time = 0 # Clear if fire cycle ended

        new_is_frozen = network_data.get('is_frozen', getattr(enemy, 'is_frozen', False))
        if new_is_frozen and not getattr(enemy, 'is_frozen', False):
            enemy.frozen_effect_timer = network_data.get('frozen_effect_timer', current_ticks_val)
        enemy.is_frozen = new_is_frozen

        new_is_defrosting = network_data.get('is_defrosting', getattr(enemy, 'is_defrosting', False))
        if new_is_defrosting and not getattr(enemy, 'is_defrosting', False): # Transitioning to defrosting
            enemy.frozen_effect_timer = network_data.get('frozen_effect_timer', getattr(enemy, 'frozen_effect_timer', current_ticks_val))
        enemy.is_defrosting = new_is_defrosting
        
        new_is_zapped = network_data.get('is_zapped', getattr(enemy, 'is_zapped', False))
        if new_is_zapped and not getattr(enemy, 'is_zapped', False):
            enemy.zapped_timer_start = network_data.get('zapped_timer_start', current_ticks_val)
            enemy.zapped_damage_last_tick = enemy.zapped_timer_start # Sync this too
        enemy.is_zapped = new_is_zapped
        enemy.has_ignited_another_enemy_this_cycle = network_data.get('has_ignited_another_enemy_this_cycle', getattr(enemy, 'has_ignited_another_enemy_this_cycle', False))
        
        new_is_stomp_dying_net = network_data.get('is_stomp_dying', False)
        if new_is_stomp_dying_net and not getattr(enemy, 'is_stomp_dying', False):
            enemy.is_stomp_dying = True
            enemy.stomp_death_start_time = network_data.get('stomp_death_start_time', current_ticks_val)
            enemy.original_stomp_facing_right = network_data.get('original_stomp_facing_right', getattr(enemy, 'facing_right', True))
            if getattr(enemy, 'state', 'idle') != 'stomp_death': set_enemy_state(enemy, 'stomp_death', get_current_ticks_monotonic())
        elif not new_is_stomp_dying_net and getattr(enemy, 'is_stomp_dying', False):
            enemy.is_stomp_dying = False
            enemy.original_stomp_death_image = None

    # Sync action states if no higher priority status is active
    can_sync_actions = can_sync_other_statuses and not \
                       (getattr(enemy, 'is_aflame', False) or getattr(enemy, 'is_deflaming', False) or \
                        getattr(enemy, 'is_frozen', False) or getattr(enemy, 'is_defrosting', False) or \
                        getattr(enemy, 'is_stomp_dying', False) or getattr(enemy, 'is_zapped', False))

    if can_sync_actions:
        enemy.is_attacking = network_data.get('is_attacking', getattr(enemy, 'is_attacking', False))
        enemy.attack_type = network_data.get('attack_type', getattr(enemy, 'attack_type', "none"))
        enemy.attack_timer = network_data.get('attack_timer', getattr(enemy, 'attack_timer', 0)) # Sync attack start time
        enemy.attack_cooldown_timer = network_data.get('attack_cooldown_timer', getattr(enemy, 'attack_cooldown_timer', 0))

        new_is_taking_hit = network_data.get('is_taking_hit', getattr(enemy, 'is_taking_hit', False))
        new_hit_timer = network_data.get('hit_timer', getattr(enemy, 'hit_timer', 0))
        if new_is_taking_hit != getattr(enemy, 'is_taking_hit', False) or \
           (new_is_taking_hit and getattr(enemy, 'hit_timer', 0) != new_hit_timer):
            enemy.is_taking_hit = new_is_taking_hit
            enemy.hit_timer = new_hit_timer
            current_enemy_state = getattr(enemy, 'state', 'idle')
            is_enemy_actually_dead = getattr(enemy, 'is_dead', False)
            if enemy.is_taking_hit and current_enemy_state != 'hit' and not is_enemy_actually_dead:
                set_enemy_state(enemy, 'hit', get_current_ticks_monotonic())
            elif not enemy.is_taking_hit and current_enemy_state == 'hit' and not is_enemy_actually_dead:
                set_enemy_state(enemy, 'idle', get_current_ticks_monotonic())

        enemy.post_attack_pause_timer = network_data.get('post_attack_pause_timer', getattr(enemy, 'post_attack_pause_timer', 0))

    # Sync logical state (e.g., 'idle', 'run') only if no high-priority status has taken over.
    if not state_changed_by_priority:
        new_logical_state_from_net = network_data.get('state', getattr(enemy, 'state', 'idle'))
        current_enemy_state = getattr(enemy, 'state', 'idle')
        
        is_current_state_a_priority_status = current_enemy_state in [
            'aflame','deflame','frozen','defrost','petrified','smashed',
            'death','death_nm','stomp_death', 'hit', 'zapped', 'jump' # Added jump for knight
        ]
        
        if not is_current_state_a_priority_status and current_enemy_state != new_logical_state_from_net:
            set_enemy_state(enemy, new_logical_state_from_net, get_current_ticks_monotonic())
        else: # If state hasn't changed or is a priority one, still sync animation frame data
            enemy.current_frame = network_data.get('current_frame', getattr(enemy, 'current_frame', 0))
            enemy.last_anim_update = network_data.get('last_anim_update', getattr(enemy, 'last_anim_update', 0))

    # Knight-specific state synchronization
    if enemy.__class__.__name__ == 'EnemyKnight':
        enemy.patrol_jump_chance = network_data.get('patrol_jump_chance', getattr(enemy, 'patrol_jump_chance', 0.015))
        enemy.patrol_jump_cooldown_ms = network_data.get('patrol_jump_cooldown_ms', getattr(enemy, 'patrol_jump_cooldown_ms', 2500))
        enemy.last_patrol_jump_time = network_data.get('last_patrol_jump_time', getattr(enemy, 'last_patrol_jump_time', 0))
        enemy._is_mid_patrol_jump = network_data.get('_is_mid_patrol_jump', getattr(enemy, '_is_mid_patrol_jump', False))
        # Sync attack_type explicitly as it's a string for knight
        enemy.attack_type = network_data.get('attack_type', getattr(enemy, 'attack_type', "none"))


    # Update rect and animate
    if hasattr(enemy, '_update_rect_from_image_and_pos'):
        enemy._update_rect_from_image_and_pos()
    elif hasattr(enemy, 'rect') and hasattr(enemy, 'pos') and hasattr(enemy.rect, 'center') and hasattr(enemy.rect, 'bottom'):
        # Fallback if _update_rect_from_image_and_pos is missing (shouldn't happen if inheriting EnemyBase)
        enemy.rect.moveCenter(enemy.pos)
        enemy.rect.moveBottom(enemy.pos.y())

    # Generic enemy color change (Knight handles its own animations, so this is for generic Enemy type)
    new_color_name_from_net = network_data.get('color_name', getattr(enemy, 'color_name', 'unknown'))
    if hasattr(enemy, 'color_name') and enemy.color_name != new_color_name_from_net and enemy.__class__.__name__ != 'EnemyKnight':
        warning(f"Client Enemy {getattr(enemy, 'enemy_id', 'N/A')}: Color changed by server from '{enemy.color_name}' to '{new_color_name_from_net}'. Reloading animations.")
        enemy.color_name = new_color_name_from_net
        new_asset_folder = os.path.join('characters', enemy.color_name)
        # Ensure load_enemy_animations exists and is imported correctly in assets.py
        enemy.animations = load_enemy_animations(relative_asset_folder=new_asset_folder)
        if enemy.animations is None:
            error(f"Client CRITICAL: Failed to reload animations for enemy {getattr(enemy, 'enemy_id', 'N/A')} with new color {enemy.color_name} from '{new_asset_folder}'")
            enemy._valid_init = False
            if hasattr(C, 'BLUE') and hasattr(enemy, 'image') and hasattr(enemy, 'rect'):
                blue_color_tuple = getattr(C, 'BLUE', (0,0,255))
                qcolor_blue = QColor(*blue_color_tuple)
                enemy.image = QPixmap(30,40); enemy.image.fill(qcolor_blue)
                if hasattr(enemy, '_update_rect_from_image_and_pos'): enemy._update_rect_from_image_and_pos()

    if getattr(enemy, '_valid_init', False) and hasattr(enemy, 'alive') and enemy.alive():
        if hasattr(enemy, 'animate'):
            enemy.animate()