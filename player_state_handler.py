#################### START OF MODIFIED FILE: player_state_handler.py ####################

# player_state_handler.py
# -*- coding: utf-8 -*-
"""
## version 1.0.0.9 (Correctly allow initial 'aflame'/'aflame_crouch' states)
Handles player state transitions and state-specific initializations.
"""
import pygame
import constants as C
from utils import PrintLimiter

def set_player_state(player, new_state: str):
    if not player._valid_init: return

    original_new_state_request = new_state
    player_id_str = f"P{player.player_id}"

    # --- State Overrides based on flags (Highest Priority) ---
    if player.is_petrified and new_state not in ['petrified', 'smashed', 'death', 'death_nm']:
        # ... (blocked logic) ...
        return
    if player.is_stone_smashed and new_state not in ['smashed', 'death', 'death_nm']:
        # ... (blocked logic) ...
        return

    # --- Modify requested state based on overriding conditions ---
    # This logic needs to be careful not to prevent the initial 'aflame' or 'aflame_crouch' states.
    # The player.is_aflame flag will be true when these states are requested by apply_aflame_effect.
    if player.is_aflame:
        # If the new_state is an attempt to switch *out* of a fire-related state
        # (and it's not death/stone/hit), then force it back to an appropriate fire state.
        if new_state not in ['aflame', 'burning', 'aflame_crouch', 'burning_crouch',
                             'deflame', 'deflame_crouch', # Allow transitions to deflame
                             'death', 'death_nm', 'petrified', 'smashed', 'hit']:
            if player.is_crouching:
                # If currently aflame and crouching, should be in a crouched fire state.
                # If transitioning to crouch, input handler should request 'burning_crouch' or 'aflame_crouch'.
                new_state = 'burning_crouch' # Default to looping crouch fire
            else:
                new_state = 'burning' # Default to looping standing fire
    elif player.is_deflaming:
        if new_state not in ['deflame', 'deflame_crouch', 'death', 'death_nm', 'petrified', 'smashed', 'hit']:
            new_state = 'deflame_crouch' if player.is_crouching else 'deflame'
    elif player.is_frozen:
        if new_state not in ['frozen', 'defrost', 'death', 'death_nm', 'petrified', 'smashed', 'hit']:
            new_state = 'frozen'
    elif player.is_defrosting:
        if new_state not in ['frozen', 'defrost', 'death', 'death_nm', 'petrified', 'smashed', 'hit']:
            new_state = 'defrost'
    # If none of the above status flags are active, 'new_state' remains original_new_state_request.

    # --- Animation Key Validation ---
    # ... (existing fallback logic for missing animations, no change here) ...
    animation_frames_for_new_state = player.animations.get(new_state)
    if not animation_frames_for_new_state and new_state not in ['petrified', 'smashed']:
        fallback_state_key = 'fall' if not player.on_ground else 'idle'
        if fallback_state_key in player.animations and player.animations[fallback_state_key]:
            if player.print_limiter.can_print(f"player_set_state_fallback_{player.player_id}_{original_new_state_request}_{new_state}"):
                print(f"Player Warning (P{player_id_str}): State '{original_new_state_request}' (became '{new_state}') anim missing. Fallback to '{fallback_state_key}'.")
            new_state = fallback_state_key
        else:
            first_available_anim_key = next((key for key, anim in player.animations.items() if anim), None)
            if not first_available_anim_key:
                if player.print_limiter.can_print(f"player_set_state_no_anims_{player.player_id}"):
                    print(f"CRITICAL Player Error (P{player_id_str}): No animations loaded. Requested: '{original_new_state_request}'. Player invalid.")
                player._valid_init = False; return
            new_state = first_available_anim_key
            if player.print_limiter.can_print(f"player_set_state_critical_fallback_{player.player_id}_{original_new_state_request}"):
                print(f"Player CRITICAL Warning (P{player_id_str}): State '{original_new_state_request}' and preferred fallbacks missing. Using first available: '{new_state}'.")


    can_change_state_now = (player.state != new_state) or \
                           (new_state == 'hit') or \
                           (new_state in ['aflame', 'aflame_crouch'] and player.state not in ['aflame', 'aflame_crouch']) # Allow setting initial fire anims

    if player.is_dead and player.death_animation_finished and new_state not in ['death', 'death_nm', 'petrified', 'smashed']:
        can_change_state_now = False

    if can_change_state_now:
        if player.print_limiter.can_print(f"state_change_{player.player_id}_{player.state}_{new_state}"):
             print(f"DEBUG P_STATE_H (P{player_id_str}): State changing from '{player.state}' to '{new_state}' (request was '{original_new_state_request}')")
        player._last_state_for_debug = new_state

        # --- Clear conflicting ACTION flags ---
        if 'attack' not in new_state and player.is_attacking: player.is_attacking = False; player.attack_type = 0
        if new_state != 'hit': player.is_taking_hit = False
        if new_state != 'dash': player.is_dashing = False
        if new_state != 'roll': player.is_rolling = False
        if new_state not in ['slide', 'slide_trans_start', 'slide_trans_end']: player.is_sliding = False

        # --- Manage STATUS flags based on the NEW state ---
        # is_aflame, is_deflaming, is_frozen, is_defrosting are primarily set by apply_effect or update_status_effects.
        # This section ensures consistency if set_state is called for these directly.
        if new_state == 'aflame' or new_state == 'burning' or new_state == 'aflame_crouch' or new_state == 'burning_crouch':
            if not player.is_aflame: # If just becoming aflame now via direct set_state
                player.aflame_timer_start = pygame.time.get_ticks()
                player.aflame_damage_last_tick = player.aflame_timer_start
            player.is_aflame = True
            player.is_deflaming = False
        # No 'else player.is_aflame = False' here; timer in player.py controls this.

        if new_state == 'deflame' or new_state == 'deflame_crouch':
            if not player.is_deflaming: # If just becoming deflaming now
                player.deflame_timer_start = pygame.time.get_ticks()
            player.is_deflaming = True
            player.is_aflame = False
        # No 'else player.is_deflaming = False' here; timer controls this.

        if new_state == 'frozen':
            if not player.is_frozen: player.frozen_effect_timer = pygame.time.get_ticks()
            player.is_frozen = True; player.is_defrosting = False
        elif new_state != 'defrost': player.is_frozen = False

        if new_state == 'defrost':
            player.is_defrosting = True; player.is_frozen = False
        elif new_state != 'frozen': player.is_defrosting = False
        
        if (player.is_petrified or player.is_stone_smashed) and new_state not in ['petrified', 'smashed']:
            player.is_petrified = False
            player.is_stone_smashed = False
            player.was_crouching_when_petrified = False
            if player.is_dead and player.current_health > 0:
                player.is_dead = False
                player.death_animation_finished = False

        player.state = new_state
        player.current_frame = 0
        player.last_anim_update = pygame.time.get_ticks()
        player.state_timer = player.last_anim_update

        # --- State-Specific Initializations ---
        # (dash, roll, slide, attack, hit, death, wall states, petrified, smashed, frozen, defrost as before)
        if new_state == 'dash':
            player.is_dashing = True; player.dash_timer = player.state_timer
            player.vel.x = C.PLAYER_DASH_SPEED * (1 if player.facing_right else -1)
            player.vel.y = 0
        elif new_state == 'roll':
            player.is_rolling = True; player.roll_timer = player.state_timer
            if abs(player.vel.x) < C.PLAYER_ROLL_SPEED * 0.7: player.vel.x = C.PLAYER_ROLL_SPEED * (1 if player.facing_right else -1)
            else: player.vel.x = player.vel.x * 0.8 + (C.PLAYER_ROLL_SPEED * 0.2 * (1 if player.facing_right else -1))
            player.vel.x = max(-C.PLAYER_ROLL_SPEED, min(C.PLAYER_ROLL_SPEED, player.vel.x))
        elif new_state == 'slide' or new_state == 'slide_trans_start':
            player.is_sliding = True; player.slide_timer = player.state_timer
            if abs(player.vel.x) < C.PLAYER_RUN_SPEED_LIMIT * 0.5: player.vel.x = C.PLAYER_RUN_SPEED_LIMIT * 0.6 * (1 if player.facing_right else -1)
        elif 'attack' in new_state:
            player.is_attacking = True; player.attack_timer = player.state_timer
            animation_for_this_attack = player.animations.get(new_state, [])
            num_attack_frames = len(animation_for_this_attack)
            base_ms_per_frame = C.ANIM_FRAME_DURATION
            if player.attack_type == 2 and hasattr(C, 'PLAYER_ATTACK2_FRAME_DURATION_MULTIPLIER'): ms_per_frame = int(base_ms_per_frame * C.PLAYER_ATTACK2_FRAME_DURATION_MULTIPLIER)
            else: ms_per_frame = base_ms_per_frame
            player.attack_duration = num_attack_frames * ms_per_frame if num_attack_frames > 0 else getattr(C, 'CHARACTER_ATTACK_STATE_DURATION', 300)
            if new_state.endswith('_nm') or new_state == 'crouch_attack': player.vel.x = 0
        elif new_state == 'hit':
            player.is_taking_hit = True; player.hit_timer = player.state_timer
            if not player.on_ground and player.vel.y > -abs(C.PLAYER_JUMP_STRENGTH * 0.5):
                player.vel.x *= -0.3
                player.vel.y = C.PLAYER_JUMP_STRENGTH * 0.4
            player.is_attacking = False; player.attack_type = 0
        elif new_state == 'death' or new_state == 'death_nm':
            player.is_dead = True; player.vel.x = 0
            if player.vel.y < -1: player.vel.y = 1
            player.acc.x = 0
            if not player.on_ground: player.acc.y = C.PLAYER_GRAVITY
            else: player.vel.y = 0; player.acc.y = 0
            player.death_animation_finished = False
        elif new_state == 'wall_climb':
            player.wall_climb_timer = player.state_timer
            player.vel.y = C.PLAYER_WALL_CLIMB_SPEED; player.vel.x = 0
        elif new_state == 'wall_slide' or new_state == 'wall_hang': player.wall_climb_timer = 0
        elif new_state == 'petrified':
            player.is_petrified = True; player.is_stone_smashed = False
            player.is_dead = True; player.death_animation_finished = True
            player.vel.xy = 0,0; player.acc.xy = 0,0
            player.is_aflame = False; player.is_deflaming = False
            player.is_frozen = False; player.is_defrosting = False
        elif new_state == 'smashed':
            player.is_stone_smashed = True; player.is_petrified = True
            player.stone_smashed_timer_start = player.state_timer
            player.is_dead = True; player.death_animation_finished = False
            player.vel.xy = 0,0; player.acc.xy = 0,0
        elif new_state == 'frozen': player.vel.xy = 0,0; player.acc.x = 0
        elif new_state == 'defrost': player.vel.xy = 0,0; player.acc.x = 0
        elif new_state == 'idle': pass
        # For 'burning', 'aflame_crouch', 'burning_crouch', 'deflame', 'deflame_crouch'
        # the primary flags (is_aflame, is_deflaming) and their timers are already handled
        # by player.apply_aflame_effect() or player.update_status_effects().
        # This function (set_player_state) is mainly ensuring the visual state string matches.

        from player_animation_handler import update_player_animation
        update_player_animation(player)

    elif not player.is_dead:
         player._last_state_for_debug = player.state

#################### END OF MODIFIED FILE: player_state_handler.py ####################