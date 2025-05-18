#################### START OF MODIFIED FILE: player_combat_handler.py ####################

# player_combat_handler.py
# -*- coding: utf-8 -*-
"""
version 1.0.0.3 (Allow movement during hit stun if on fire)
Handles player combat: attacks, damage dealing/taking, healing, and projectile firing.
Functions here will typically take a 'player' instance as their first argument.
"""
import pygame
import constants as C
from projectiles import Fireball # Needed for instantiating Fireball

def fire_player_fireball(player):
    # ... (existing code, no changes needed here for this specific issue) ...
    print(f"DEBUG PCH (P{player.player_id}): Attempting fire_player_fireball. Valid: {player._valid_init}, Dead: {player.is_dead}, Alive: {player.alive() if hasattr(player, 'alive') else 'N/A'}, ProjGrp: {player.projectile_sprites_group is not None}, AllGrp: {player.all_sprites_group is not None}")
    if not player._valid_init or player.is_dead or not player.alive():
        print(f"DEBUG PCH (P{player.player_id}): Fireball RETURN early - player not valid/alive.")
        return
    if player.projectile_sprites_group is None or player.all_sprites_group is None:
        print(f"DEBUG PCH (P{player.player_id}): Fireball RETURN early - sprite groups not set.")
        if player.print_limiter.can_print(f"player_{player.player_id}_fireball_no_group_ref_handler"):
            print(f"Player {player.player_id} (CombatHandler): Cannot fire fireball, projectile/all_sprites group not set.")
        return
    current_time_ms = pygame.time.get_ticks()
    print(f"DEBUG PCH (P{player.player_id}): Fireball Cooldown Check. Current: {current_time_ms}, LastFire: {player.fireball_cooldown_timer}, CooldownVal: {C.FIREBALL_COOLDOWN}, Diff: {current_time_ms - player.fireball_cooldown_timer}")
    if current_time_ms - player.fireball_cooldown_timer >= C.FIREBALL_COOLDOWN:
        player.fireball_cooldown_timer = current_time_ms
        spawn_x = player.rect.centerx
        spawn_y = player.rect.centery
        current_aim_direction = player.fireball_last_input_dir.copy()
        if current_aim_direction.length_squared() == 0:
            current_aim_direction.x = 1.0 if player.facing_right else -1.0
            current_aim_direction.y = 0.0
        proj_dims = getattr(C, "FIREBALL_DIMENSIONS", (10,10))
        offset_distance = (player.rect.width / 2) + (proj_dims[0] / 2) - 35
        if abs(current_aim_direction.y) > 0.8 * abs(current_aim_direction.x):
            offset_distance = (player.rect.height / 2) + (proj_dims[1] / 2) - 35
        if current_aim_direction.length_squared() > 0:
            offset_vector = current_aim_direction.normalize() * offset_distance
            spawn_x += offset_vector.x
            spawn_y += offset_vector.y
        new_fireball = Fireball(spawn_x, spawn_y, current_aim_direction, player)
        player.projectile_sprites_group.add(new_fireball)
        player.all_sprites_group.add(new_fireball)
        print(f"DEBUG PCH (P{player.player_id}): Fireball CREATED AND ADDED to groups. Groups now: Proj Count={len(player.projectile_sprites_group.sprites())}, All Count={len(player.all_sprites_group.sprites())}")
        if player.print_limiter.can_print(f"player_{player.player_id}_fire_fireball_msg_combat_handler"):
            print(f"Player {player.player_id} (CombatHandler) fires fireball. Aim Dir: {current_aim_direction}, Spawn Pos: ({spawn_x:.1f}, {spawn_y:.1f})")
    else:
        print(f"DEBUG PCH (P{player.player_id}): Fireball ON COOLDOWN.")
        if player.print_limiter.can_print(f"player_{player.player_id}_fireball_cooldown_combat_handler"):
            print(f"Player {player.player_id} (CombatHandler): Fireball on cooldown.")


def check_player_attack_collisions(player, targets_list):
    # ... (existing code, no changes needed here for this specific issue) ...
    if not player._valid_init or not player.is_attacking or player.is_dead or not player.alive():
        return
    if player.facing_right: player.attack_hitbox.midleft = player.rect.midright
    else: player.attack_hitbox.midright = player.rect.midleft
    vertical_offset_for_crouch_attack = -10 if player.is_crouching and player.attack_type == 4 else 0
    player.attack_hitbox.centery = player.rect.centery + vertical_offset_for_crouch_attack
    current_time_ms = pygame.time.get_ticks()
    for target_sprite in targets_list:
        if target_sprite is player: continue
        if not (target_sprite and hasattr(target_sprite, '_valid_init') and target_sprite._valid_init and \
                hasattr(target_sprite, 'is_dead') and not target_sprite.is_dead and target_sprite.alive()):
            continue
        target_is_currently_invincible = False
        if hasattr(target_sprite, 'is_taking_hit') and hasattr(target_sprite, 'hit_timer') and \
           hasattr(target_sprite, 'hit_cooldown'):
            if target_sprite.is_taking_hit and \
               (current_time_ms - target_sprite.hit_timer < target_sprite.hit_cooldown):
                target_is_currently_invincible = True
        if target_is_currently_invincible:
            continue
        if player.attack_hitbox.colliderect(target_sprite.rect):
            if hasattr(target_sprite, 'take_damage') and callable(target_sprite.take_damage):
                damage_to_inflict = 0
                if player.attack_type == 1: damage_to_inflict = C.PLAYER_ATTACK1_DAMAGE
                elif player.attack_type == 2: damage_to_inflict = C.PLAYER_ATTACK2_DAMAGE
                elif player.attack_type == 3: damage_to_inflict = C.PLAYER_COMBO_ATTACK_DAMAGE
                elif player.attack_type == 4: damage_to_inflict = C.PLAYER_CROUCH_ATTACK_DAMAGE
                if damage_to_inflict > 0:
                    target_sprite.take_damage(damage_to_inflict)


def player_take_damage(player, damage_amount):
    """
    Handles the player instance taking a specified amount of damage.
    Updates health, and potentially triggers 'hit' or 'death' states.
    If player is on fire, 'hit' state is not set, but damage and cooldown apply.

    Args:
        player (Player): The player instance receiving damage.
        damage_amount (int): The amount of damage to inflict.
    """
    current_time_ms = pygame.time.get_ticks()
    
    if not player._valid_init or player.is_dead or not player.alive() or \
       (player.is_taking_hit and current_time_ms - player.hit_timer < player.hit_cooldown): 
        return

    player.current_health -= damage_amount
    player.current_health = max(0, player.current_health) 

    player.is_taking_hit = True # Always grant invulnerability window
    player.hit_timer = current_time_ms

    if player.current_health <= 0: 
        if not player.is_dead: 
            player.set_state('death') 
    else:
        # MODIFIED: Only set to 'hit' state if NOT currently in a fire visual state
        is_in_fire_visual_state = player.state in ['aflame', 'burning', 'aflame_crouch', 'burning_crouch', 'deflame', 'deflame_crouch']
        
        if not is_in_fire_visual_state:
            # Only change to 'hit' if not already in 'hit' and cooldown has passed (or it's a new hit)
            # The 'current_time_ms - player.state_timer < player.hit_duration' check is tricky here
            # because state_timer is for the current state, not necessarily the last 'hit' state.
            # The main invulnerability is handled by is_taking_hit and hit_timer.
            # If we are setting to 'hit', it means a new hit occurred.
            if player.state != 'hit': # If not already in hit, set to hit
                 player.set_state('hit')
            # If already in 'hit' state, this function was called again within hit_duration,
            # but the outer guard (is_taking_hit & hit_timer < hit_cooldown) should prevent re-entry
            # unless hit_cooldown is shorter than hit_duration, which would be unusual.
        else:
            if player.print_limiter.can_print(f"player_hit_while_on_fire_{player.player_id}"):
                print(f"Player {player.player_id}: Took damage while on fire. State remains '{player.state}'. is_taking_hit=True.")
            # Player remains visually on fire but gets hit invulnerability.

def player_self_inflict_damage(player, damage_amount):
    # ... (existing code) ...
    if not player._valid_init or player.is_dead or not player.alive(): return
    player_take_damage(player, damage_amount)

def player_heal_to_full(player):
    # ... (existing code) ...
    if not player._valid_init: return
    if player.is_dead and player.current_health <=0 : return
    player.current_health = player.max_health
    if player.is_taking_hit: player.is_taking_hit = False
    if player.state == 'hit': player.set_state('idle')


#################### END OF MODIFIED FILE: player_combat_handler.py ####################