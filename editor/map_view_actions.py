#################### START OF FILE: map_view_actions.py ####################

# editor/map_view_actions.py
# -*- coding: utf-8 -*-
"""
Contains functions for handling map editing actions originating from the MapViewWidget.
"""
import logging
import os

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple
from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QImage

from . import editor_config as ED_CONFIG
from . import editor_history
from . import editor_map_utils

if TYPE_CHECKING:
    from .map_view_widget import MapViewWidget # To avoid circular import for type hinting
    from .editor_state import EditorState

logger = logging.getLogger(__name__)


def perform_place_action(map_view: 'MapViewWidget', grid_x: int, grid_y: int, continuous: bool = False, is_first_action: bool = False):
    editor_state = map_view.editor_state
    if editor_state.current_tool_mode != "place": return 
    if continuous and (grid_x, grid_y) == editor_state.last_painted_tile_coords: return
    
    effective_asset_key, is_flipped, rotation, _ = editor_state.get_current_placement_info()
    if not effective_asset_key: return
    
    asset_definition_for_placement = editor_state.assets_palette.get(effective_asset_key)
    if not asset_definition_for_placement:
        if effective_asset_key.startswith(ED_CONFIG.CUSTOM_ASSET_PALETTE_PREFIX):
             filename = effective_asset_key.split(ED_CONFIG.CUSTOM_ASSET_PALETTE_PREFIX,1)[1]
             asset_definition_for_placement = {
                "game_type_id": ED_CONFIG.CUSTOM_IMAGE_ASSET_KEY,
                "asset_editor_key": effective_asset_key, 
                "source_file_path": f"Custom/{filename}", 
                "colorable": False, "category": "custom"
             }
        else:
            logger.error(f"Palette data for effective asset '{effective_asset_key}' not found for placement.")
            return

    made_change_in_stroke = False
    if is_first_action: editor_history.push_undo_state(editor_state)

    is_placer_tool = False
    if editor_state.palette_current_asset_key: 
        original_palette_asset_data = editor_state.assets_palette.get(editor_state.palette_current_asset_key)
        if original_palette_asset_data and \
           original_palette_asset_data.get("places_asset_key") and \
           original_palette_asset_data.get("icon_type") == "2x2_placer":
            is_placer_tool = True
    
    if is_placer_tool:
        for r_off in range(2):
            for c_off in range(2):
                if place_single_object_on_map(map_view, effective_asset_key, asset_definition_for_placement, grid_x + c_off, grid_y + r_off, is_flipped, rotation):
                    made_change_in_stroke = True
    else:
        if place_single_object_on_map(map_view, effective_asset_key, asset_definition_for_placement, grid_x, grid_y, is_flipped, rotation):
            made_change_in_stroke = True

    if made_change_in_stroke: map_view.map_content_changed.emit()
    editor_state.last_painted_tile_coords = (grid_x, grid_y)

def place_single_object_on_map(map_view: 'MapViewWidget', asset_key_for_data: str, asset_definition: Dict, grid_x: int, grid_y: int, is_flipped_h: bool, rotation: int) -> bool:
    editor_state = map_view.editor_state
    world_x = int(float(grid_x * editor_state.grid_size))
    world_y = int(float(grid_y * editor_state.grid_size))

    game_id = asset_definition.get("game_type_id", "unknown")
    category = asset_definition.get("category", "unknown")
    is_spawn_type = category == "spawn"
    
    is_custom_image_type = (asset_key_for_data == ED_CONFIG.CUSTOM_IMAGE_ASSET_KEY or
                           (asset_key_for_data.startswith(ED_CONFIG.CUSTOM_ASSET_PALETTE_PREFIX) and game_id == ED_CONFIG.CUSTOM_IMAGE_ASSET_KEY) )
    is_trigger_type = asset_key_for_data == ED_CONFIG.TRIGGER_SQUARE_ASSET_KEY

    if not is_spawn_type and not is_custom_image_type and not is_trigger_type:
        for obj in editor_state.placed_objects:
            if obj.get("world_x") == world_x and obj.get("world_y") == world_y and \
               obj.get("asset_editor_key") == asset_key_for_data and \
               obj.get("is_flipped_h", False) == is_flipped_h and \
               obj.get("rotation", 0) == rotation: 
                if asset_definition.get("colorable") and editor_state.current_selected_asset_paint_color and obj.get("override_color") != editor_state.current_selected_asset_paint_color:
                    obj["override_color"] = editor_state.current_selected_asset_paint_color
                    map_view.update_specific_object_visuals(obj); return True
                return False

    new_obj_data: Dict[str, Any] = {
        "asset_editor_key": asset_key_for_data, 
        "world_x": world_x, "world_y": world_y,
        "game_type_id": game_id,
        "layer_order": 0,
        "properties": ED_CONFIG.get_default_properties_for_asset(game_id),
        "is_flipped_h": is_flipped_h,
        "rotation": rotation,
        "editor_hidden": False, 
        "editor_locked": False  
    }

    if is_custom_image_type:
        if asset_key_for_data.startswith(ED_CONFIG.CUSTOM_ASSET_PALETTE_PREFIX):
             filename_from_key = asset_key_for_data.split(ED_CONFIG.CUSTOM_ASSET_PALETTE_PREFIX, 1)[1]
             new_obj_data["source_file_path"] = f"Custom/{filename_from_key}"
        else:
             new_obj_data["source_file_path"] = asset_definition.get("source_file_path", "")

        map_folder = editor_map_utils.get_map_specific_folder_path(editor_state, editor_state.map_name_for_function)
        full_path = ""
        if map_folder and new_obj_data["source_file_path"]:
             full_path = os.path.join(map_folder, new_obj_data["source_file_path"])
        
        if full_path and os.path.exists(full_path):
            q_img = QImage(full_path)
            if not q_img.isNull():
                new_obj_data["original_width"] = q_img.width(); new_obj_data["original_height"] = q_img.height()
                new_obj_data["current_width"] = q_img.width(); new_obj_data["current_height"] = q_img.height()
            else:
                new_obj_data["original_width"]=new_obj_data["current_width"]=ED_CONFIG.BASE_GRID_SIZE*2
                new_obj_data["original_height"]=new_obj_data["current_height"]=ED_CONFIG.BASE_GRID_SIZE*2
        else: 
            new_obj_data["original_width"]=new_obj_data["current_width"]=ED_CONFIG.BASE_GRID_SIZE*2
            new_obj_data["original_height"]=new_obj_data["current_height"]=ED_CONFIG.BASE_GRID_SIZE*2
        new_obj_data["crop_rect"] = None 

    elif is_trigger_type:
        new_obj_data["current_width"] = ED_CONFIG.BASE_GRID_SIZE * 2
        new_obj_data["current_height"] = ED_CONFIG.BASE_GRID_SIZE * 2

    elif asset_definition.get("colorable") and editor_state.current_selected_asset_paint_color:
        new_obj_data["override_color"] = editor_state.current_selected_asset_paint_color

    if is_spawn_type: 
        editor_state.placed_objects = [obj for obj in editor_state.placed_objects if obj.get("game_type_id") != game_id]

    editor_state.placed_objects.append(new_obj_data)
    map_view.draw_placed_objects() # Call MapView's method
    return True


def perform_erase_action(map_view: 'MapViewWidget', grid_x: int, grid_y: int, continuous: bool = False, is_first_action: bool = False):
    editor_state = map_view.editor_state
    if editor_state.current_tool_mode != "tool_eraser": return
    if continuous and (grid_x, grid_y) == editor_state.last_erased_tile_coords: return
    world_x_snapped = float(grid_x * editor_state.grid_size); world_y_snapped = float(grid_y * editor_state.grid_size)
    target_point_scene = QPointF(world_x_snapped + editor_state.grid_size / 2.0, world_y_snapped + editor_state.grid_size / 2.0)
    item_to_remove_data: Optional[Dict[str, Any]] = None; highest_z = -float('inf')
    
    for obj_data in editor_state.placed_objects:
        obj_x = obj_data.get("world_x", 0); obj_y = obj_data.get("world_y", 0)
        # Default to grid_size for non-resizable, otherwise use current_width/height
        is_resizable = obj_data.get("asset_editor_key") in [ED_CONFIG.CUSTOM_IMAGE_ASSET_KEY, ED_CONFIG.TRIGGER_SQUARE_ASSET_KEY]
        obj_w = obj_data.get("current_width") if is_resizable else editor_state.grid_size
        obj_h = obj_data.get("current_height") if is_resizable else editor_state.grid_size
        
        obj_rect = QRectF(float(obj_x), float(obj_y), float(obj_w), float(obj_h))
        if obj_rect.contains(target_point_scene):
            current_obj_z = obj_data.get("layer_order", 0)
            if current_obj_z >= highest_z:
                highest_z = current_obj_z; item_to_remove_data = obj_data
                
    if item_to_remove_data:
        if is_first_action: editor_history.push_undo_state(editor_state)
        editor_state.placed_objects.remove(item_to_remove_data)
        item_id = id(item_to_remove_data)
        if item_id in map_view._map_object_items: # Accessing private member, consider refactor
            map_obj_item = map_view._map_object_items.pop(item_id)
            if hasattr(map_obj_item, 'show_interaction_handles'): # BaseResizableMapItem
                map_obj_item.show_interaction_handles(False) # type: ignore
                for handle in map_obj_item.interaction_handles: # type: ignore
                    if handle.scene(): map_view.map_scene.removeItem(handle)
                map_obj_item.interaction_handles.clear() # type: ignore
            if map_obj_item.scene(): map_view.map_scene.removeItem(map_obj_item)
        map_view.map_content_changed.emit()
        editor_state.last_erased_tile_coords = (grid_x, grid_y)


def perform_color_tile_action(map_view: 'MapViewWidget', grid_x: int, grid_y: int, continuous: bool = False, is_first_action: bool = False):
    editor_state = map_view.editor_state
    if editor_state.current_tool_mode != "color_pick": return
    if not editor_state.current_tile_paint_color: return
    if continuous and (grid_x, grid_y) == editor_state.last_colored_tile_coords: return
    
    world_x_snapped = float(grid_x * editor_state.grid_size)
    world_y_snapped = float(grid_y * editor_state.grid_size)
    colored_something = False
    target_point_scene = QPointF(world_x_snapped + editor_state.grid_size / 2.0, world_y_snapped + editor_state.grid_size / 2.0)
    item_to_color_data: Optional[Dict[str, Any]] = None
    highest_z = -float('inf')

    for obj_data in editor_state.placed_objects:
        if obj_data.get("asset_editor_key") in [ED_CONFIG.CUSTOM_IMAGE_ASSET_KEY, ED_CONFIG.TRIGGER_SQUARE_ASSET_KEY]:
            continue
        asset_info = editor_state.assets_palette.get(str(obj_data.get("asset_editor_key")))
        if not asset_info or not asset_info.get("colorable"):
            continue
        
        obj_x = obj_data.get("world_x", 0)
        obj_y = obj_data.get("world_y", 0)
        obj_w_tuple, obj_h_tuple = asset_info.get("original_size_pixels", (editor_state.grid_size, editor_state.grid_size)) 
        obj_w, obj_h = float(obj_w_tuple), float(obj_h_tuple) 
        obj_rect = QRectF(float(obj_x), float(obj_y), float(obj_w), float(obj_h))

        if obj_rect.contains(target_point_scene):
            current_obj_z = obj_data.get("layer_order", 0)
            if current_obj_z >= highest_z:
                highest_z = current_obj_z
                item_to_color_data = obj_data
                
    if item_to_color_data:
        new_color = editor_state.current_tile_paint_color
        if item_to_color_data.get("override_color") != new_color:
            if is_first_action: editor_history.push_undo_state(editor_state)
            item_to_color_data["override_color"] = new_color
            map_view.update_specific_object_visuals(item_to_color_data)
            colored_something = True
            
    if colored_something:
        map_view.map_content_changed.emit()
        editor_state.last_colored_tile_coords = (grid_x, grid_y)

def delete_selected_map_objects_action(map_view: 'MapViewWidget'):
    editor_state = map_view.editor_state
    selected_qt_items = map_view.map_scene.selectedItems()
    if not selected_qt_items: return

    # Import here to avoid partial init issues if these classes are complex
    from .map_object_items import StandardMapObjectItem
    from .editor_custom_items import BaseResizableMapItem

    items_to_process = [item for item in selected_qt_items if isinstance(item, (StandardMapObjectItem, BaseResizableMapItem))]
    if not items_to_process: return

    editor_history.push_undo_state(editor_state)

    data_refs_to_remove = [item.map_object_data_ref for item in items_to_process if hasattr(item, 'map_object_data_ref')]

    editor_state.placed_objects = [
        obj for obj in editor_state.placed_objects if obj not in data_refs_to_remove
    ]

    for item_map_obj in items_to_process:
        item_data_ref = getattr(item_map_obj, 'map_object_data_ref', None)
        if item_data_ref:
            item_id = id(item_data_ref)
            if item_id in map_view._map_object_items: # Accessing private member
                del map_view._map_object_items[item_id]

        if isinstance(item_map_obj, BaseResizableMapItem):
            item_map_obj.show_interaction_handles(False)
            for handle in item_map_obj.interaction_handles:
                if handle.scene(): map_view.map_scene.removeItem(handle)
            item_map_obj.interaction_handles.clear()

        if item_map_obj.scene():
            map_view.map_scene.removeItem(item_map_obj)

    map_view.map_scene.clearSelection()
    map_view.map_content_changed.emit()
    map_view.map_object_selected_for_properties.emit(None)
    map_view.show_status_message(f"Deleted {len(data_refs_to_remove)} object(s).")

#################### END OF FILE: map_view_actions.py ####################