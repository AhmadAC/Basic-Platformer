# editor_assets.py
# -*- coding: utf-8 -*-
"""
## version 2.0.2 (PySide6 Conversion - Added Qt import for enums)
Handles loading and managing assets for the editor's palette using QPixmap and QMovie.
"""
import os
import sys
import logging
from typing import Optional, Dict, Any, Tuple, List

from PySide6.QtGui import QPixmap, QImage, QPainter, QColor, QMovie
from PySide6.QtCore import QRectF, QPointF, QSize, Qt # CORRECTED: Added Qt

# --- (Sys.path manipulation) ---
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

try:
    from assets import resource_path
except ImportError:
    print("CRITICAL ASSETS: 'assets' module (resource_path) not found. Using basic fallback.")
    def resource_path(relative_path):
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        return os.path.join(base_path, relative_path)

import editor_config as ED_CONFIG
from editor_state import EditorState

logger = logging.getLogger(__name__)

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
    if half_type == "left": rect_to_draw = QRectF(0, 0, base_size / 2, base_size)
    elif half_type == "right": rect_to_draw = QRectF(base_size / 2, 0, base_size / 2, base_size)
    elif half_type == "top": rect_to_draw = QRectF(0, 0, base_size, base_size / 2)
    elif half_type == "bottom": rect_to_draw = QRectF(0, base_size / 2, base_size, base_size / 2)

    if rect_to_draw:
        painter.drawRect(rect_to_draw)
    painter.end()
    return pixmap

def _create_icon_pixmap(base_size: int, icon_type: str, color_tuple: Tuple[int,int,int]) -> QPixmap:
    pixmap = QPixmap(base_size, base_size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setBrush(QColor(*color_tuple))
    painter.setPen(QColor(0,0,0))

    if icon_type == "2x2_placer":
        s = base_size
        rect_size = s * 0.35
        gap = s * 0.1
        painter.drawRect(QRectF(gap, gap, rect_size, rect_size))
        painter.drawRect(QRectF(s - gap - rect_size, gap, rect_size, rect_size))
        painter.drawRect(QRectF(gap, s - gap - rect_size, rect_size, rect_size))
        painter.drawRect(QRectF(s - gap - rect_size, s - gap - rect_size, rect_size, rect_size))
    elif icon_type == "eraser":
        s = base_size
        painter.setBrush(QColor(*color_tuple))
        painter.setPen(QColor(Qt.GlobalColor.black)) # Corrected: Qt.GlobalColor.black
        painter.drawRect(QRectF(s * 0.1, s * 0.3, s * 0.8, s * 0.4))
        painter.drawLine(QPointF(s*0.2, s*0.2), QPointF(s*0.8, s*0.8))
        painter.drawLine(QPointF(s*0.2, s*0.8), QPointF(s*0.8, s*0.2))
    elif icon_type == "color_swatch":
        s = base_size
        painter.setBrush(QColor(*color_tuple))
        painter.setPen(QColor(Qt.GlobalColor.black)) # Corrected: Qt.GlobalColor.black
        painter.drawRect(QRectF(s*0.1, s*0.1, s*0.8, s*0.8))
    else:
        painter.setPen(QColor(*color_tuple))
        font = painter.font(); font.setPointSize(base_size // 2); painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "?") # Corrected: Qt.AlignmentFlag.AlignCenter

    painter.end()
    return pixmap

def get_asset_pixmap(asset_editor_key: str,
                     asset_data_entry: Dict[str, Any],
                     target_size: QSize,
                     override_color: Optional[Tuple[int,int,int]] = None) -> Optional[QPixmap]:
    final_pixmap: Optional[QPixmap] = None
    ts = ED_CONFIG.BASE_GRID_SIZE

    color_to_use = override_color
    if not color_to_use and asset_data_entry.get("colorable"):
        color_to_use = asset_data_entry.get("base_color_tuple") or \
                       (asset_data_entry.get("surface_params_dims_color")[2] if asset_data_entry.get("surface_params_dims_color") else None)

    if "source_file" in asset_data_entry:
        full_path = resource_path(asset_data_entry["source_file"])
        if not os.path.exists(full_path):
            logger.error(f"Assets Error: File NOT FOUND at '{full_path}' for asset '{asset_editor_key}' in get_asset_pixmap")
            # Use ED_CONFIG.C.RED directly as it's defined as a tuple
            return _create_colored_pixmap(target_size.width(), target_size.height(), ED_CONFIG.C.RED if hasattr(ED_CONFIG.C, 'RED') else (255,0,0))


        if asset_data_entry["source_file"].lower().endswith(".gif"):
            movie = QMovie(full_path)
            if movie.isValid():
                final_pixmap = movie.currentPixmap()
            else:
                logger.warning(f"QMovie could not load/is invalid for '{asset_editor_key}' from '{full_path}'. Trying QPixmap.")
                final_pixmap = QPixmap(full_path)
        else:
            final_pixmap = QPixmap(full_path)

        if final_pixmap and final_pixmap.isNull():
            logger.error(f"Failed to load image for '{asset_editor_key}' from '{full_path}' using QPixmap.")
            final_pixmap = None

        if final_pixmap and color_to_use and asset_data_entry.get("colorable"):
            temp_image = final_pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32)
            painter = QPainter(temp_image)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Multiply)
            painter.fillRect(temp_image.rect(), QColor(*color_to_use, 128))
            painter.end()
            final_pixmap = QPixmap.fromImage(temp_image)

    elif "surface_params" in asset_data_entry:
        w, h, default_color = asset_data_entry["surface_params"]
        final_pixmap = _create_colored_pixmap(w, h, color_to_use or default_color)
    elif "render_mode" in asset_data_entry and asset_data_entry["render_mode"] == "half_tile":
        half_type = asset_data_entry.get("half_type", "left")
        default_color = asset_data_entry.get("base_color_tuple", ED_CONFIG.C.MAGENTA if hasattr(ED_CONFIG.C, 'MAGENTA') else (255,0,255))
        final_pixmap = _create_half_tile_pixmap(ts, half_type, color_to_use or default_color)
    elif "icon_type" in asset_data_entry:
        icon_type = asset_data_entry["icon_type"]
        default_color = asset_data_entry.get("base_color_tuple", ED_CONFIG.C.YELLOW if hasattr(ED_CONFIG.C, 'YELLOW') else (255,255,0))
        final_pixmap = _create_icon_pixmap(ts, icon_type, color_to_use or default_color)

    if not final_pixmap:
        logger.warning(f"Could not generate pixmap for '{asset_editor_key}'. Creating fallback.")
        final_pixmap = _create_colored_pixmap(ts, ts, ED_CONFIG.C.RED if hasattr(ED_CONFIG.C, 'RED') else (255,0,0))
        painter = QPainter(final_pixmap)
        painter.setPen(QColor(0,0,0))
        painter.drawLine(0,0, ts, ts)
        painter.drawLine(0,ts, ts, 0)
        painter.end()

    if final_pixmap and (final_pixmap.size() != target_size):
        final_pixmap = final_pixmap.scaled(target_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation) # Corrected

    return final_pixmap


def load_editor_palette_assets(editor_state: EditorState, main_window_ref: Optional[Any] = None):
    editor_state.assets_palette.clear()
    logger.info("Loading editor palette assets for Qt...")
    successful_loads = 0
    failed_loads = 0
    target_thumb_size = QSize(ED_CONFIG.ASSET_THUMBNAIL_SIZE, ED_CONFIG.ASSET_THUMBNAIL_SIZE)
    ts = ED_CONFIG.BASE_GRID_SIZE

    for asset_key, asset_info_def in ED_CONFIG.EDITOR_PALETTE_ASSETS.items():
        asset_data_entry: Dict[str, Any] = {
            "game_type_id": asset_info_def.get("game_type_id", asset_key),
            "category": asset_info_def.get("category", "unknown"),
            "original_size_pixels": (ts, ts),
            "places_asset_key": asset_info_def.get("places_asset_key"),
            "colorable": asset_info_def.get("colorable", False),
            "render_mode": asset_info_def.get("render_mode"),
            "half_type": asset_info_def.get("half_type"),
            "base_color_tuple": asset_info_def.get("base_color_tuple"),
            "surface_params_dims_color": asset_info_def.get("surface_params"),
            "name_in_palette": asset_info_def.get("name_in_palette", asset_key.replace("_", " ").title()) # Use name_in_palette or derive
        }
        # Ensure tooltip key is not in asset_data_entry as tooltips are removed
        if "tooltip" in asset_data_entry: # Should not happen if ED_CONFIG is updated
            del asset_data_entry["tooltip"]

        pixmap_for_palette: Optional[QPixmap] = None
        pixmap_for_cursor: Optional[QPixmap] = None
        original_w, original_h = ts, ts

        fallback_red = ED_CONFIG.C.RED if hasattr(ED_CONFIG.C, 'RED') else (255,0,0)
        fallback_magenta = ED_CONFIG.C.MAGENTA if hasattr(ED_CONFIG.C, 'MAGENTA') else (255,0,255)
        fallback_yellow = ED_CONFIG.C.YELLOW if hasattr(ED_CONFIG.C, 'YELLOW') else (255,255,0)
        fallback_blue = ED_CONFIG.C.BLUE if hasattr(ED_CONFIG.C, 'BLUE') else (0,0,255)


        if "source_file" in asset_info_def:
            source_file_path = asset_info_def["source_file"]
            try:
                full_path = resource_path(source_file_path)
                if not os.path.exists(full_path):
                    logger.error(f"Assets Error: File NOT FOUND at '{full_path}' for asset '{asset_key}'")
                    pixmap_for_palette = _create_colored_pixmap(ts, ts, fallback_red)
                else:
                    temp_pixmap = None
                    if source_file_path.lower().endswith(".gif"):
                        movie = QMovie(full_path)
                        if movie.isValid() and movie.frameCount() > 0:
                            temp_pixmap = movie.currentPixmap()
                        else:
                            logger.warning(f"QMovie failed for '{asset_key}'. Trying QPixmap.")
                            temp_pixmap = QPixmap(full_path)
                    else:
                        temp_pixmap = QPixmap(full_path)

                    if temp_pixmap and not temp_pixmap.isNull():
                        original_w, original_h = temp_pixmap.width(), temp_pixmap.height()
                        pixmap_for_palette = temp_pixmap.scaled(target_thumb_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation) # Corrected
                    else:
                        logger.error(f"Failed to load image for '{asset_key}' from '{full_path}'.")
                        pixmap_for_palette = _create_colored_pixmap(ts,ts, fallback_red)
            except Exception as e:
                logger.error(f"Error loading source_file for '{asset_key}': {e}", exc_info=True)
                pixmap_for_palette = _create_colored_pixmap(ts,ts, fallback_red)

        elif "surface_params" in asset_info_def:
            w, h, color = asset_info_def["surface_params"]
            original_w, original_h = w, h
            pixmap_for_palette = _create_colored_pixmap(w, h, color)
        elif "render_mode" in asset_info_def and asset_info_def["render_mode"] == "half_tile":
            half_type = asset_info_def.get("half_type", "left")
            color = asset_info_def.get("base_color_tuple", fallback_magenta)
            original_w, original_h = ts, ts
            pixmap_for_palette = _create_half_tile_pixmap(ts, half_type, color)
        elif "icon_type" in asset_info_def:
            icon_type = asset_info_def["icon_type"]
            color = asset_info_def.get("base_color_tuple", fallback_yellow)
            original_w, original_h = ts, ts
            pixmap_for_palette = _create_icon_pixmap(ts, icon_type, color)
        else:
            logger.warning(f"Asset '{asset_key}' has no defined source or generation method.")
            pixmap_for_palette = _create_colored_pixmap(ts,ts, fallback_red)

        asset_data_entry["original_size_pixels"] = (original_w, original_h)

        if pixmap_for_palette and pixmap_for_palette.size() != target_thumb_size:
             pixmap_for_palette = pixmap_for_palette.scaled(target_thumb_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation) # Corrected

        cursor_base_pixmap = get_asset_pixmap(
            asset_key, asset_info_def,
            QSize(original_w, original_h)
        )

        if cursor_base_pixmap and not cursor_base_pixmap.isNull():
            temp_image_for_cursor = cursor_base_pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
            painter = QPainter(temp_image_for_cursor)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
            painter.fillRect(temp_image_for_cursor.rect(), QColor(0, 0, 0, ED_CONFIG.CURSOR_ASSET_ALPHA))
            painter.end()
            pixmap_for_cursor = QPixmap.fromImage(temp_image_for_cursor)
        else:
            pixmap_for_cursor = _create_colored_pixmap(original_w, original_h, fallback_blue)


        if pixmap_for_palette and not pixmap_for_palette.isNull():
            asset_data_entry["q_pixmap"] = pixmap_for_palette
            asset_data_entry["q_pixmap_cursor"] = pixmap_for_cursor
            editor_state.assets_palette[asset_key] = asset_data_entry
            successful_loads += 1
        else:
            logger.error(f"Failed to generate final palette pixmap for '{asset_key}'.")
            fallback_pixmap = _create_colored_pixmap(target_thumb_size.width(), target_thumb_size.height(), fallback_red)
            painter = QPainter(fallback_pixmap); painter.setPen(QColor(0,0,0)); painter.drawLine(0,0, fallback_pixmap.width(), fallback_pixmap.height()); painter.drawLine(0,fallback_pixmap.height(), fallback_pixmap.width(), 0); painter.end()
            asset_data_entry["q_pixmap"] = fallback_pixmap
            asset_data_entry["q_pixmap_cursor"] = fallback_pixmap.copy()
            editor_state.assets_palette[asset_key] = asset_data_entry
            failed_loads += 1

    logger.info(f"Palette asset loading complete. Success: {successful_loads}, Failed: {failed_loads}.")