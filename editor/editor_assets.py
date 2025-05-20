# editor/editor_assets.py
# -*- coding: utf-8 -*-
"""
## version 2.0.2 (PySide6 - Corrected asset scaling for map view)
Handles loading and managing assets for the editor's palette using PySide6.
Prioritizes QImageReader for GIFs for palette/cursor first frame.
Ensures map objects are drawn at their native (original) size.
"""
import os
import sys
import logging
from typing import Optional, Dict, Any, Tuple, List

from PySide6.QtGui import QPixmap, QImage, QPainter, QColor, QPen, QImageReader
from PySide6.QtCore import QRectF, QPointF, QSize, Qt
from PySide6.QtWidgets import QApplication

# --- Sys.path manipulation ---
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

logger = logging.getLogger(__name__)

try:
    from assets import resource_path
    if logger.hasHandlers() and logger.isEnabledFor(logging.INFO): # Check if logger is configured
        logger.info("EditorAssets: Imported 'resource_path' from root 'assets'.")
    elif not logger.hasHandlers(): # Basic config if no handlers exist yet
        logging.basicConfig(level=logging.DEBUG, format='FallbackLogger - %(levelname)s - %(message)s')
        logger = logging.getLogger(__name__) # Re-get logger after basicConfig
        logger.info("EditorAssets (Fallback Logger Active): Imported 'resource_path' from root 'assets'.")
except ImportError:
    if not logger.hasHandlers(): 
        logging.basicConfig(level=logging.DEBUG, format='FallbackLogger - %(levelname)s - %(message)s')
        logger = logging.getLogger(__name__)
    logger.warning("EditorAssets: Could not import 'resource_path' from root 'assets'. Using fallback.")
    def resource_path(relative_path: str) -> str: return os.path.join(parent_dir, relative_path)

from . import editor_config as ED_CONFIG # Use relative import
from .editor_state import EditorState # Use relative import

# --- Helper functions for creating procedural QPixmaps ---
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
    rect_to_draw = QRectF()
    if half_type == "left": rect_to_draw = QRectF(0, 0, base_size / 2.0, float(base_size))
    elif half_type == "right": rect_to_draw = QRectF(base_size / 2.0, 0, base_size / 2.0, float(base_size))
    elif half_type == "top": rect_to_draw = QRectF(0, 0, float(base_size), base_size / 2.0)
    elif half_type == "bottom": rect_to_draw = QRectF(0, base_size / 2.0, float(base_size), base_size / 2.0)
    if not rect_to_draw.isNull(): painter.drawRect(rect_to_draw)
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
        painter.drawRect(QRectF(s * 0.1, s * 0.3, s * 0.8, s * 0.4))
        pen = QPen(border_qcolor, 2); pen.setCapStyle(Qt.PenCapStyle.RoundCap); painter.setPen(pen)
        painter.drawLine(QPointF(s*0.25, s*0.25), QPointF(s*0.75, s*0.75))
        painter.drawLine(QPointF(s*0.25, s*0.75), QPointF(s*0.75, s*0.25))
    elif icon_type == "color_swatch":
        painter.setBrush(icon_qcolor); painter.setPen(border_qcolor)
        painter.drawRect(QRectF(s*0.1, s*0.1, s*0.8, s*0.8))
    else:
        painter.setPen(icon_qcolor)
        font = painter.font(); font.setPointSize(int(s * 0.6)); font.setBold(True); painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "?")
    painter.end()
    return pixmap


def get_asset_pixmap(asset_editor_key: str,
                     asset_data_entry: Dict[str, Any],
                     requested_target_size: QSize, # The size the CALLER wants the pixmap to be
                     override_color: Optional[Tuple[int,int,int]] = None,
                     get_native_size_only: bool = False) -> Optional[QPixmap]:
    """
    Loads or generates a QPixmap for an asset.
    - If get_native_size_only is True, it returns the pixmap at its natural loaded/generated size,
      ignoring requested_target_size for scaling.
    - Otherwise, it returns the pixmap scaled to requested_target_size.
    """
    native_pixmap: Optional[QPixmap] = None
    ts = ED_CONFIG.BASE_GRID_SIZE

    color_to_use_tuple = override_color
    if not color_to_use_tuple and asset_data_entry.get("colorable"):
        color_to_use_tuple = asset_data_entry.get("base_color_tuple")
        if not color_to_use_tuple:
            surface_params_val = asset_data_entry.get("surface_params")
            if surface_params_val and isinstance(surface_params_val, tuple) and len(surface_params_val) == 3:
                color_to_use_tuple = surface_params_val[2]

    source_file_path_rel = asset_data_entry.get("source_file")

    if source_file_path_rel:
        full_path_abs = resource_path(source_file_path_rel)
        full_path_norm = os.path.normpath(full_path_abs)
        logger.debug(f"get_asset_pixmap: Attempting to load '{asset_editor_key}' from '{full_path_norm}'")
        if not os.path.exists(full_path_norm):
            logger.error(f"File NOT FOUND: '{full_path_norm}' for asset '{asset_editor_key}'")
        else:
            reader = QImageReader(full_path_norm)
            if source_file_path_rel.lower().endswith(".gif"): reader.setFormat(b"gif")
            
            logger.debug(f"get_asset_pixmap: QImageReader created for '{full_path_norm}'. Can read: {reader.canRead()}")
            if reader.canRead():
                image_from_reader: QImage = reader.read()
                if not image_from_reader.isNull():
                    logger.debug(f"get_asset_pixmap: Image read successfully for '{full_path_norm}'. Size: {image_from_reader.size()}")
                    native_pixmap = QPixmap.fromImage(image_from_reader)
                    if native_pixmap.isNull(): 
                        logger.error(f"QPixmap.fromImage failed for '{full_path_norm}'. Reader error: {reader.errorString()}")
                    else:
                        logger.debug(f"get_asset_pixmap: Pixmap created from image. Size: {native_pixmap.size()}")
                else: 
                    logger.error(f"QImageReader.read() null for '{full_path_norm}'. Reader error: {reader.errorString()}")
            else: 
                logger.error(f"QImageReader cannot read '{full_path_norm}'. Reader error: {reader.errorString()}")
            
            if native_pixmap and not native_pixmap.isNull() and color_to_use_tuple and asset_data_entry.get("colorable"):
                try:
                    logger.debug(f"get_asset_pixmap: Colorizing '{asset_editor_key}' with {color_to_use_tuple}")
                    temp_image = native_pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
                    painter = QPainter(temp_image)
                    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                    painter.fillRect(temp_image.rect(), QColor(*color_to_use_tuple))
                    painter.end()
                    native_pixmap = QPixmap.fromImage(temp_image)
                    if native_pixmap.isNull():
                         logger.error(f"get_asset_pixmap: Colorized pixmap became null for '{asset_editor_key}'.")
                    else:
                         logger.debug(f"get_asset_pixmap: Colorizing successful for '{asset_editor_key}'. New pixmap size: {native_pixmap.size()}")

                except Exception as e_colorize: logger.error(f"Error colorizing '{asset_editor_key}': {e_colorize}", exc_info=True)
    
    elif "surface_params" in asset_data_entry and asset_data_entry.get("render_mode") is None and asset_data_entry.get("icon_type") is None:
        params = asset_data_entry["surface_params"]
        if params and isinstance(params, tuple) and len(params) == 3:
            w, h, default_color_tuple = params
            native_pixmap = _create_colored_pixmap(w, h, color_to_use_tuple or default_color_tuple)
            logger.debug(f"get_asset_pixmap: Created procedural colored pixmap for '{asset_editor_key}'. Size: {native_pixmap.size() if native_pixmap else 'None'}")
        else: logger.warning(f"Malformed 'surface_params' for '{asset_editor_key}': {params}")
    elif "render_mode" in asset_data_entry and asset_data_entry["render_mode"] == "half_tile":
        half_type = asset_data_entry.get("half_type", "left")
        default_color_proc = asset_data_entry.get("base_color_tuple", getattr(ED_CONFIG.C, 'MAGENTA', (255,0,255)))
        native_pixmap = _create_half_tile_pixmap(ts, half_type, color_to_use_tuple or default_color_proc)
        logger.debug(f"get_asset_pixmap: Created procedural half_tile pixmap for '{asset_editor_key}'. Size: {native_pixmap.size() if native_pixmap else 'None'}")
    elif "icon_type" in asset_data_entry:
        icon_type_str = asset_data_entry["icon_type"]
        default_color_icon = asset_data_entry.get("base_color_tuple", getattr(ED_CONFIG.C, 'YELLOW', (255,255,0)))
        native_pixmap = _create_icon_pixmap(ts, icon_type_str, color_to_use_tuple or default_color_icon)
        logger.debug(f"get_asset_pixmap: Created procedural icon pixmap for '{asset_editor_key}'. Size: {native_pixmap.size() if native_pixmap else 'None'}")

    if not native_pixmap or native_pixmap.isNull():
        logger.warning(f"Native pixmap for '{asset_editor_key}' failed or is null. Creating RED fallback using requested_target_size: {requested_target_size}.")
        fallback_pixmap = QPixmap(requested_target_size)
        fallback_pixmap.fill(QColor(*getattr(ED_CONFIG.C, 'RED', (255,0,0))))
        painter = QPainter(fallback_pixmap); painter.setPen(QColor(Qt.GlobalColor.black))
        painter.drawLine(0,0, fallback_pixmap.width(), fallback_pixmap.height())
        painter.drawLine(0,fallback_pixmap.height(), fallback_pixmap.width(), 0); painter.end()
        return fallback_pixmap

    if get_native_size_only:
        logger.debug(f"get_asset_pixmap: Returning NATIVE size pixmap for '{asset_editor_key}'. Size: {native_pixmap.size()}")
        return native_pixmap # Return the unscaled native pixmap
    
    # If we need to scale it to the requested_target_size
    if native_pixmap.size() != requested_target_size:
        scaled_pixmap = native_pixmap.scaled(requested_target_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        logger.debug(f"get_asset_pixmap: SCALED pixmap for '{asset_editor_key}' from {native_pixmap.size()} to {requested_target_size} (actual: {scaled_pixmap.size()}).")
        return scaled_pixmap
    else:
        logger.debug(f"get_asset_pixmap: Returning pixmap for '{asset_editor_key}' (already at requested size). Size: {native_pixmap.size()}")
        return native_pixmap # Already the correct size


def load_editor_palette_assets(editor_state: EditorState, main_window_ref: Optional[Any] = None):
    editor_state.assets_palette.clear()
    if QApplication.instance() is None:
        logger.critical("QApplication not instantiated before load_editor_palette_assets!")
    
    logger.info("Loading editor palette assets for Qt...")
    successful_loads = 0; failed_loads = 0
    target_thumb_size = QSize(ED_CONFIG.ASSET_THUMBNAIL_SIZE, ED_CONFIG.ASSET_THUMBNAIL_SIZE)
    ts = ED_CONFIG.BASE_GRID_SIZE

    fallback_qcolor_red = QColor(*getattr(ED_CONFIG.C, 'RED', (255,0,0)))
    fallback_qcolor_blue = QColor(*getattr(ED_CONFIG.C, 'BLUE', (0,0,255)))

    for asset_key, asset_info_def in ED_CONFIG.EDITOR_PALETTE_ASSETS.items():
        logger.debug(f"Processing palette asset: {asset_key}")
        asset_data_entry: Dict[str, Any] = {
            "game_type_id": asset_info_def.get("game_type_id", asset_key),
            "category": asset_info_def.get("category", "unknown"),
            # "original_size_pixels" will be determined below
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

        # --- Determine and store NATIVE/ORIGINAL size of the asset ---
        original_w, original_h = ts, ts # Default
        # Get the asset at its native size first
        # Pass a dummy QSize for requested_target_size as get_native_size_only=True will ignore it for scaling.
        native_pixmap_for_size_determination = get_asset_pixmap(asset_key, asset_data_entry, 
                                                                QSize(1,1), # Dummy, ignored for scaling by get_native_size_only
                                                                override_color=None, 
                                                                get_native_size_only=True)
        if native_pixmap_for_size_determination and not native_pixmap_for_size_determination.isNull():
            original_w, original_h = native_pixmap_for_size_determination.width(), native_pixmap_for_size_determination.height()
            logger.debug(f"Native size for '{asset_key}' determined as: {original_w}x{original_h}")
        else: # Fallback if native size determination failed (e.g., file not found for source_file assets)
            if asset_data_entry.get("source_file"):
                logger.warning(f"Could not determine native size for file-based asset '{asset_key}'. Using default {ts}x{ts}.")
            # For procedural, it might have 'surface_params'
            elif "surface_params" in asset_info_def:
                params = asset_info_def["surface_params"]
                if params and isinstance(params, tuple) and len(params) >= 2:
                    original_w, original_h = params[0], params[1]
                    logger.debug(f"Native size for procedural '{asset_key}' from surface_params: {original_w}x{original_h}")
            # Add more specific fallbacks for half_tile, icon_type if needed, otherwise default ts,ts holds.
        asset_data_entry["original_size_pixels"] = (original_w, original_h)
        # --- End NATIVE size determination ---

        # Get the pixmap for the palette (thumbnail size)
        pixmap_for_palette = get_asset_pixmap(asset_key, asset_data_entry, target_thumb_size, get_native_size_only=False)
        
        intended_pixmap_created_successfully = False
        if pixmap_for_palette and not pixmap_for_palette.isNull():
            # Check if it's the RED fallback (which is created at target_thumb_size)
            is_fallback_red_check_img = pixmap_for_palette.toImage()
            is_fallback_red = (pixmap_for_palette.size() == target_thumb_size and
                               is_fallback_red_check_img.pixelColor(0,0) == fallback_qcolor_red and
                               is_fallback_red_check_img.pixelColor(target_thumb_size.width()-1, 0) == fallback_qcolor_red)
            if not is_fallback_red:
                intended_pixmap_created_successfully = True
                logger.debug(f"Palette pixmap for '{asset_key}' (thumbnail) loaded/created. Size: {pixmap_for_palette.size()}")
            else:
                 logger.warning(f"Palette pixmap for '{asset_key}' appears to be the RED fallback.")


        if not pixmap_for_palette or pixmap_for_palette.isNull():
            logger.error(f"Creating FINAL fallback palette icon for '{asset_key}' (after native size attempt). Target size: {target_thumb_size}")
            pixmap_for_palette = QPixmap(target_thumb_size); pixmap_for_palette.fill(fallback_qcolor_red)
            painter = QPainter(pixmap_for_palette); painter.setPen(QColor(Qt.GlobalColor.black))
            painter.drawLine(0,0,target_thumb_size.width(),target_thumb_size.height())
            painter.drawLine(0,target_thumb_size.height(),target_thumb_size.width(),0); painter.end()
        
        asset_data_entry["q_pixmap"] = pixmap_for_palette

        # --- Cursor Pixmap Creation (at its original/native size with alpha) ---
        # original_w, original_h are now correctly determined above
        logger.debug(f"Creating cursor pixmap for '{asset_key}' at native size: {original_w}x{original_h}")
        cursor_base_pixmap_native = get_asset_pixmap(asset_key, asset_data_entry, 
                                                     QSize(original_w, original_h), 
                                                     override_color=None, # Use asset's default color or base image for cursor
                                                     get_native_size_only=True) # Ensure native size
        pixmap_for_cursor: Optional[QPixmap] = None
        if cursor_base_pixmap_native and not cursor_base_pixmap_native.isNull():
            try:
                img_for_cursor_alpha = cursor_base_pixmap_native.toImage().convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
                cursor_image_with_alpha = QImage(img_for_cursor_alpha.size(), QImage.Format.Format_ARGB32_Premultiplied)
                cursor_image_with_alpha.fill(Qt.GlobalColor.transparent) # Start with a transparent image
                painter = QPainter(cursor_image_with_alpha)
                painter.setOpacity(ED_CONFIG.CURSOR_ASSET_ALPHA / 255.0)
                painter.drawImage(0, 0, img_for_cursor_alpha) # Draw the original (possibly colored) image with opacity
                painter.end()
                pixmap_for_cursor = QPixmap.fromImage(cursor_image_with_alpha)
                if pixmap_for_cursor.isNull():
                    logger.error(f"Cursor pixmap became null after alpha application for '{asset_key}'.")
                else:
                    logger.debug(f"Cursor pixmap for '{asset_key}' created with alpha. Size: {pixmap_for_cursor.size()}")

            except Exception as e_cursor_alpha:
                logger.error(f"Error applying alpha to cursor for '{asset_key}': {e_cursor_alpha}", exc_info=True)
                pixmap_for_cursor = QPixmap(original_w, original_h); pixmap_for_cursor.fill(fallback_qcolor_blue)
        else:
            logger.warning(f"Native base pixmap for cursor of '{asset_key}' was null. Using fallback BLUE cursor of size {original_w}x{original_h}.")
            pixmap_for_cursor = QPixmap(original_w, original_h); pixmap_for_cursor.fill(fallback_qcolor_blue)
        
        asset_data_entry["q_pixmap_cursor"] = pixmap_for_cursor
        editor_state.assets_palette[asset_key] = asset_data_entry

        if intended_pixmap_created_successfully: successful_loads += 1
        else: failed_loads += 1

    logger.info(f"Palette asset loading complete. Success: {successful_loads}, Failed/Fallback: {failed_loads}.")