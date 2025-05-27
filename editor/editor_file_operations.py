# editor/editor_file_operations.py
# -*- coding: utf-8 -*-
"""
Handles file operations, dialogs, and map/asset management logic for the editor.
MODIFIED: load_map_action now uses QFileDialog.getExistingDirectory and then
          constructs the expected JSON file path from the selected folder name.
"""
from typing import Dict, Optional, Any, List, Tuple, cast, TYPE_CHECKING
import logging
import os
import shutil
from PySide6.QtCore import Qt, Slot, QTimer, Signal, QSize, QRectF # Added QRectF for type hinting
from PySide6.QtWidgets import QMessageBox, QFileDialog, QInputDialog, QColorDialog
from PySide6.QtGui import QImage, QPainter,QFont, QColor

from . import editor_config as ED_CONFIG
from . import editor_map_utils
from . import editor_history

if TYPE_CHECKING:
    from .editor_main_window import EditorMainWindow
    from .editor_state import EditorState

logger = logging.getLogger(__name__) # Uses the logger configured in editor_main_window.py

# --- Helper for internal save/export ---
def _internal_save_map_json(editor_state: 'EditorState', parent_window: 'EditorMainWindow') -> bool:
    logger.debug("Internal Save Map (JSON) called.")
    if editor_map_utils.save_map_to_json(editor_state):
        logger.info(f"Editor data saved: {os.path.basename(editor_state.current_json_filename or 'unknown.json')}.")
        return True
    else:
        QMessageBox.critical(parent_window, "Save Error", "Failed to save map editor data (.json). Check logs.")
        return False

def _internal_export_map_py(editor_state: 'EditorState', parent_window: 'EditorMainWindow') -> bool:
    logger.debug("Internal Export Map (PY) called.")
    if not editor_state.current_json_filename:
         logger.warning("Cannot Export PY: No JSON file path available (map likely not saved yet).")
         return False
    if editor_map_utils.export_map_to_game_python_script(editor_state):
        logger.info(f"Map exported for game: {os.path.basename(editor_state.current_map_filename or 'unknown.py')}.")
        return True
    else:
        QMessageBox.critical(parent_window, "Export Error", "Failed to export map for game (.py). Check logs.")
        return False

# --- Main File Operations ---

def new_map_action(main_win: 'EditorMainWindow'):
    editor_state = main_win.editor_state
    logger.info("New Map action triggered.")
    if not main_win.confirm_unsaved_changes("create a new map"):
        return
    map_name, ok = QInputDialog.getText(main_win, "New Map", "Enter map name (e.g., level_1):")
    if ok and map_name:
        clean_map_name = editor_map_utils.sanitize_map_name(map_name)
        if not clean_map_name:
            QMessageBox.warning(main_win, "Invalid Name", "Map name is invalid or results in an empty name after sanitization."); return
        map_folder_path = editor_map_utils.get_map_specific_folder_path(editor_state, clean_map_name)
        if map_folder_path and os.path.exists(map_folder_path):
            QMessageBox.warning(main_win, "Name Exists", f"A map folder (or file) named '{clean_map_name}' already exists in the maps directory."); return

        size_str, ok_size = QInputDialog.getText(main_win, "Map Size", "Enter map size (Width,Height in tiles):", text=f"{ED_CONFIG.DEFAULT_MAP_WIDTH_TILES},{ED_CONFIG.DEFAULT_MAP_HEIGHT_TILES}")
        if ok_size and size_str:
            try:
                w_str, h_str = size_str.split(',')
                width_tiles, height_tiles = int(w_str.strip()), int(h_str.strip())
                max_w, max_h = getattr(ED_CONFIG, "MAX_MAP_WIDTH_TILES", 2000), getattr(ED_CONFIG, "MAX_MAP_HEIGHT_TILES", 2000)
                if not (1 <= width_tiles <= max_w and 1 <= height_tiles <= max_h):
                    raise ValueError(f"Dimensions must be between 1x1 and {max_w}x{max_h}.")

                editor_map_utils.init_new_map_state(editor_state, clean_map_name, width_tiles, height_tiles)
                main_win.map_view_widget.load_map_from_state()
                main_win.asset_palette_widget.clear_selection()
                main_win.asset_palette_widget.populate_assets()
                main_win.properties_editor_widget.clear_display()
                main_win.selection_pane_widget.populate_items()
                if not main_win._is_embedded:
                    main_win.update_window_title()
                main_win.show_status_message(f"New map '{clean_map_name}' created. Save to create files.", ED_CONFIG.STATUS_BAR_MESSAGE_TIMEOUT * 2)
                editor_history.push_undo_state(editor_state)
                main_win.update_edit_actions_enabled_state()
            except ValueError as e_size:
                QMessageBox.warning(main_win, "Invalid Size", f"Invalid map size format or value: {e_size}")
            except Exception as e_new_map:
                logger.error(f"Error during new map creation: {e_new_map}", exc_info=True)
                QMessageBox.critical(main_win, "Error", f"Could not create new map: {e_new_map}")
    else:
        main_win.show_status_message("New map cancelled.")

def load_map_action(main_win: 'EditorMainWindow'):
    editor_state = main_win.editor_state
    logger.info("Load Map action triggered (folder selection mode).")
    if not main_win.confirm_unsaved_changes("load another map"):
        return

    maps_base_dir = editor_map_utils.get_maps_base_directory()
    if not editor_map_utils.ensure_maps_directory_exists():
         QMessageBox.critical(main_win, "Error", f"Cannot access or create base maps directory: {maps_base_dir}")
         return

    # Use QFileDialog.getExistingDirectory to select a folder
    selected_folder_path = QFileDialog.getExistingDirectory(
        main_win,
        "Select Map Folder to Load",
        maps_base_dir,
        QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks
    )

    if selected_folder_path:
        logger.info(f"Map folder selected by user: {selected_folder_path}")

        # Ensure the selected folder is within the expected maps_base_dir structure
        if not selected_folder_path.startswith(os.path.normpath(maps_base_dir)):
            QMessageBox.warning(main_win, "Invalid Selection", "Please select a map folder within the main maps directory.")
            logger.warning(f"User selected folder '{selected_folder_path}' which is outside the base maps dir '{maps_base_dir}'.")
            return

        map_folder_name = os.path.basename(selected_folder_path)
        expected_json_filename = f"{map_folder_name}{ED_CONFIG.LEVEL_EDITOR_SAVE_FORMAT_EXTENSION}"
        json_file_path_to_load = os.path.join(selected_folder_path, expected_json_filename)

        logger.info(f"Attempting to load map JSON: {json_file_path_to_load}")

        if os.path.exists(json_file_path_to_load) and os.path.isfile(json_file_path_to_load):
            if editor_map_utils.load_map_from_json(editor_state, json_file_path_to_load):
                main_win.map_view_widget.load_map_from_state()
                main_win.asset_palette_widget.clear_selection()
                main_win.asset_palette_widget.populate_assets()
                main_win.properties_editor_widget.clear_display()
                main_win.selection_pane_widget.populate_items()
                if not main_win._is_embedded:
                    main_win.update_window_title()
                main_win.show_status_message(f"Map '{editor_state.map_name_for_function}' loaded.")
                editor_history.push_undo_state(editor_state)
                main_win.update_edit_actions_enabled_state()
            else:
                QMessageBox.critical(main_win, "Load Error", f"Failed to load map data from: {expected_json_filename}")
        else:
            QMessageBox.warning(main_win, "Load Error",
                                f"Could not find the expected map file '{expected_json_filename}' in the selected folder '{map_folder_name}'.")
            logger.error(f"Map JSON file '{json_file_path_to_load}' not found or is not a file.")
    else:
        main_win.show_status_message("Load map cancelled.")


def save_map_action(main_win: 'EditorMainWindow') -> bool:
    editor_state = main_win.editor_state
    logger.info("Save Map (Unified JSON & PY) action triggered.")
    if not editor_state.map_name_for_function or editor_state.map_name_for_function == "untitled_map":
        map_name, ok = QInputDialog.getText(main_win, "Save Map As", "Enter map name (e.g., level_default):")
        if ok and map_name:
            clean_map_name = editor_map_utils.sanitize_map_name(map_name)
            if not clean_map_name:
                QMessageBox.warning(main_win, "Invalid Name", "Map name is invalid or empty.")
                return False

            map_folder_path_check = editor_map_utils.get_map_specific_folder_path(editor_state, clean_map_name)
            if map_folder_path_check and os.path.exists(map_folder_path_check):
                reply = QMessageBox.question(main_win, "Map Exists",
                                             f"A map folder named '{clean_map_name}' already exists. Overwrite its contents?",
                                             QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.No:
                    main_win.show_status_message("Save cancelled: map name exists and not overwritten.")
                    return False

            editor_map_utils.init_new_map_state(editor_state, clean_map_name,
                                                editor_state.map_width_tiles,
                                                editor_state.map_height_tiles,
                                                preserve_objects=True)
            if not main_win._is_embedded:
                main_win.update_window_title()
        else:
            main_win.show_status_message("Save cancelled: map name not provided.")
            return False

    map_folder = editor_map_utils.get_map_specific_folder_path(editor_state, editor_state.map_name_for_function, ensure_exists=True)
    if not map_folder:
         QMessageBox.critical(main_win, "Error", f"Could not create map folder for '{editor_state.map_name_for_function}'. Save failed.")
         return False

    json_saved_ok = _internal_save_map_json(editor_state, main_win)
    py_exported_ok = False
    if json_saved_ok:
        py_exported_ok = _internal_export_map_py(editor_state, main_win)

    if json_saved_ok and py_exported_ok:
        editor_state.unsaved_changes = False
        if not main_win._is_embedded:
            main_win.update_window_title()
        main_win.update_edit_actions_enabled_state()
        main_win.selection_pane_widget.populate_items()
        main_win.show_status_message(f"Map '{editor_state.map_name_for_function}' saved (JSON & PY).")
        return True
    elif json_saved_ok:
        editor_state.unsaved_changes = True
        main_win.show_status_message(f"Map '{editor_state.map_name_for_function}' JSON saved, but PY export FAILED. Try saving again.", ED_CONFIG.STATUS_BAR_MESSAGE_TIMEOUT * 2)
        if not main_win._is_embedded:
            main_win.update_window_title()
        main_win.update_edit_actions_enabled_state()
        return False
    else:
        main_win.show_status_message("Save Map FAILED. Check logs.")
        return False

def rename_map_action(main_win: 'EditorMainWindow'):
    editor_state = main_win.editor_state
    logger.info("Rename Map action triggered.")
    if not editor_state.current_json_filename or not editor_state.map_name_for_function or editor_state.map_name_for_function == "untitled_map":
        QMessageBox.information(main_win, "Rename Map", "No map loaded or saved to rename.")
        return
    old_map_name = editor_state.map_name_for_function
    new_name_str, ok = QInputDialog.getText(main_win, "Rename Map", f"New name for map '{old_map_name}':", text=old_map_name)
    if ok and new_name_str:
        clean_new_name = editor_map_utils.sanitize_map_name(new_name_str)
        if not clean_new_name:
            QMessageBox.warning(main_win, "Invalid Name", "New map name is invalid.")
            return
        if clean_new_name == old_map_name:
            main_win.show_status_message("Rename cancelled: name unchanged.")
            return

        old_map_folder_path = editor_map_utils.get_map_specific_folder_path(editor_state, old_map_name)
        new_map_folder_path = editor_map_utils.get_map_specific_folder_path(editor_state, clean_new_name)
        if not old_map_folder_path or not new_map_folder_path:
            QMessageBox.critical(main_win, "Rename Error", "Could not determine folder paths for rename operation.")
            return
        if os.path.exists(new_map_folder_path):
            QMessageBox.warning(main_win, "Rename Error", f"A map folder named '{clean_new_name}' already exists.")
            return
        if not os.path.exists(old_map_folder_path):
            QMessageBox.warning(main_win, "Rename Error", f"Original map folder '{old_map_name}' not found. Cannot rename.")
            return
        try:
            logger.info(f"Attempting rename of map folder '{old_map_folder_path}' to '{new_map_folder_path}'.")
            shutil.move(old_map_folder_path, new_map_folder_path)
            logger.info(f"Folder '{old_map_folder_path}' renamed to '{new_map_folder_path}'.")

            editor_state.map_name_for_function = clean_new_name
            editor_map_utils.init_new_map_state(editor_state, clean_new_name, editor_state.map_width_tiles, editor_state.map_height_tiles, preserve_objects=True)

            if not save_map_action(main_win):
                 QMessageBox.warning(main_win, "Rename Warning", "Folder renamed, but failed to save files with new name. Please try saving manually.")
            else:
                main_win.show_status_message(f"Map renamed to '{clean_new_name}' and files updated.")

            if not main_win._is_embedded:
                main_win.update_window_title()
            main_win.update_edit_actions_enabled_state()
            main_win.asset_palette_widget.populate_assets()
            main_win.selection_pane_widget.populate_items()
        except Exception as e_rename_map:
            logger.error(f"Error during map rename process: {e_rename_map}", exc_info=True)
            QMessageBox.critical(main_win, "Rename Error", f"An unexpected error occurred during map rename: {e_rename_map}")
    else:
        main_win.show_status_message("Rename map cancelled.")


def delete_map_folder_action(main_win: 'EditorMainWindow'):
    editor_state = main_win.editor_state
    logger.info("Delete Map Folder action triggered.")
    if not editor_state.current_json_filename or not editor_state.map_name_for_function or editor_state.map_name_for_function == "untitled_map":
         QMessageBox.information(main_win, "Delete Map", "No map loaded or saved to delete.")
         return
    map_name_to_delete = editor_state.map_name_for_function
    reply = QMessageBox.warning(main_win, "Confirm Delete",
                                 f"Are you sure you want to delete the ENTIRE folder for map '{map_name_to_delete}' including all its contents (JSON, PY, Custom assets)?\nThis action CANNOT be undone.",
                                 QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
    if reply == QMessageBox.StandardButton.Yes:
        if editor_map_utils.delete_map_folder_and_contents(editor_state, map_name_to_delete):
            main_win.show_status_message(f"Map folder '{map_name_to_delete}' deleted.")
            logger.info(f"Deleted map '{map_name_to_delete}' was currently loaded. Resetting editor state.")
            editor_state.reset_map_context()
            main_win.map_view_widget.load_map_from_state()
            main_win.asset_palette_widget.clear_selection()
            main_win.asset_palette_widget.populate_assets()
            main_win.properties_editor_widget.clear_display()
            main_win.selection_pane_widget.populate_items()
            if not main_win._is_embedded:
                main_win.update_window_title()
            main_win.update_edit_actions_enabled_state()
        else:
            QMessageBox.critical(main_win, "Delete Error", f"Failed to delete folder for map '{map_name_to_delete}'. Check logs.")
    else:
        main_win.show_status_message("Delete map folder cancelled.")

def export_map_as_image_action(main_win: 'EditorMainWindow'):
    editor_state = main_win.editor_state
    logger.info("Export Map as Image action triggered.")
    if not editor_state.placed_objects and not editor_state.current_json_filename:
        QMessageBox.information(main_win, "Export Error", "No map content to export as an image.")
        return

    default_map_name = editor_state.map_name_for_function if editor_state.map_name_for_function != "untitled_map" else "untitled_map_export"
    map_folder = editor_map_utils.get_map_specific_folder_path(editor_state, editor_state.map_name_for_function, ensure_exists=True)

    project_root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # Assuming editor is in a subfolder
    suggested_dir = map_folder if map_folder else os.path.join(project_root_dir, "map_exports")

    if not map_folder and not os.path.exists(suggested_dir):
        try: os.makedirs(suggested_dir)
        except OSError as e:
            logger.error(f"Could not create 'map_exports' dir: {e}")
            suggested_dir = editor_map_utils.get_maps_base_directory()

    suggested_path = os.path.join(suggested_dir, default_map_name + ".png")
    file_path, _ = QFileDialog.getSaveFileName(main_win, "Export Map as Image", suggested_path, "PNG Images (*.png);;All Files (*)")

    if not file_path:
        main_win.show_status_message("Export map as image cancelled.")
        return

    try:
        scene = main_win.map_view_widget.scene()
        if not scene:
            QMessageBox.critical(main_win, "Export Error", "Cannot access map scene.")
            return

        visible_objects_for_export = []
        for obj_data in editor_state.placed_objects:
            if not obj_data.get("editor_hidden", False):
                item_id = id(obj_data)
                original_item = main_win.map_view_widget._map_object_items.get(item_id)
                if original_item:
                    visible_objects_for_export.append(original_item)

        if not visible_objects_for_export:
             QMessageBox.information(main_win, "Export Error", "No visible map content to export.")
             return

        target_rect = QRectF()
        for item in visible_objects_for_export:
            target_rect = target_rect.united(item.sceneBoundingRect())

        if target_rect.isEmpty():
            QMessageBox.information(main_win, "Export Error", "Map is empty or no visible items with valid bounds.")
            return

        padding = 20
        target_rect.adjust(-padding, -padding, padding, padding)
        img_w, img_h = int(target_rect.width()), int(target_rect.height())

        if img_w <= 0 or img_h <= 0:
            QMessageBox.critical(main_win, "Export Error", f"Invalid image dimensions after padding: {img_w}x{img_h}")
            return

        image = QImage(img_w, img_h, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)

        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)

        bg_color = QColor(*editor_state.background_color)
        if bg_color.alpha() == 255:
            painter.fillRect(image.rect(), bg_color)

        hidden_items_backup = []
        for item_id, item_view in main_win.map_view_widget._map_object_items.items():
            obj_data_item = getattr(item_view, 'map_object_data_ref', None)
            if obj_data_item and obj_data_item.get("editor_hidden", False):
                if item_view.isVisible():
                    hidden_items_backup.append(item_view)
                    item_view.setVisible(False)

        scene.render(painter, QRectF(image.rect()), target_rect)

        for item_view_bkp in hidden_items_backup:
            item_view_bkp.setVisible(True)

        painter.end()

        if image.save(file_path, "PNG"):
            main_win.show_status_message(f"Map exported as image: {os.path.basename(file_path)}")
        else:
            QMessageBox.critical(main_win, "Export Error", f"Failed to save image to:\n{file_path}")
    except Exception as e:
        logger.error(f"Error exporting map as image: {e}", exc_info=True)
        QMessageBox.critical(main_win, "Export Error", f"Unexpected error during image export:\n{e}")
    finally:
        if 'hidden_items_backup' in locals():
            for item_view_bkp_finally in hidden_items_backup:
                if item_view_bkp_finally: item_view_bkp_finally.setVisible(True)


def upload_image_to_map_action(main_win: 'EditorMainWindow'):
    editor_state = main_win.editor_state
    logger.info("Upload Image to Map action triggered.")
    if not editor_state.map_name_for_function or editor_state.map_name_for_function == "untitled_map":
        QMessageBox.warning(main_win, "Upload Error", "A map must be named and active to upload images to it.")
        return
    map_name = editor_state.map_name_for_function
    custom_asset_folder = editor_map_utils.get_map_specific_folder_path(editor_state, map_name, subfolder="Custom", ensure_exists=True)
    if not custom_asset_folder:
        QMessageBox.critical(main_win, "Upload Error", f"Could not create 'Custom' asset folder for map '{map_name}'.")
        return

    file_path, _ = QFileDialog.getOpenFileName(main_win, "Select Image to Upload to Map's Custom Assets", custom_asset_folder, "Images (*.png *.jpg *.jpeg *.gif)")

    if file_path:
        image_filename = os.path.basename(file_path)
        destination_image_path = os.path.join(custom_asset_folder, image_filename)
        try:
            if os.path.normpath(file_path) != os.path.normpath(destination_image_path):
                if os.path.exists(destination_image_path):
                    reply = QMessageBox.question(main_win, "File Exists",
                                                 f"Image '{image_filename}' already exists in this map's Custom assets. Overwrite?",
                                                 QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
                    if reply == QMessageBox.StandardButton.No:
                        main_win.show_status_message(f"Image '{image_filename}' not overwritten.")
                        return
                shutil.copy2(file_path, destination_image_path)

            logger.info(f"Image '{file_path}' ensured at '{destination_image_path}'.")
            q_image = QImage(destination_image_path)
            if q_image.isNull():
                QMessageBox.warning(main_win, "Image Error", f"Could not load uploaded image: {image_filename}")
                return

            view_rect = main_win.map_view_widget.viewport().rect()
            center_scene_pos = main_win.map_view_widget.mapToScene(view_rect.center())

            img_original_width = q_image.width()
            img_original_height = q_image.height()

            new_image_obj_data = {
                "asset_editor_key": ED_CONFIG.CUSTOM_IMAGE_ASSET_KEY,
                "game_type_id": ED_CONFIG.CUSTOM_IMAGE_ASSET_KEY,
                "world_x": int(center_scene_pos.x() - img_original_width / 2),
                "world_y": int(center_scene_pos.y() - img_original_height / 2),
                "source_file_path": f"Custom/{image_filename}",
                "original_width": img_original_width,
                "original_height": img_original_height,
                "current_width": img_original_width,
                "current_height": img_original_height,
                "crop_rect": None,
                "layer_order": 0,
                "rotation": 0,
                "is_flipped_h": False,
                "editor_hidden": False,
                "editor_locked": False,
                "properties": ED_CONFIG.get_default_properties_for_asset(ED_CONFIG.CUSTOM_IMAGE_ASSET_KEY)
            }
            editor_history.push_undo_state(editor_state)
            editor_state.placed_objects.append(new_image_obj_data)
            main_win.map_view_widget.draw_placed_objects()
            main_win.handle_map_content_changed()

            if main_win.asset_palette_widget.category_filter_combo.currentText().lower() == "custom":
                main_win.asset_palette_widget.populate_assets()
            main_win.show_status_message(f"Image '{image_filename}' uploaded and added to map.")
        except Exception as e_upload:
            logger.error(f"Error uploading image '{image_filename}': {e_upload}", exc_info=True)
            QMessageBox.critical(main_win, "Upload Error", f"Could not upload image: {e_upload}")
    else:
        main_win.show_status_message("Image upload cancelled.")


def handle_upload_image_for_trigger_dialog(main_win: 'EditorMainWindow', trigger_object_data_ref: Dict[str, Any]):
    editor_state = main_win.editor_state
    logger.info(f"Upload Image for Trigger action triggered for: {id(trigger_object_data_ref)}")
    if not editor_state.map_name_for_function or editor_state.map_name_for_function == "untitled_map":
        QMessageBox.warning(main_win, "Upload Error", "A map must be named and active.")
        return
    map_name = editor_state.map_name_for_function
    custom_folder = editor_map_utils.get_map_specific_folder_path(editor_state, map_name, subfolder="Custom", ensure_exists=True)
    if not custom_folder:
        QMessageBox.critical(main_win, "Upload Error", f"Could not access/create 'Custom' folder for map '{map_name}'.")
        return
    file_path, _ = QFileDialog.getOpenFileName(main_win, "Select Image for Trigger Square", custom_folder, "Images (*.png *.jpg *.jpeg *.gif)")
    if file_path:
        image_filename = os.path.basename(file_path)
        destination_image_path = os.path.join(custom_folder, image_filename)
        try:
            if os.path.normpath(file_path) != os.path.normpath(destination_image_path) :
                if os.path.exists(destination_image_path):
                    reply = QMessageBox.question(main_win, "File Exists", f"Image '{image_filename}' already exists in Custom assets. Overwrite?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
                    if reply == QMessageBox.StandardButton.No:
                        main_win.show_status_message(f"Trigger image '{image_filename}' not overwritten.")
                        return
                shutil.copy2(file_path, destination_image_path)

            relative_path = f"Custom/{image_filename}"
            editor_history.push_undo_state(editor_state)
            trigger_object_data_ref["properties"]["image_in_square"] = relative_path
            main_win.properties_editor_widget.update_property_field_value(trigger_object_data_ref, "image_in_square", relative_path)
            main_win.map_view_widget.update_specific_object_visuals(trigger_object_data_ref)
            main_win.handle_map_content_changed()
            main_win.show_status_message(f"Image '{image_filename}' set for trigger square.")
        except Exception as e_upload_trigger:
            logger.error(f"Error setting image for trigger '{image_filename}': {e_upload_trigger}", exc_info=True)
            QMessageBox.critical(main_win, "Upload Error", f"Could not set image for trigger: {e_upload_trigger}")