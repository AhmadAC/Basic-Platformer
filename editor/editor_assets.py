#################### START OF FILE: editor\editor_assets.py ####################

# editor_assets.py
# -*- coding: utf-8 -*-
"""
## version 2.0.1 (PySide6 Refactor - QPixmap/QImage, QImageReader focus)
Handles loading and managing assets for the editor's palette using PySide6.
Prioritizes QImageReader for GIFs for palette/cursor first frame.
"""
import os
import sys
import logging
from typing import Optional, Dict, Any, Tuple, List

from PySide6.QtGui import QPixmap, QImage, QPainter, QColor, QPen, QImageReader # QMovie removed as QImageReader is preferred
from PySide6.QtCore import QRectF, QPointF, QSize, Qt
from PySide6.QtWidgets import QApplication # For checking instance

# --- Sys.path manipulation to find project root for 'assets' and 'editor_config' ---
current_dir = os.path.dirname(os.path.abspath(__file__)) # editor directory
parent_dir = os.path.dirname(current_dir) # project root
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

logger = logging.getLogger(__name__) # Get logger (should be configured by editor.py)

try:
    # Import resource_path from the refactored assets.py in the project root
    from assets import resource_path
    if logger.hasHandlers(): logger.info("EditorAssets: Successfully imported 'resource_path' from root 'assets' module.")
    else: # BasicConfig if logger not configured (e.g. direct testing of this file)
        logging.basicConfig(level=logging.DEBUG, format='FallbackLogger - %(levelname)s - %(message)s')
        logger.info("EditorAssets (Fallback Logger): Imported 'resource_path' from root 'assets'.")
except ImportError:
    if not logger.hasHandlers(): logging.basicConfig(level=logging.DEBUG, format='FallbackLogger - %(levelname)s - %(message)s')
    logger.warning("EditorAssets: Could not import 'resource_path' from root 'assets'. Using fallback.")
    # Fallback resource_path (relative to this file's assumed project structure)
    def resource_path(relative_path_to_join_to_project_root: str) -> str:
        return os.path.join(parent_dir, relative_path_to_join_to_project_root)
# --- End resource_path setup ---

import editor_config as ED_CONFIG # From the editor package (already refactored)
from editor_state import EditorState # From the editor package

# --- Helper functions for creating procedural QPixmaps ---

def _create_colored_pixmap(width: int, height: int, color_tuple: Tuple[int,int,int]) -> QPixmap:
    pixmap = QPixmap(max(1, width), max(1, height)) # Ensure positive dimensions
    pixmap.fill(QColor(*color_tuple))
    return pixmap

def _create_half_tile_pixmap(base_size: int, half_type: str, color_tuple: Tuple[int,int,int]) -> QPixmap:
    pixmap = QPixmap(base_size, base_size)
    pixmap.fill(Qt.GlobalColor.transparent) # Start with transparent background
    painter = QPainter(pixmap)
    painter.setBrush(QColor(*color_tuple))
    painter.setPen(Qt.GlobalColor.transparent) # No border for the half-tile itself
    
    rect_to_draw = QRectF()
    if half_type == "left": rect_to_draw = QRectF(0, 0, base_size / 2.0, float(base_size))
    elif half_type == "right": rect_to_draw = QRectF(base_size / 2.0, 0, base_size / 2.0, float(base_size))
    elif half_type == "top": rect_to_draw = QRectF(0, 0, float(base_size), base_size / 2.0)
    elif half_type == "bottom": rect_to_draw = QRectF(0, base_size / 2.0, float(base_size), base_size / 2.0)
    
    if not rect_to_draw.isNull():
        painter.drawRect(rect_to_draw)
    painter.end()
    return pixmap

def _create_icon_pixmap(base_size: int, icon_type: str, color_tuple: Tuple[int,int,int]) -> QPixmap:
    pixmap = QPixmap(base_size, base_size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    
    s = float(base_size)
    icon_qcolor = QColor(*color_tuple)
    border_qcolor = QColor(Qt.GlobalColor.black)

    if icon_type == "2x2_placer":
        rect_size = s * 0.35; gap = s * 0.1
        painter.setBrush(icon_qcolor); painter.setPen(border_qcolor)
        painter.drawRect(QRectF(gap, gap, rect_size, rect_size))
        painter.drawRect(QRectF(s - gap - rect_size, gap, rect_size, rect_size))
        painter.drawRect(QRectF(gap, s - gap - rect_size, rect_size, rect_size))
        painter.drawRect(QRectF(s - gap - rect_size, s - gap - rect_size, rect_size, rect_size))
    elif icon_type == "eraser":
        painter.setBrush(icon_qcolor); painter.setPen(border_qcolor)
        painter.drawRect(QRectF(s * 0.1, s * 0.3, s * 0.8, s * 0.4)) # Eraser body
        pen = QPen(border_qcolor, 2); pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawLine(QPointF(s*0.25, s*0.25), QPointF(s*0.75, s*0.75)) # Cross
        painter.drawLine(QPointF(s*0.25, s*0.75), QPointF(s*0.75, s*0.25))
    elif icon_type == "color_swatch":
        painter.setBrush(icon_qcolor); painter.setPen(border_qcolor)
        painter.drawRect(QRectF(s*0.1, s*0.1, s*0.8, s*0.8)) # Simple colored square
    else: # Fallback '?' icon
        painter.setPen(icon_qcolor)
        font = painter.font(); font.setPointSize(int(s * 0.6)); font.setBold(True)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "?")
    
    painter.end()
    return pixmap

def get_asset_pixmap(asset_editor_key: str,
                     asset_data_entry: Dict[str, Any],
                     target_size: QSize,
                     override_color: Optional[Tuple[int,int,int]] = None) -> Optional[QPixmap]:
    """
    Loads or generates a QPixmap for an asset, suitable for palette or cursor.
    Prioritizes QImageReader for file-based assets (first frame for GIFs).
    Handles colorization and procedural generation.
    """
    final_pixmap: Optional[QPixmap] = None
    ts = ED_CONFIG.BASE_GRID_SIZE # Tile Size from editor_config

    # Determine color to use (override or default from asset definition)
    color_to_use_tuple = override_color
    if not color_to_use_tuple and asset_data_entry.get("colorable"):
        color_to_use_tuple = asset_data_entry.get("base_color_tuple")
        if not color_to_use_tuple:
            surface_params_val = asset_data_entry.get("surface_params")
            if surface_params_val and isinstance(surface_params_val, tuple) and len(surface_params_val) == 3:
                color_to_use_tuple = surface_params_val[2] # (w,h,color)

    source_file_path_rel = asset_data_entry.get("source_file")

    if source_file_path_rel:
        full_path_abs = resource_path(source_file_path_rel) # Resolve path
        full_path_norm = os.path.normpath(full_path_abs)

        if not os.path.exists(full_path_norm):
            logger.error(f"Assets Error (get_asset_pixmap): File NOT FOUND at '{full_path_norm}' for asset '{asset_editor_key}'")
        else:
            reader = QImageReader(full_path_norm)
            # For GIFs, QImageReader.read() usually gets the first frame.
            # For PNGs, JPEGs, etc., it reads the static image.
            if source_file_path_rel.lower().endswith(".gif"):
                reader.setFormat(b"gif") # Hint for GIF reader, usually auto-detected

            if reader.canRead():
                image_from_reader: QImage = reader.read()
                if not image_from_reader.isNull():
                    final_pixmap = QPixmap.fromImage(image_from_reader)
                    if final_pixmap.isNull():
                        logger.error(f"Assets Error (get_asset_pixmap): QPixmap.fromImage failed for '{full_path_norm}' (asset '{asset_editor_key}'). Reader error: {reader.errorString()}")
                else:
                    logger.error(f"Assets Error (get_asset_pixmap): QImageReader.read() returned null QImage for '{full_path_norm}' (asset '{asset_editor_key}'). Reader error: {reader.error()}, String: {reader.errorString()}")
            else:
                logger.error(f"Assets Error (get_asset_pixmap): QImageReader CANNOT READ file '{full_path_norm}' (asset '{asset_editor_key}'). Reader error: {reader.error()}, String: {reader.errorString()}")
            
            # Colorization logic (if pixmap loaded and colorable)
            if final_pixmap and not final_pixmap.isNull() and color_to_use_tuple and asset_data_entry.get("colorable"):
                try:
                    # Create a temporary QImage for direct pixel manipulation for tinting
                    # Ensure it has an alpha channel for proper tinting
                    temp_image = final_pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
                    painter = QPainter(temp_image)
                    # Use CompositionMode_SourceIn to apply color only to non-transparent parts
                    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                    painter.fillRect(temp_image.rect(), QColor(*color_to_use_tuple))
                    painter.end()
                    final_pixmap = QPixmap.fromImage(temp_image) # Convert back to QPixmap
                except Exception as e_colorize:
                    logger.error(f"Error colorizing pixmap for '{asset_editor_key}' in get_asset_pixmap: {e_colorize}", exc_info=True)
    
    # Procedural generation if no file or file loading failed
    elif "surface_params" in asset_data_entry and \
         asset_data_entry.get("render_mode") is None and \
         asset_data_entry.get("icon_type") is None:
        params = asset_data_entry["surface_params"]
        if params and isinstance(params, tuple) and len(params) == 3:
            w, h, default_color_tuple = params
            final_pixmap = _create_colored_pixmap(w, h, color_to_use_tuple or default_color_tuple)
        else:
            logger.warning(f"Malformed 'surface_params' for procedural tile '{asset_editor_key}'. Expected (w,h,color), got {params}")
    elif "render_mode" in asset_data_entry and asset_data_entry["render_mode"] == "half_tile":
        half_type = asset_data_entry.get("half_type", "left")
        default_color_proc = asset_data_entry.get("base_color_tuple", getattr(ED_CONFIG.C, 'MAGENTA', (255,0,255)))
        final_pixmap = _create_half_tile_pixmap(ts, half_type, color_to_use_tuple or default_color_proc)
    elif "icon_type" in asset_data_entry:
        icon_type_str = asset_data_entry["icon_type"]
        default_color_icon = asset_data_entry.get("base_color_tuple", getattr(ED_CONFIG.C, 'YELLOW', (255,255,0)))
        final_pixmap = _create_icon_pixmap(ts, icon_type_str, color_to_use_tuple or default_color_icon)

    # Fallback if no pixmap could be generated/loaded
    if not final_pixmap or final_pixmap.isNull():
        logger.warning(f"Could not generate/load pixmap for '{asset_editor_key}'. Creating RED fallback.")
        final_pixmap = QPixmap(target_size)
        final_pixmap.fill(QColor(*getattr(ED_CONFIG.C, 'RED', (255,0,0))))
        painter = QPainter(final_pixmap)
        painter.setPen(QColor(Qt.GlobalColor.black))
        painter.drawLine(0,0, final_pixmap.width(), final_pixmap.height())
        painter.drawLine(0,final_pixmap.height(), final_pixmap.width(), 0)
        painter.end()

    # Scale to target size if needed (e.g., for palette thumbnails)
    if final_pixmap and not final_pixmap.isNull() and (final_pixmap.size() != target_size):
        final_pixmap = final_pixmap.scaled(target_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)

    return final_pixmap


def load_editor_palette_assets(editor_state: EditorState, main_window_ref: Optional[Any] = None):
    editor_state.assets_palette.clear()
    if QApplication.instance() is None:
        logger.critical("CRITICAL: QApplication not instantiated before load_editor_palette_assets! Asset loading will likely fail.")
        # This is a fatal issue for Qt graphics operations.
        # The main editor should ensure QApplication exists.
    
    logger.info("Loading editor palette assets for Qt...")
    successful_loads = 0; failed_loads = 0
    target_thumb_size = QSize(ED_CONFIG.ASSET_THUMBNAIL_SIZE, ED_CONFIG.ASSET_THUMBNAIL_SIZE)
    ts = ED_CONFIG.BASE_GRID_SIZE # Tile Size

    # Define fallback QColors directly for convenience
    fallback_qcolor_red = QColor(*getattr(ED_CONFIG.C, 'RED', (255,0,0)))
    fallback_qcolor_magenta = QColor(*getattr(ED_CONFIG.C, 'MAGENTA', (255,0,255)))
    fallback_qcolor_yellow = QColor(*getattr(ED_CONFIG.C, 'YELLOW', (255,255,0)))
    fallback_qcolor_blue = QColor(*getattr(ED_CONFIG.C, 'BLUE', (0,0,255)))

    for asset_key, asset_info_def in ED_CONFIG.EDITOR_PALETTE_ASSETS.items():
        asset_data_entry: Dict[str, Any] = {
            "game_type_id": asset_info_def.get("game_type_id", asset_key),
            "category": asset_info_def.get("category", "unknown"),
            "original_size_pixels": (ts, ts), # Default, updated if loaded from file
            "places_asset_key": asset_info_def.get("places_asset_key"),
            "colorable": asset_info_def.get("colorable", False),
            "render_mode": asset_info_def.get("render_mode"),
            "half_type": asset_info_def.get("half_type"),
            "base_color_tuple": asset_info_def.get("base_color_tuple"), # Stored as tuple
            "surface_params": asset_info_def.get("surface_params"),
            "name_in_palette": asset_info_def.get("name_in_palette", asset_key.replace("_", " ").title()),
            "source_file": asset_info_def.get("source_file"),
            "icon_type": asset_info_def.get("icon_type")
        }

        pixmap_for_palette: Optional[QPixmap] = None
        intended_pixmap_created_successfully = False
        original_w, original_h = ts, ts # Default original size
        source_file_path_rel = asset_info_def.get("source_file")

        if source_file_path_rel:
            # Use get_asset_pixmap which now robustly handles file loading for palette thumbnails
            # No override_color needed for the base palette icon itself.
            pixmap_for_palette = get_asset_pixmap(asset_key, asset_data_entry, target_thumb_size)
            if pixmap_for_palette and not pixmap_for_palette.isNull():
                 # Check if it's not the generic RED fallback from get_asset_pixmap
                is_fallback_red = (pixmap_for_palette.size() == target_thumb_size and
                                   pixmap_for_palette.toImage().pixelColor(0,0) == fallback_qcolor_red)
                if not is_fallback_red:
                    intended_pixmap_created_successfully = True
                    # Determine original size from the loaded file asset if possible
                    # We need a way to get original dimensions from get_asset_pixmap or load once unscaled
                    # For now, let's assume source_file implies a defined size or we use default.
                    # This part might need refinement if original_size_pixels needs to be very accurate
                    # for all file types *before* scaling to thumbnail.
                    # A temporary load of the full image might be needed here just for size.
                    temp_full_pixmap = get_asset_pixmap(asset_key, asset_data_entry, QSize(1000,1000)) # Load large to get original aspect
                    if temp_full_pixmap and not temp_full_pixmap.isNull():
                        original_w, original_h = temp_full_pixmap.width(), temp_full_pixmap.height()
        
        # Procedural generation if not from file or file loading failed
        if not intended_pixmap_created_successfully:
            # Use get_asset_pixmap for procedural ones too, ensuring consistency
            # Pass a large target_size initially to get its "original" procedural size, then scale
            temp_procedural_pixmap = get_asset_pixmap(asset_key, asset_data_entry, QSize(ts*2, ts*2)) # Larger temp
            if temp_procedural_pixmap and not temp_procedural_pixmap.isNull():
                original_w, original_h = temp_procedural_pixmap.width(), temp_procedural_pixmap.height()
                pixmap_for_palette = temp_procedural_pixmap.scaled(target_thumb_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                is_fallback_red = (pixmap_for_palette.size() == target_thumb_size and
                                   pixmap_for_palette.toImage().pixelColor(0,0) == fallback_qcolor_red)
                if not is_fallback_red:
                    intended_pixmap_created_successfully = True


        asset_data_entry["original_size_pixels"] = (original_w, original_h)

        if not pixmap_for_palette or pixmap_for_palette.isNull(): # Absolute fallback if all else fails
            if source_file_path_rel: logger.error(f"Creating FINAL fallback palette icon for '{asset_key}'.")
            pixmap_for_palette = QPixmap(target_thumb_size)
            pixmap_for_palette.fill(fallback_qcolor_red) # Red error placeholder
            painter = QPainter(pixmap_for_palette); painter.setPen(QColor(Qt.GlobalColor.black))
            painter.drawLine(0,0, pixmap_for_palette.width(), pixmap_for_palette.height())
            painter.drawLine(0,pixmap_for_palette.height(), pixmap_for_palette.width(), 0); painter.end()

        # --- Cursor Pixmap Creation ---
        # Get the asset at its original size for the cursor, then apply alpha.
        cursor_base_pixmap = get_asset_pixmap(asset_key, asset_data_entry, QSize(original_w, original_h))
        pixmap_for_cursor: Optional[QPixmap] = None
        if cursor_base_pixmap and not cursor_base_pixmap.isNull():
            try:
                img_for_cursor_alpha = cursor_base_pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
                cursor_image_with_alpha = QImage(img_for_cursor_alpha.size(), QImage.Format.Format_ARGB32_Premultiplied)
                cursor_image_with_alpha.fill(Qt.GlobalColor.transparent) # Start with transparent
                painter = QPainter(cursor_image_with_alpha)
                painter.setOpacity(ED_CONFIG.CURSOR_ASSET_ALPHA / 255.0) # Apply alpha
                painter.drawImage(0, 0, img_for_cursor_alpha) # Draw the base image with opacity
                painter.end()
                pixmap_for_cursor = QPixmap.fromImage(cursor_image_with_alpha)
            except Exception as e_cursor_alpha:
                logger.error(f"Error applying alpha to cursor for '{asset_key}': {e_cursor_alpha}", exc_info=True)
                # Fallback cursor pixmap
                pixmap_for_cursor = QPixmap(original_w, original_h); pixmap_for_cursor.fill(fallback_qcolor_blue)
        else:
            logger.warning(f"Base pixmap for cursor of '{asset_key}' was null. Using fallback BLUE cursor.")
            pixmap_for_cursor = QPixmap(original_w, original_h); pixmap_for_cursor.fill(fallback_qcolor_blue)


        asset_data_entry["q_pixmap"] = pixmap_for_palette # For palette display
        asset_data_entry["q_pixmap_cursor"] = pixmap_for_cursor # For map view cursor
        editor_state.assets_palette[asset_key] = asset_data_entry

        if intended_pixmap_created_successfully: successful_loads += 1
        else: failed_loads += 1

    logger.info(f"Palette asset loading complete. Successfully processed intended assets: {successful_loads}, Assets requiring fallbacks or failed: {failed_loads}.")

#################### END OF FILE: editor\editor_assets.py ####################