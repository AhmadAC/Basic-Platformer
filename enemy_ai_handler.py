########## START OF FILE: enemy_ai_handler.py ##########

"""
version 1.0.0.5 (Added debug prints for state tracking; refined aflame/deflame state enforcement)
Handles AI logic for enemies, including patrolling, chasing, and attacking decisions.
Functions here will typically take an 'enemy' instance as their first argument.
"""
import pygame
import random
import math
import constants as C # For accessing enemy-specific constants and general game constants

# --- DEBUG FLAG ---
# Set to True to enable detailed state logging for enemies
ENABLE_ENEMY_AI_DEBUG_PRINTS = False #<<<<<<<<<<<<< SET TO True TO ENABLE DEBUG PRINTS

def log_enemy_state(enemy, message, current_time_ms):
    if ENABLE_ENEMY_AI_DEBUG_PRINTS:
        enemy_id_str = "N/A"
        if hasattr(enemy, 'id'): # Assuming your enemy might have an ID
            enemy_id_str = str(enemy.id)
        elif hasattr(enemy, 'rect'): # Fallback to rect object ID if no custom ID
            enemy_id_str = f"ObjID_{id(enemy.rect)}"

        print(f"[{current_time_ms/1000:.2f}s] Enemy AI (ID: {enemy_id_str}): {message}")
        print(f"    Flags: is_aflame={getattr(enemy, 'is_aflame', 'N/A')}, "
              f"is_deflaming={getattr(enemy, 'is_deflaming', 'N/A')}, "
              f"is_frozen={getattr(enemy, 'is_frozen', 'N/A')}, "
              f"is_attacking={getattr(enemy, 'is_attacking', 'N/A')}")
        print(f"    State: current='{getattr(enemy, 'state', 'N/A')}', "
              f"ai_state='{getattr(enemy, 'ai_state', 'N/A')}'")
        if hasattr(enemy, 'pos'): print(f"    Pos: {getattr(enemy.pos, 'x', 'N/A')}, {getattr(enemy.pos, 'y', 'N/A')}")


def set_enemy_new_patrol_target(enemy):
    """
    Sets a new patrol target X-coordinate for the enemy instance.
    If a patrol_area (pygame.Rect) is defined for the enemy, it patrols within that area.
    Otherwise, it patrols a set distance from its current position.

    Args:
        enemy (Enemy): The enemy instance for which to set a new patrol target.
    """
    current_x = 0
    if hasattr(enemy, 'pos') and enemy.pos:
        current_x = enemy.pos.x
    elif hasattr(enemy, 'rect'):
        current_x = enemy.rect.centerx

    if hasattr(enemy, 'patrol_area') and enemy.patrol_area and isinstance(enemy.patrol_area, pygame.Rect):
         min_x_patrol = enemy.patrol_area.left + enemy.rect.width / 2
         max_x_patrol = enemy.patrol_area.right - enemy.rect.width / 2
         
         if min_x_patrol < max_x_patrol: 
             enemy.patrol_target_x = random.uniform(min_x_patrol, max_x_patrol)
         else: 
             enemy.patrol_target_x = enemy.patrol_area.centerx
    else: 
        patrol_direction = 1 if random.random() > 0.5 else -1
        enemy.patrol_target_x = current_x + patrol_direction * getattr(C, 'ENEMY_PATROL_DIST', 150)
    
    if not hasattr(enemy, 'patrol_target_x') or enemy.patrol_target_x is None:
        enemy.patrol_target_x = current_x


def enemy_ai_update(enemy, players_list_for_ai):
    """
    Updates the enemy's AI state (e.g., patrolling, chasing, attacking) and behavior
    based on player proximity and other conditions. Modifies the enemy instance directly.

    Args:
        enemy (Enemy): The enemy instance to update.
        players_list_for_ai (list): A list of player Sprites that the AI can target.
    """
    current_time_ms = pygame.time.get_ticks()
    log_enemy_state(enemy, "Starting AI update.", current_time_ms)

    if not hasattr(enemy, '_valid_init') or not enemy._valid_init or \
       (hasattr(enemy, 'is_dead') and enemy.is_dead) or not enemy.alive():
        if hasattr(enemy, 'acc'): enemy.acc.x = 0
        log_enemy_state(enemy, "Entity invalid, dead, or not alive. No AI.", current_time_ms)
        return

    if (hasattr(enemy, 'is_frozen') and enemy.is_frozen) or \
       (hasattr(enemy, 'is_defrosting') and enemy.is_defrosting):
        if hasattr(enemy, 'acc'): enemy.acc.x = 0
        # Ensure correct animation state if frozen/defrosting
        if hasattr(enemy, 'is_frozen') and enemy.is_frozen and enemy.state != 'frozen':
            log_enemy_state(enemy, "Entity is frozen. Forcing 'frozen' state.", current_time_ms)
            enemy.set_state('frozen')
        elif hasattr(enemy, 'is_defrosting') and enemy.is_defrosting and enemy.state != 'defrosting':
            log_enemy_state(enemy, "Entity is defrosting. Forcing 'defrosting' state.", current_time_ms)
            enemy.set_state('defrosting')
        else:
            log_enemy_state(enemy, "Entity frozen/defrosting. State already correct or flag not specific. No AI movement.", current_time_ms)
        return

    if hasattr(enemy, 'is_taking_hit') and enemy.is_taking_hit and \
       hasattr(enemy, 'hit_timer') and hasattr(enemy, 'hit_cooldown') and \
       current_time_ms - enemy.hit_timer < enemy.hit_cooldown:
        if hasattr(enemy, 'acc'): enemy.acc.x = 0
        log_enemy_state(enemy, "Entity is in hit stun / cooldown. No AI.", current_time_ms)
        # 'hit' state should be managed by the hit logic itself
        return

    # --- Player Detection (Copied from previous, with checks) ---
    closest_target_player = None
    min_squared_distance_to_player = float('inf')
    # Ensure enemy.pos exists for distance calculations
    if not hasattr(enemy, 'pos') or not enemy.pos:
        log_enemy_state(enemy, "Enemy has no 'pos' attribute. Cannot detect players.", current_time_ms)
        if hasattr(enemy, 'acc'): enemy.acc.x = 0
        return # Cannot proceed without enemy position

    for player_candidate in players_list_for_ai:
        is_candidate_targetable = (
            player_candidate and hasattr(player_candidate, '_valid_init') and player_candidate._valid_init and
            hasattr(player_candidate, 'pos') and hasattr(player_candidate, 'rect') and
            player_candidate.alive() and not getattr(player_candidate, 'is_dead', True)
        )
        if is_candidate_targetable:
            squared_dist = (player_candidate.pos.x - enemy.pos.x)**2 + \
                           (player_candidate.pos.y - enemy.pos.y)**2
            if squared_dist < min_squared_distance_to_player:
                min_squared_distance_to_player = squared_dist
                closest_target_player = player_candidate

    distance_to_target_player = math.sqrt(min_squared_distance_to_player) if closest_target_player else float('inf')
    enemy_attack_range = getattr(C, 'ENEMY_ATTACK_RANGE', 60)
    enemy_detection_range = getattr(C, 'ENEMY_DETECTION_RANGE', 200)
    enemy_standard_acceleration = getattr(C, 'ENEMY_ACCEL', 0.4)
    
    vertical_distance_to_player = float('inf')
    if closest_target_player and hasattr(closest_target_player, 'rect') and hasattr(enemy, 'rect'):
        vertical_distance_to_player = abs(closest_target_player.rect.centery - enemy.rect.centery)
    
    has_vertical_line_of_sight = vertical_distance_to_player < enemy.rect.height * 1.0 if closest_target_player and hasattr(enemy, 'rect') else False
    is_player_in_attack_range = distance_to_target_player < enemy_attack_range and has_vertical_line_of_sight
    is_player_in_detection_range = distance_to_target_player < enemy_detection_range and has_vertical_line_of_sight


    # --- Aflame/Deflame Handling (High Priority) ---
    if hasattr(enemy, 'is_aflame') and enemy.is_aflame:
        log_enemy_state(enemy, "AFLAME check: is_aflame is True.", current_time_ms)
        if enemy.state != 'aflame':
            log_enemy_state(enemy, f"  State '{enemy.state}' is not 'aflame'. Setting to 'aflame'.", current_time_ms)
            enemy.set_state('aflame')
            log_enemy_state(enemy, f"  After set_state('aflame'), new state is '{enemy.state}'.", current_time_ms)
        else:
            log_enemy_state(enemy, "  State already 'aflame'.", current_time_ms)

        if not (hasattr(enemy, 'pos') and hasattr(enemy, 'acc')): return
        if closest_target_player and is_player_in_detection_range:
            enemy.ai_state = 'chasing_aflame'
            should_face_right = (closest_target_player.pos.x > enemy.pos.x)
            enemy.acc.x = enemy_standard_acceleration * (1 if should_face_right else -1)
            if enemy.facing_right != should_face_right: enemy.facing_right = should_face_right
        else:
            enemy.ai_state = 'patrolling_aflame'
            if not hasattr(enemy, 'patrol_target_x') or enemy.patrol_target_x is None or \
               abs(enemy.pos.x - enemy.patrol_target_x) < 10:
                set_enemy_new_patrol_target(enemy)
            should_face_right = (enemy.patrol_target_x > enemy.pos.x)
            enemy.acc.x = enemy_standard_acceleration * 0.7 * (1 if should_face_right else -1)
            if enemy.facing_right != should_face_right: enemy.facing_right = should_face_right
        log_enemy_state(enemy, "AFLAME: Handled movement, returning.", current_time_ms)
        return

    elif hasattr(enemy, 'is_deflaming') and enemy.is_deflaming: # IMPORTANT: This must be 'elif'
        log_enemy_state(enemy, "DEFLAME check: is_deflaming is True.", current_time_ms)
        if enemy.state != 'deflame':
            log_enemy_state(enemy, f"  State '{enemy.state}' is not 'deflame'. Setting to 'deflame'.", current_time_ms)
            enemy.set_state('deflame')
            log_enemy_state(enemy, f"  After set_state('deflame'), new state is '{enemy.state}'.", current_time_ms)
        else:
            log_enemy_state(enemy, "  State already 'deflame'.", current_time_ms)

        if not (hasattr(enemy, 'pos') and hasattr(enemy, 'acc')): return
        if closest_target_player and is_player_in_detection_range:
            enemy.ai_state = 'chasing_deflaming'
            should_face_right = (closest_target_player.pos.x > enemy.pos.x)
            enemy.acc.x = enemy_standard_acceleration * (1 if should_face_right else -1)
            if enemy.facing_right != should_face_right: enemy.facing_right = should_face_right
        else:
            enemy.ai_state = 'patrolling_deflaming'
            if not hasattr(enemy, 'patrol_target_x') or enemy.patrol_target_x is None or \
               abs(enemy.pos.x - enemy.patrol_target_x) < 10:
                set_enemy_new_patrol_target(enemy)
            should_face_right = (enemy.patrol_target_x > enemy.pos.x)
            enemy.acc.x = enemy_standard_acceleration * 0.7 * (1 if should_face_right else -1)
            if enemy.facing_right != should_face_right: enemy.facing_right = should_face_right
        log_enemy_state(enemy, "DEFLAME: Handled movement, returning.", current_time_ms)
        return

    # --- Post-attack Pause ---
    if hasattr(enemy, 'post_attack_pause_timer') and enemy.post_attack_pause_timer > 0 and \
       current_time_ms < enemy.post_attack_pause_timer:
        if hasattr(enemy, 'acc'): enemy.acc.x = 0
        if enemy.state != 'idle':
            log_enemy_state(enemy, "Post-attack pause. Setting state to 'idle'.", current_time_ms)
            enemy.set_state('idle')
        else:
            log_enemy_state(enemy, "Post-attack pause. Already 'idle'.", current_time_ms)
        return

    # --- Ongoing Attack Animation Handling ---
    if hasattr(enemy, 'is_attacking') and enemy.is_attacking:
        if not (hasattr(enemy, 'attack_timer') and hasattr(enemy, 'attack_duration')):
            enemy.is_attacking = False
            if hasattr(enemy, 'acc'): enemy.acc.x = 0
            log_enemy_state(enemy, "ATTACKING: Missing attack_timer/duration. Failsafe: stopping attack.", current_time_ms)
            return

        if current_time_ms - enemy.attack_timer >= enemy.attack_duration:
            log_enemy_state(enemy, "ATTACKING: Attack animation finished.", current_time_ms)
            enemy.is_attacking = False
            if hasattr(enemy, 'attack_type'): enemy.attack_type = 0
            if hasattr(enemy, 'attack_cooldown_timer'): enemy.attack_cooldown_timer = current_time_ms
            if hasattr(enemy, 'post_attack_pause_timer') and hasattr(enemy, 'post_attack_pause_duration'):
                enemy.post_attack_pause_timer = current_time_ms + enemy.post_attack_pause_duration
            
            # Aflame/Deflame already handled by returning earlier.
            enemy.set_state('idle')
            log_enemy_state(enemy, "ATTACKING: Set state to 'idle' after attack.", current_time_ms)
            if hasattr(enemy, 'acc'): enemy.acc.x = 0
            return
        else:
            if hasattr(enemy, 'acc'): enemy.acc.x = 0
            log_enemy_state(enemy, "ATTACKING: Still in attack animation. No X movement.", current_time_ms)
            return

    # --- Standard AI Logic ---
    if not (hasattr(enemy, 'pos') and hasattr(enemy, 'acc') and hasattr(enemy, 'facing_right') and hasattr(enemy, 'state')):
        log_enemy_state(enemy, "Missing essential attributes (pos, acc, facing_right, state). Cannot run standard AI.", current_time_ms)
        return

    if not hasattr(enemy, 'patrol_target_x') or enemy.patrol_target_x is None:
        set_enemy_new_patrol_target(enemy)
        log_enemy_state(enemy, f"Initialized patrol_target_x to {enemy.patrol_target_x}", current_time_ms)

    enemy_attack_cooldown_duration = getattr(C, 'ENEMY_ATTACK_COOLDOWN', 1500)
    is_attack_off_cooldown = not hasattr(enemy, 'attack_cooldown_timer') or \
                             (hasattr(enemy, 'attack_cooldown_timer') and \
                              current_time_ms - enemy.attack_cooldown_timer > enemy_attack_cooldown_duration)

    if not closest_target_player:
        enemy.ai_state = 'patrolling'
        if enemy.state not in ['patrolling', 'run']:
            enemy.set_state('patrolling')
        log_enemy_state(enemy, f"No target. Patrolling. Current state '{enemy.state}'.", current_time_ms)

        if abs(enemy.pos.x - enemy.patrol_target_x) < 10:
            set_enemy_new_patrol_target(enemy)
            log_enemy_state(enemy, f"Patrol target reached. New target: {enemy.patrol_target_x}", current_time_ms)

        should_face_right_for_patrol = (enemy.patrol_target_x > enemy.pos.x)
        patrol_acceleration = enemy_standard_acceleration * 0.7
        enemy.acc.x = patrol_acceleration * (1 if should_face_right_for_patrol else -1)
        if enemy.facing_right != should_face_right_for_patrol: enemy.facing_right = should_face_right_for_patrol
        return

    current_target_acceleration_x = 0
    current_target_facing_right = enemy.facing_right

    if is_player_in_attack_range and is_attack_off_cooldown:
        log_enemy_state(enemy, "Player in attack range and cooldown ready. Initiating attack.", current_time_ms)
        enemy.ai_state = 'attacking'
        current_target_facing_right = (closest_target_player.pos.x > enemy.pos.x)
        enemy.facing_right = current_target_facing_right
        
        attack_animation_key_to_use = 'attack'
        if hasattr(enemy, 'animations') and 'attack_nm' in enemy.animations and enemy.animations['attack_nm']:
            attack_animation_key_to_use = 'attack_nm'
        
        enemy.set_state(attack_animation_key_to_use)
        log_enemy_state(enemy, f"Set state to '{attack_animation_key_to_use}'. New state '{enemy.state}'.", current_time_ms)
        # Assuming enemy.set_state for attack also sets enemy.is_attacking = True and timers.
        return

    elif is_player_in_detection_range:
        enemy.ai_state = 'chasing'
        current_target_facing_right = (closest_target_player.pos.x > enemy.pos.x)
        current_target_acceleration_x = enemy_standard_acceleration * (1 if current_target_facing_right else -1)
        if enemy.state not in ['chasing', 'run']:
            enemy.set_state('chasing') # Or 'run'
        log_enemy_state(enemy, f"Player in detection range. Chasing. Current state '{enemy.state}'.", current_time_ms)

    else:
        enemy.ai_state = 'patrolling'
        if enemy.state not in ['patrolling', 'run']:
            enemy.set_state('patrolling')
        log_enemy_state(enemy, f"Player not in detection range. Patrolling. Current state '{enemy.state}'.", current_time_ms)

        if abs(enemy.pos.x - enemy.patrol_target_x) < 10:
            set_enemy_new_patrol_target(enemy)
            log_enemy_state(enemy, f"Patrol target reached (default). New target: {enemy.patrol_target_x}", current_time_ms)

        current_target_facing_right = (enemy.patrol_target_x > enemy.pos.x)
        current_target_acceleration_x = enemy_standard_acceleration * 0.7 * \
                                        (1 if current_target_facing_right else -1)

    enemy.acc.x = current_target_acceleration_x
    if not (hasattr(enemy, 'is_attacking') and enemy.is_attacking) and \
       enemy.facing_right != current_target_facing_right:
         enemy.facing_right = current_target_facing_right
    log_enemy_state(enemy, f"End of standard AI. Acc.x: {enemy.acc.x}, FacingRight: {enemy.facing_right}", current_time_ms)