# editor/editor_updates.py
# -*- coding: utf-8 -*-
"""
Continuous update functions for the editor state, called each frame.
"""
import pygame
import math
import logging
from typing import Tuple

import editor_config as ED_CONFIG
from editor_state import EditorState

logger = logging.getLogger(__name__)

def update_continuous_camera_pan(editor_state: EditorState, map_view_rect: pygame.Rect, mouse_pos: Tuple[int,int], dt: float):
    """
    Handles continuous camera panning via WASD keys and edge scrolling.
    Also manages camera momentum when mouse leaves map view.
    """
    if editor_state.active_dialog_type: 
        editor_state.camera_momentum_pan=(0.0,0.0)
        return

    keys = pygame.key.get_pressed()
    pan_px_sec = ED_CONFIG.KEY_PAN_SPEED_PIXELS_PER_SECOND
    edge_pan_px_sec = ED_CONFIG.EDGE_SCROLL_SPEED_PIXELS_PER_SECOND
    pan_amount, edge_pan_amount = pan_px_sec * dt, edge_pan_px_sec * dt
    
    cam_moved_by_direct_input = False
    dx, dy = 0.0, 0.0

    if keys[pygame.K_a]: dx -= pan_amount; cam_moved_by_direct_input=True
    if keys[pygame.K_d]: dx += pan_amount; cam_moved_by_direct_input=True
    if keys[pygame.K_w]: dy -= pan_amount; cam_moved_by_direct_input=True
    if keys[pygame.K_s] and not (keys[pygame.K_LCTRL]or keys[pygame.K_RCTRL]): dy+=pan_amount; cam_moved_by_direct_input=True
    
    prev_is_mouse_over_map = editor_state.is_mouse_over_map_view
    editor_state.is_mouse_over_map_view = map_view_rect.collidepoint(mouse_pos)

    if editor_state.is_mouse_over_map_view:
        editor_state.camera_momentum_pan = (0.0, 0.0) # Stop momentum if mouse re-enters
        if editor_state.last_mouse_pos_map_view and dt > 0.0001: # Calculate mouse velocity
            vel_x = (mouse_pos[0] - editor_state.last_mouse_pos_map_view[0]) / dt
            vel_y = (mouse_pos[1] - editor_state.last_mouse_pos_map_view[1]) / dt
            editor_state.mouse_velocity_map_view = (vel_x, vel_y)
        else:
            editor_state.mouse_velocity_map_view = (0.0, 0.0)
        editor_state.last_mouse_pos_map_view = mouse_pos

        # Edge scrolling if mouse is over map and no key pan
        if not cam_moved_by_direct_input:
            zone=ED_CONFIG.EDGE_SCROLL_ZONE_THICKNESS
            if mouse_pos[0]<map_view_rect.left+zone: dx-=edge_pan_amount; cam_moved_by_direct_input=True # Treat edge scroll as direct input for momentum
            elif mouse_pos[0]>map_view_rect.right-zone: dx+=edge_pan_amount; cam_moved_by_direct_input=True
            if mouse_pos[1]<map_view_rect.top+zone: dy-=edge_pan_amount; cam_moved_by_direct_input=True
            elif mouse_pos[1]>map_view_rect.bottom-zone: dy+=edge_pan_amount; cam_moved_by_direct_input=True
            
    elif prev_is_mouse_over_map and not editor_state.is_mouse_over_map_view: # Mouse just left map view
        if not cam_moved_by_direct_input and \
           (abs(editor_state.mouse_velocity_map_view[0]) > ED_CONFIG.CAMERA_MOMENTUM_MIN_SPEED_THRESHOLD or \
            abs(editor_state.mouse_velocity_map_view[1]) > ED_CONFIG.CAMERA_MOMENTUM_MIN_SPEED_THRESHOLD) :
            
            # Changed: Removed negative sign to make camera pan in direction of swipe
            fling_vx = editor_state.mouse_velocity_map_view[0] * ED_CONFIG.CAMERA_MOMENTUM_INITIAL_MULTIPLIER
            fling_vy = editor_state.mouse_velocity_map_view[1] * ED_CONFIG.CAMERA_MOMENTUM_INITIAL_MULTIPLIER
            editor_state.camera_momentum_pan = (fling_vx, fling_vy)
            logger.debug(f"Mouse exited map view. Initiated camera fling with momentum: ({fling_vx:.2f}, {fling_vy:.2f}) based on mouse velocity {editor_state.mouse_velocity_map_view}")
        
        editor_state.last_mouse_pos_map_view = None
        editor_state.mouse_velocity_map_view = (0.0,0.0)

    if cam_moved_by_direct_input: # Keys or edge scroll
        editor_state.camera_momentum_pan = (0.0, 0.0) # Stop momentum if there's direct input
        editor_state.camera_offset_x += dx
        editor_state.camera_offset_y += dy

    # Clamp camera
    max_cam_x = max(0, editor_state.get_map_pixel_width() - map_view_rect.width)
    max_cam_y = max(0, editor_state.get_map_pixel_height() - map_view_rect.height)
    editor_state.camera_offset_x = max(0, min(editor_state.camera_offset_x, max_cam_x))
    editor_state.camera_offset_y = max(0, min(editor_state.camera_offset_y, max_cam_y))


def update_asset_palette_scroll_momentum(editor_state: EditorState, dt: float,
                                         asset_list_visible_height: float,
                                         total_asset_content_height: float):
    """
    Updates the asset palette scroll position based on momentum.
    """
    if not hasattr(editor_state, 'asset_palette_scroll_momentum'):
        editor_state.asset_palette_scroll_momentum = 0.0

    if editor_state.asset_palette_scroll_momentum != 0.0:
        delta_scroll = editor_state.asset_palette_scroll_momentum * dt
        editor_state.asset_palette_scroll_y += delta_scroll

        # Dampen momentum (more frame-rate independent)
        # The (dt * 60.0) part scales damping as if it's happening 60 times a second
        editor_state.asset_palette_scroll_momentum *= (ED_CONFIG.ASSET_PALETTE_FLING_DAMPING_FACTOR ** (dt * 60.0)) 
        
        if abs(editor_state.asset_palette_scroll_momentum) < ED_CONFIG.ASSET_PALETTE_FLING_MIN_SPEED_THRESHOLD:
            editor_state.asset_palette_scroll_momentum = 0.0

        max_scroll = max(0, total_asset_content_height - asset_list_visible_height)
        
        boundary_hit = False
        if editor_state.asset_palette_scroll_y < 0:
            editor_state.asset_palette_scroll_y = 0
            boundary_hit = True
        elif editor_state.asset_palette_scroll_y > max_scroll:
            editor_state.asset_palette_scroll_y = max_scroll
            boundary_hit = True
        
        if boundary_hit:
            editor_state.asset_palette_scroll_momentum = 0.0 # Stop dead at boundary