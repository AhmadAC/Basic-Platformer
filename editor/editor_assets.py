# editor_assets.py
# -*- coding: utf-8 -*-
"""
## version 2.0.6 (PySide6 Conversion - Prioritize QImageReader for GIFs, Robust Fallbacks)
Handles loading and managing assets for the editor's palette.
Prioritizes QImageReader for getting the first frame of GIFs for palette/cursor.
"""
import os
import sys
import logging
from typing import Optional, Dict, Any, Tuple, List

from PySide6.QtGui import QPixmap, QImage, QPainter, QColor, QMovie, QPen, QImageReader
from PySide6.QtCore import QRectF, QPointF, QSize, Qt
from PySide6.QtWidgets import QApplication # For checking instance

# --- (Sys.path manipulation and resource_path definition as before) ---
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

try:
    from assets import resource_path
    logger = logging.getLogger(__name__) # Get logger after successful import
    if logger.hasHandlers():
         logger.info("EditorAssets: Successfully imported 'resource_path' from 'assets' module.")
    else: # BasicConfig if logger not configured by main editor script yet (e.g. direct testing)
        logging.basicConfig(level=logging.DEBUG)
        logger = logging.getLogger(__name__)
        logger.info("EditorAssets (Fallback Logger): Imported 'resource_path' from 'assets'.")

except ImportError:
    logging.basicConfig(level=logging.DEBUG) # Ensure logger exists even for fallback
    logger = logging.getLogger(__name__)
    logger.warning("EditorAssets: Could not import 'resource_path' from 'assets' module. Using fallback.")
    def resource_path(relative_path_to_join_to_project_root: str) -> str:
        current_script_path = os.path.abspath(__file__)
        current_script_dir = os.path.dirname(current_script_path)
        project_root = os.path.dirname(current_script_dir)
        absolute_path = os.path.join(project_root, relative_path_to_join_to_project_root)
        return absolute_path
# --- End resource_path setup ---

import editor_config as ED_CONFIG
from editor_state import EditorState

# _create_colored_pixmap, _create_half_tile_pixmap, _create_icon_pixmap remain the same
# as in the version 2.0.5 / the one you provided in the file list.
# For brevity, I'll omit them here but ensure they are in your actual file.
def _create_colored_pixmap(width: int, height: int, color_tuple: Tuple[int,int,int]) -> QPixmap:
    pixmap = QPixmap(max(1, width), max(1, height))
    pixmap.fill(QColor(*color_tuple))
    return pixmap

def _create_half_tile_pixmap(base_size: int, half_type: str, color_tuple: Tuple[int,int,int]) -> QPixmap:
    pixmap = QPixmap(base_size, base_size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setBrush(QColor(*color_tuple))
    painter.setPen(Qt.GlobalColor.transparent)
    rect_to_draw = None
    if half_type == "left": rect_to_draw = QRectF(0, 0, base_size / 2.0, float(base_size))
    elif half_type == "right": rect_to_draw = QRectF(base_size / 2.0, 0, base_size / 2.0, float(base_size))
    elif half_type == "top": rect_to_draw = QRectF(0, 0, float(base_size), base_size / 2.0)
    elif half_type == "bottom": rect_to_draw = QRectF(0, base_size / 2.0, float(base_size), base_size / 2.0)
    if rect_to_draw: painter.drawRect(rect_to_draw)
    painter.end(); return pixmap

def _create_icon_pixmap(base_size: int, icon_type: str, color_tuple: Tuple[int,int,int]) -> QPixmap:
    pixmap = QPixmap(base_size, base_size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    if icon_type == "2x2_placer":
        s = float(base_size); rect_size = s * 0.35; gap = s * 0.1
        painter.setBrush(QColor(*color_tuple)); painter.setPen(QColor(Qt.GlobalColor.black))
        painter.drawRect(QRectF(gap, gap, rect_size, rect_size)); painter.drawRect(QRectF(s - gap - rect_size, gap, rect_size, rect_size))
        painter.drawRect(QRectF(gap, s - gap - rect_size, rect_size, rect_size)); painter.drawRect(QRectF(s - gap - rect_size, s - gap - rect_size, rect_size, rect_size))
    elif icon_type == "eraser":
        s = float(base_size); painter.setBrush(QColor(*color_tuple)); painter.setPen(QColor(Qt.GlobalColor.black))
        painter.drawRect(QRectF(s * 0.1, s * 0.3, s * 0.8, s * 0.4))
        pen = QPen(QColor(Qt.GlobalColor.black), 2); pen.setCapStyle(Qt.PenCapStyle.RoundCap); painter.setPen(pen)
        painter.drawLine(QPointF(s*0.25, s*0.25), QPointF(s*0.75, s*0.75)); painter.drawLine(QPointF(s*0.25, s*0.75), QPointF(s*0.75, s*0.25))
    elif icon_type == "color_swatch":
        s = float(base_size); painter.setBrush(QColor(*color_tuple)); painter.setPen(QColor(Qt.GlobalColor.black))
        painter.drawRect(QRectF(s*0.1, s*0.1, s*0.8, s*0.8))
    else:
        painter.setPen(QColor(*color_tuple)); font = painter.font(); font.setPointSize(int(base_size * 0.6)); font.setBold(True)
        painter.setFont(font); painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "?")
    painter.end(); return pixmap


def get_asset_pixmap(asset_editor_key: str,
                     asset_data_entry: Dict[str, Any],
                     target_size: QSize,
                     override_color: Optional[Tuple[int,int,int]] = None) -> Optional[QPixmap]:
    final_pixmap: Optional[QPixmap] = None
    ts = ED_CONFIG.BASE_GRID_SIZE

    color_to_use = override_color
    if not color_to_use and asset_data_entry.get("colorable"):
        color_to_use = asset_data_entry.get("base_color_tuple")
        if not color_to_use:
            surface_params_val = asset_data_entry.get("surface_params")
            if surface_params_val and isinstance(surface_params_val, tuple) and len(surface_params_val) == 3:
                color_to_use = surface_params_val[2]

    source_file_path = asset_data_entry.get("source_file")

    if source_file_path:
        full_path = resource_path(source_file_path)
        full_path = os.path.normpath(full_path)

        if not os.path.exists(full_path):
            logger.error(f"Assets Error (get_asset_pixmap): File NOT FOUND at '{full_path}' for asset '{asset_editor_key}'")
            final_pixmap = _create_colored_pixmap(target_size.width(), target_size.height(), ED_CONFIG.C.RED if hasattr(ED_CONFIG.C, 'RED') else (255,0,0))
        else:
            # --- Use QImageReader as primary for all files in get_asset_pixmap ---
            reader = QImageReader(full_path)
            # For GIFs, QImageReader usually reads the first frame.
            # For other formats, it reads the static image.
            # Explicitly set format for GIF to help reader, though usually auto-detected
            if source_file_path.lower().endswith(".gif"):
                reader.setFormat(b"gif")
            
            if reader.canRead():
                image_from_reader = reader.read() # Returns QImage
                if not image_from_reader.isNull():
                    final_pixmap = QPixmap.fromImage(image_from_reader)
                    if final_pixmap.isNull(): # Should not happen if QImage was valid
                        logger.error(f"Assets Error (get_asset_pixmap): QPixmap.fromImage failed for '{full_path}' (asset '{asset_editor_key}'). Reader error: {reader.errorString()}")
                        final_pixmap = None
                    # else: logger.debug(f"Assets (get_asset_pixmap): Successfully loaded '{full_path}' using QImageReader -> QPixmap for '{asset_editor_key}'.")
                else:
                    logger.error(f"Assets Error (get_asset_pixmap): QImageReader.read() failed for '{full_path}' (asset '{asset_editor_key}'). Reader error: {reader.error()}, String: {reader.errorString()}")
                    final_pixmap = None
            else: # reader.canRead() is false
                logger.error(f"Assets Error (get_asset_pixmap): QImageReader CANNOT READ file '{full_path}' (asset '{asset_editor_key}'). Reader error: {reader.error()}, String: {reader.errorString()}")
                # As a last resort for GIF, try QMovie if QImageReader failed entirely
                if source_file_path.lower().endswith(".gif"):
                    logger.debug(f"Assets (get_asset_pixmap): QImageReader failed for GIF '{asset_editor_key}', trying QMovie as final fallback.")
                    movie = QMovie(full_path)
                    if movie.isValid() and movie.frameCount() > 0:
                        final_pixmap = movie.currentPixmap()
                        if final_pixmap.isNull():
                             logger.error(f"Assets (get_asset_pixmap): QMovie fallback also resulted in null pixmap for GIF '{asset_editor_key}'. Movie Error: {movie.errorString()}")
                             final_pixmap = None
                    else:
                        logger.error(f"Assets (get_asset_pixmap): QMovie fallback also failed for GIF '{asset_editor_key}'. Movie valid: {movie.isValid()}, frames: {movie.frameCount()}, Error: {movie.errorString()}")
                        final_pixmap = None

            # Colorization logic (remains the same)
            if final_pixmap and not final_pixmap.isNull() and color_to_use and asset_data_entry.get("colorable"):
                try:
                    temp_image = final_pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
                    painter = QPainter(temp_image)
                    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                    painter.fillRect(temp_image.rect(), QColor(*color_to_use))
                    painter.end()
                    final_pixmap = QPixmap.fromImage(temp_image)
                except Exception as e_colorize:
                    logger.error(f"Error colorizing pixmap for '{asset_editor_key}' in get_asset_pixmap: {e_colorize}", exc_info=True)
    
    # Procedural generation logic (remains the same)
    elif "surface_params" in asset_data_entry and \
         asset_data_entry.get("render_mode") is None and \
         asset_data_entry.get("icon_type") is None:
        # ... (same as your last version)
        params = asset_data_entry["surface_params"]
        if params and isinstance(params, tuple) and len(params) == 3:
            w, h, default_color = params
            final_pixmap = _create_colored_pixmap(w, h, color_to_use or default_color)
        else:
            logger.warning(f"Malformed 'surface_params' for procedural tile '{asset_editor_key}'. Expected (w,h,color), got {params}")
    elif "render_mode" in asset_data_entry and asset_data_entry["render_mode"] == "half_tile":
        half_type = asset_data_entry.get("half_type", "left")
        default_color = asset_data_entry.get("base_color_tuple", ED_CONFIG.C.MAGENTA if hasattr(ED_CONFIG.C, 'MAGENTA') else (255,0,255))
        final_pixmap = _create_half_tile_pixmap(ts, half_type, color_to_use or default_color)
    elif "icon_type" in asset_data_entry:
        icon_type = asset_data_entry["icon_type"]
        default_color = asset_data_entry.get("base_color_tuple", ED_CONFIG.C.YELLOW if hasattr(ED_CONFIG.C, 'YELLOW') else (255,255,0))
        final_pixmap = _create_icon_pixmap(ts, icon_type, color_to_use or default_color)


    if not final_pixmap or final_pixmap.isNull():
        logger.warning(f"Could not generate pixmap for '{asset_editor_key}' (final_pixmap is null/None) in get_asset_pixmap. Creating fallback.")
        final_pixmap = _create_colored_pixmap(target_size.width(), target_size.height(), ED_CONFIG.C.RED if hasattr(ED_CONFIG.C, 'RED') else (255,0,0))
        painter = QPainter(final_pixmap)
        painter.setPen(QColor(Qt.GlobalColor.black))
        painter.drawLine(0,0, final_pixmap.width(), final_pixmap.height())
        painter.drawLine(0,final_pixmap.height(), final_pixmap.width(), 0)
        painter.end()

    if final_pixmap and not final_pixmap.isNull() and (final_pixmap.size() != target_size):
        final_pixmap = final_pixmap.scaled(target_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)

    return final_pixmap


def load_editor_palette_assets(editor_state: EditorState, main_window_ref: Optional[Any] = None):
    editor_state.assets_palette.clear()
    if QApplication.instance() is None: # Ensure QApplication exists before any QPixmap/QMovie
        logger.critical("CRITICAL: QApplication not instantiated before load_editor_palette_assets!")
        # This is a fatal issue for Qt graphics.
        # Depending on structure, might need to raise an error or handle differently.
        # For now, just log and proceed, asset loading will likely fail.
    logger.info("Loading editor palette assets for Qt...")
    successful_loads = 0
    failed_loads = 0
    target_thumb_size = QSize(ED_CONFIG.ASSET_THUMBNAIL_SIZE, ED_CONFIG.ASSET_THUMBNAIL_SIZE)
    ts = ED_CONFIG.BASE_GRID_SIZE

    fallback_red = ED_CONFIG.C.RED if hasattr(ED_CONFIG.C, 'RED') else (255,0,0)
    fallback_magenta = ED_CONFIG.C.MAGENTA if hasattr(ED_CONFIG.C, 'MAGENTA') else (255,0,255)
    fallback_yellow = ED_CONFIG.C.YELLOW if hasattr(ED_CONFIG.C, 'YELLOW') else (255,255,0)
    fallback_blue = ED_CONFIG.C.BLUE if hasattr(ED_CONFIG.C, 'BLUE') else (0,0,255)

    for asset_key, asset_info_def in ED_CONFIG.EDITOR_PALETTE_ASSETS.items():
        asset_data_entry: Dict[str, Any] = {
            "game_type_id": asset_info_def.get("game_type_id", asset_key),
            "category": asset_info_def.get("category", "unknown"),
            "original_size_pixels": (ts, ts), # Default, updated if loaded from file
            "places_asset_key": asset_info_def.get("places_asset_key"),
            "colorable": asset_info_def.get("colorable", False),
            "render_mode": asset_info_def.get("render_mode"),
            "half_type": asset_info_def.get("half_type"),
            "base_color_tuple": asset_info_def.get("base_color_tuple"),
            "surface_params": asset_info_def.get("surface_params"),
            "name_in_palette": asset_info_def.get("name_in_palette", asset_key.replace("_", " ").title()),
            "source_file": asset_info_def.get("source_file"),
            "icon_type": asset_info_def.get("icon_type")
        }

        pixmap_for_palette: Optional[QPixmap] = None
        intended_pixmap_created_successfully = False
        original_w, original_h = ts, ts
        source_file_path = asset_info_def.get("source_file")

        if source_file_path:
            try:
                full_path = resource_path(source_file_path)
                full_path = os.path.normpath(full_path)
                logger.debug(f"Attempting to load asset '{asset_key}' from normalized path: '{full_path}'")

                if not os.path.exists(full_path):
                    logger.error(f"Assets Error: File NOT FOUND at '{full_path}' for asset '{asset_key}'")
                else:
                    logger.debug(f"File exists: '{full_path}'. Attempting Qt load...")
                    temp_pixmap: Optional[QPixmap] = None
                    
                    # --- Primary attempt using QImageReader for all file types ---
                    reader = QImageReader(full_path)
                    # For GIFs, QImageReader typically reads the first frame.
                    # For other formats like PNG, it reads the static image.
                    if source_file_path.lower().endswith(".gif"):
                        reader.setFormat(b"gif") # Hint for GIF reader

                    if reader.canRead():
                        image_from_reader = reader.read() # QImage
                        if not image_from_reader.isNull():
                            temp_pixmap = QPixmap.fromImage(image_from_reader)
                            if temp_pixmap.isNull():
                                logger.error(f"QPixmap.fromImage failed for '{full_path}' (asset '{asset_key}'). Reader error: {reader.errorString()}")
                                temp_pixmap = None
                            # else: logger.debug(f"Successfully loaded '{full_path}' using QImageReader -> QPixmap for '{asset_key}'.")
                        else:
                            logger.error(f"QImageReader.read() failed for '{full_path}' (asset '{asset_key}'). Reader error: {reader.error()}, String: {reader.errorString()}")
                    else: # reader.canRead() is false
                        logger.error(f"QImageReader CANNOT READ file '{full_path}' (asset '{asset_key}'). Reader error: {reader.error()}, String: {reader.errorString()}")
                        # If QImageReader fails for GIF, try QMovie as a last resort (might handle complex animations better if needed later)
                        if source_file_path.lower().endswith(".gif"):
                            logger.debug(f"QImageReader failed for GIF '{asset_key}', trying QMovie as final fallback.")
                            movie = QMovie(full_path)
                            if movie.isValid() and movie.frameCount() > 0:
                                temp_pixmap = movie.currentPixmap()
                                if temp_pixmap.isNull():
                                     logger.error(f"QMovie fallback for '{full_path}' -> currentPixmap IS NULL. Movie Error: {movie.errorString()}")
                                     temp_pixmap = None
                            else: # QMovie failed
                                logger.error(f"QMovie fallback also failed for GIF '{asset_key}'. Movie valid: {movie.isValid()}, frames: {movie.frameCount()}, Error: {movie.errorString()}")

                    if temp_pixmap and not temp_pixmap.isNull():
                        original_w, original_h = temp_pixmap.width(), temp_pixmap.height()
                        pixmap_for_palette = temp_pixmap # Will be scaled to target_thumb_size later
                        intended_pixmap_created_successfully = True
                    else:
                        logger.error(f"All Qt loading attempts failed for file-based asset '{asset_key}' from '{full_path}'")
            except Exception as e:
                logger.error(f"Exception during source_file processing for '{asset_key}': {e}", exc_info=True)
        
        # Procedural generation if not from file or file loading failed
        if not intended_pixmap_created_successfully:
            if "surface_params" in asset_info_def and asset_info_def["surface_params"] is not None:
                # ... (same procedural logic as before)
                params = asset_info_def["surface_params"]
                if params and isinstance(params, tuple) and len(params) == 3:
                    w, h, color = params; original_w, original_h = w, h
                    pixmap_for_palette = _create_colored_pixmap(w, h, color)
                    intended_pixmap_created_successfully = True
                else: logger.warning(f"Malformed 'surface_params' for '{asset_key}': {params}")
            elif "render_mode" in asset_info_def and asset_info_def["render_mode"] == "half_tile":
                half_type = asset_info_def.get("half_type", "left")
                color = asset_info_def.get("base_color_tuple", fallback_magenta)
                original_w, original_h = ts, ts
                pixmap_for_palette = _create_half_tile_pixmap(ts, half_type, color)
                intended_pixmap_created_successfully = True
            elif "icon_type" in asset_info_def:
                icon_type = asset_info_def["icon_type"]
                color = asset_info_def.get("base_color_tuple", fallback_yellow)
                original_w, original_h = ts, ts
                pixmap_for_palette = _create_icon_pixmap(ts, icon_type, color)
                intended_pixmap_created_successfully = True

        asset_data_entry["original_size_pixels"] = (original_w, original_h)

        if not intended_pixmap_created_successfully or not pixmap_for_palette or pixmap_for_palette.isNull():
            if source_file_path: logger.error(f"Creating fallback palette icon for '{asset_key}'.")
            pixmap_for_palette = _create_colored_pixmap(target_thumb_size.width(), target_thumb_size.height(), fallback_red)
            painter = QPainter(pixmap_for_palette); painter.setPen(QColor(Qt.GlobalColor.black))
            painter.drawLine(0,0, pixmap_for_palette.width(), pixmap_for_palette.height())
            painter.drawLine(0,pixmap_for_palette.height(), pixmap_for_palette.width(), 0); painter.end()

        if pixmap_for_palette and not pixmap_for_palette.isNull() and pixmap_for_palette.size() != target_thumb_size:
             pixmap_for_palette = pixmap_for_palette.scaled(target_thumb_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)

        # --- Cursor Pixmap Creation ---
        # get_asset_pixmap itself now uses QImageReader primarily.
        cursor_base_pixmap = get_asset_pixmap(asset_key, asset_data_entry, QSize(original_w, original_h))
        pixmap_for_cursor: Optional[QPixmap] = None
        if cursor_base_pixmap and not cursor_base_pixmap.isNull():
            try:
                img_for_cursor_alpha = cursor_base_pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
                cursor_image_with_alpha = QImage(img_for_cursor_alpha.size(), QImage.Format.Format_ARGB32_Premultiplied)
                cursor_image_with_alpha.fill(Qt.GlobalColor.transparent)
                painter = QPainter(cursor_image_with_alpha)
                painter.setOpacity(ED_CONFIG.CURSOR_ASSET_ALPHA / 255.0)
                painter.drawImage(0, 0, img_for_cursor_alpha)
                painter.end()
                pixmap_for_cursor = QPixmap.fromImage(cursor_image_with_alpha)
            except Exception as e_cursor_alpha:
                logger.error(f"Error applying alpha to cursor for '{asset_key}': {e_cursor_alpha}", exc_info=True)
                pixmap_for_cursor = _create_colored_pixmap(original_w, original_h, fallback_blue)
        else:
            logger.warning(f"Base pixmap for cursor of '{asset_key}' was null. Using fallback cursor.")
            pixmap_for_cursor = _create_colored_pixmap(original_w, original_h, fallback_blue)

        asset_data_entry["q_pixmap"] = pixmap_for_palette
        asset_data_entry["q_pixmap_cursor"] = pixmap_for_cursor
        editor_state.assets_palette[asset_key] = asset_data_entry

        if intended_pixmap_created_successfully and pixmap_for_palette and not pixmap_for_palette.isNull():
            successful_loads += 1
        else:
            failed_loads += 1

    logger.info(f"Palette asset loading complete. Successfully processed intended assets: {successful_loads}, Assets requiring fallbacks or failed: {failed_loads}.")