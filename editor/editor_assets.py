#################### START OF FILE: editor_assets.py ####################

# editor/editor_assets.py
# -*- coding: utf-8 -*-
"""
## version 2.1.0 (Feature Rich Update - Assets)
Handles loading and managing assets for the editor's palette using PySide6.
- Includes placeholder icon generation for trigger squares.
- get_asset_pixmap can now handle source_file paths being absolute for custom assets.
- Added rotation and flip support to get_asset_pixmap.
"""
import os
import sys
import logging
from typing import Optional, Dict, Any, Tuple, List

from PySide6.QtGui import QPixmap, QImage, QPainter, QColor, QPen, QImageReader, QBrush, QTransform
from PySide6.QtCore import QRectF, QPointF, QSize, Qt
from PySide6.QtWidgets import QApplication

# --- Sys.path manipulation ---
current_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

logger = logging.getLogger(__name__)

try:
    from assets import resource_path
    if logger.hasHandlers() and logger.isEnabledFor(logging.INFO): 
        logger.info("EditorAssets: Imported 'resource_path' from root 'assets'.")
    elif not logger.hasHandlers(): 
        logging.basicConfig(level=logging.DEBUG, format='FallbackLogger - %(levelname)s - %(message)s')
        logger = logging.getLogger(__name__) 
        logger.info("EditorAssets (Fallback Logger Active): Imported 'resource_path' from root 'assets'.")
except ImportError:
    if not logger.hasHandlers(): 
        logging.basicConfig(level=logging.DEBUG, format='FallbackLogger - %(levelname)s - %(message)s')
        logger = logging.getLogger(__name__)
    logger.warning("EditorAssets: Could not import 'resource_path' from root 'assets'. Using fallback.")
    def resource_path(relative_path: str) -> str: 
        return os.path.join(parent_dir, relative_path)

from . import editor_config as ED_CONFIG 
from .editor_state import EditorState 

# --- Helper functions for creating procedural QPixmaps ---
def _create_colored_pixmap(width: int, height: int, color_tuple: Tuple[int,int,int]) -> QPixmap:
    safe_width = max(1, width)
    safe_height = max(1, height)
    pixmap = QPixmap(safe_width, safe_height)
    if pixmap.isNull():
        logger.error(f"_create_colored_pixmap: QPixmap is null for size {safe_width}x{safe_height}. Returning empty pixmap.")
        return QPixmap() 
    pixmap.fill(QColor(*color_tuple))
    return pixmap

def _create_half_tile_pixmap(base_size: int, half_type: str, color_tuple: Tuple[int,int,int]) -> QPixmap:
    safe_base_size = max(1, base_size)
    pixmap = QPixmap(safe_base_size, safe_base_size)
    if pixmap.isNull():
        logger.error(f"_create_half_tile_pixmap: QPixmap is null for size {safe_base_size}x{safe_base_size}. Returning empty pixmap.")
        return QPixmap()
        
    pixmap.fill(Qt.GlobalColor.transparent)
    
    painter = QPainter()
    if not painter.begin(pixmap):
        logger.error(f"_create_half_tile_pixmap: QPainter.begin() failed for pixmap size {safe_base_size}x{safe_base_size}. Pixmap might be invalid.")
        return pixmap 
        
    try:
        painter.setBrush(QColor(*color_tuple))
        painter.setPen(Qt.GlobalColor.transparent)
        rect_to_draw = QRectF()
        if half_type == "left": rect_to_draw = QRectF(0, 0, safe_base_size / 2.0, float(safe_base_size))
        elif half_type == "right": rect_to_draw = QRectF(safe_base_size / 2.0, 0, safe_base_size / 2.0, float(safe_base_size))
        elif half_type == "top": rect_to_draw = QRectF(0, 0, float(safe_base_size), safe_base_size / 2.0)
        elif half_type == "bottom": rect_to_draw = QRectF(0, safe_base_size / 2.0, float(safe_base_size), safe_base_size / 2.0)
        
        if not rect_to_draw.isNull() and rect_to_draw.isValid():
            painter.drawRect(rect_to_draw)
        else:
            logger.warning(f"_create_half_tile_pixmap: rect_to_draw is null or invalid for half_type '{half_type}'.")
    finally:
        painter.end()
        
    return pixmap

def _create_icon_pixmap(base_size: int, icon_type: str, color_tuple: Tuple[int,int,int, Optional[int]]) -> QPixmap:
    safe_base_size = max(1, base_size)
    pixmap = QPixmap(safe_base_size, safe_base_size)
    if pixmap.isNull():
        logger.error(f"_create_icon_pixmap: QPixmap is null for size {safe_base_size}x{safe_base_size} (original base_size: {base_size}). Returning empty pixmap.")
        return QPixmap()

    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter()
    if not painter.begin(pixmap):
        logger.error(f"_create_icon_pixmap: QPainter.begin() failed for pixmap size {safe_base_size}x{safe_base_size}. Pixmap might be invalid.")
        return pixmap 

    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        s = float(safe_base_size)
        
        if len(color_tuple) == 4 and color_tuple[3] is not None: 
            icon_qcolor = QColor(color_tuple[0], color_tuple[1], color_tuple[2], color_tuple[3]) 
        else: 
            icon_qcolor = QColor(color_tuple[0], color_tuple[1], color_tuple[2]) 
            
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
        elif icon_type == "generic_square_icon": 
            painter.setBrush(QBrush(icon_qcolor))
            painter.setPen(QPen(border_qcolor, 1))
            inner_rect = QRectF(s * 0.15, s * 0.15, s * 0.7, s * 0.7)
            painter.drawRect(inner_rect)
            text_color = Qt.GlobalColor.black if icon_qcolor.lightnessF() > 0.5 else Qt.GlobalColor.white
            if icon_qcolor.alphaF() < 0.5: 
                 text_color = Qt.GlobalColor.black 
            painter.setPen(text_color)
            font = painter.font(); font.setPointSize(int(s * 0.35)); font.setBold(True); painter.setFont(font)
            painter.drawText(inner_rect, Qt.AlignmentFlag.AlignCenter, "TRG")
        else: 
            painter.setPen(icon_qcolor)
            font = painter.font(); font.setPointSize(int(s * 0.6)); font.setBold(True); painter.setFont(font)
            painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "?")
    finally:
        painter.end()
        
    return pixmap


def get_asset_pixmap(asset_editor_key: str,
                     asset_data_entry: Dict[str, Any],
                     requested_target_size: QSize, 
                     override_color: Optional[Tuple[int,int,int]] = None,
                     get_native_size_only: bool = False,
                     is_flipped_h: bool = False,
                     rotation: int = 0) -> Optional[QPixmap]: # Added rotation
    native_pixmap: Optional[QPixmap] = None
    ts = ED_CONFIG.BASE_GRID_SIZE

    color_to_use_tuple = override_color
    if not color_to_use_tuple and asset_data_entry.get("colorable"):
        color_to_use_tuple = asset_data_entry.get("base_color_tuple")
        if not color_to_use_tuple:
            surface_params_val = asset_data_entry.get("surface_params")
            if surface_params_val and isinstance(surface_params_val, tuple) and len(surface_params_val) == 3:
                color_to_use_tuple = surface_params_val[2]

    source_file_path = asset_data_entry.get("source_file") 

    if source_file_path:
        full_path_abs = source_file_path if os.path.isabs(source_file_path) else resource_path(source_file_path)
        full_path_norm = os.path.normpath(full_path_abs)
        
        if not os.path.exists(full_path_norm):
            logger.error(f"File NOT FOUND: '{full_path_norm}' for asset '{asset_editor_key}'")
        else:
            reader = QImageReader(full_path_norm)
            if source_file_path.lower().endswith(".gif"): reader.setFormat(b"gif")
            
            if reader.canRead():
                image_from_reader: QImage = reader.read()
                if not image_from_reader.isNull():
                    native_pixmap = QPixmap.fromImage(image_from_reader)
                    if native_pixmap.isNull(): 
                        logger.error(f"QPixmap.fromImage failed for '{full_path_norm}'. Error: {reader.errorString()}")
                else: 
                    logger.error(f"QImageReader.read() null for '{full_path_norm}'. Error: {reader.errorString()}")
            else: 
                logger.error(f"QImageReader cannot read '{full_path_norm}'. Error: {reader.errorString()}")
            
            if native_pixmap and not native_pixmap.isNull() and color_to_use_tuple and asset_data_entry.get("colorable"):
                try:
                    temp_image = native_pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
                    painter = QPainter()
                    if painter.begin(temp_image):
                        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn) # type: ignore
                        painter.fillRect(temp_image.rect(), QColor(*color_to_use_tuple)) # type: ignore
                        painter.end()
                        native_pixmap = QPixmap.fromImage(temp_image)
                    else:
                        logger.error(f"Failed to begin painter for colorizing '{asset_editor_key}'")
                except Exception as e_colorize: logger.error(f"Error colorizing '{asset_editor_key}': {e_colorize}", exc_info=True)
    
    elif "surface_params" in asset_data_entry and asset_data_entry.get("render_mode") is None and asset_data_entry.get("icon_type") is None:
        params = asset_data_entry["surface_params"]
        if params and isinstance(params, tuple) and len(params) == 3:
            w, h, default_color_tuple = params
            native_pixmap = _create_colored_pixmap(w, h, color_to_use_tuple or default_color_tuple) # type: ignore
    elif "render_mode" in asset_data_entry and asset_data_entry["render_mode"] == "half_tile":
        half_type = asset_data_entry.get("half_type", "left")
        default_color_proc = asset_data_entry.get("base_color_tuple", getattr(ED_CONFIG.C, 'MAGENTA', (255,0,255)))
        native_pixmap = _create_half_tile_pixmap(ts, half_type, color_to_use_tuple or default_color_proc) # type: ignore
    elif "icon_type" in asset_data_entry:
        icon_type_str = asset_data_entry["icon_type"]
        default_color_icon = asset_data_entry.get("base_color_tuple", getattr(ED_CONFIG.C, 'YELLOW', (255,255,0)))
        native_pixmap = _create_icon_pixmap(ts, icon_type_str, color_to_use_tuple or default_color_icon) # type: ignore

    if not native_pixmap or native_pixmap.isNull():
        logger.warning(f"Native pixmap for '{asset_editor_key}' failed or is null. Creating RED fallback.")
        fb_w = requested_target_size.width() if requested_target_size.width() > 0 else ED_CONFIG.ASSET_THUMBNAIL_SIZE
        fb_h = requested_target_size.height() if requested_target_size.height() > 0 else ED_CONFIG.ASSET_THUMBNAIL_SIZE
        
        fallback_pixmap = QPixmap(max(1, fb_w), max(1, fb_h))
        if fallback_pixmap.isNull():
            logger.error(f"Fallback pixmap for '{asset_editor_key}' is ALSO NULL. Size: {fb_w}x{fb_h}")
            return QPixmap()

        fallback_pixmap.fill(QColor(*getattr(ED_CONFIG.C, 'RED', (255,0,0))))
        
        painter = QPainter()
        if painter.begin(fallback_pixmap):
            try:
                painter.setPen(QColor(Qt.GlobalColor.black))
                painter.drawLine(0,0, fallback_pixmap.width()-1, fallback_pixmap.height()-1)
                painter.drawLine(0,fallback_pixmap.height()-1, fallback_pixmap.width()-1, 0)
            finally:
                painter.end()
        else:
            logger.error(f"Failed to begin painter on fallback pixmap for {asset_editor_key}")
        
        if is_flipped_h and not fallback_pixmap.isNull(): 
            try:
                temp_img = fallback_pixmap.toImage()
                if not temp_img.isNull():
                    flipped_img = temp_img.mirrored(True, False) 
                    if not flipped_img.isNull():
                        fallback_pixmap = QPixmap.fromImage(flipped_img)
            except Exception as e_flip_fallback:
                logger.error(f"Error flipping fallback pixmap for '{asset_editor_key}': {e_flip_fallback}")
        
        if rotation != 0 and not fallback_pixmap.isNull():
            try:
                temp_img = fallback_pixmap.toImage()
                if not temp_img.isNull():
                    img_center = temp_img.rect().center()
                    transform = QTransform().translate(img_center.x(), img_center.y()).rotate(float(rotation)).translate(-img_center.x(), -img_center.y())
                    rotated_img = temp_img.transformed(transform, Qt.TransformationMode.SmoothTransformation)
                    if not rotated_img.isNull():
                        fallback_pixmap = QPixmap.fromImage(rotated_img)
            except Exception as e_rotate_fallback:
                logger.error(f"Error rotating fallback pixmap for '{asset_editor_key}': {e_rotate_fallback}")
        return fallback_pixmap

    # Apply flip 
    if is_flipped_h and native_pixmap and not native_pixmap.isNull():
        try:
            temp_img = native_pixmap.toImage()
            if not temp_img.isNull():
                flipped_img = temp_img.mirrored(True, False) 
                if not flipped_img.isNull():
                    native_pixmap = QPixmap.fromImage(flipped_img)
                else: logger.error(f"Failed to mirror image for '{asset_editor_key}'")
            else: logger.error(f"Failed to convert pixmap to image for flipping for '{asset_editor_key}'")
        except Exception as e_flip:
            logger.error(f"Error flipping pixmap for '{asset_editor_key}': {e_flip}", exc_info=True)
    
    # Apply rotation
    if rotation != 0 and native_pixmap and not native_pixmap.isNull():
        try:
            temp_img = native_pixmap.toImage()
            if not temp_img.isNull():
                img_center = temp_img.rect().center()
                transform = QTransform().translate(img_center.x(), img_center.y()).rotate(float(rotation)).translate(-img_center.x(), -img_center.y())
                rotated_img = temp_img.transformed(transform, Qt.TransformationMode.SmoothTransformation)
                
                if not rotated_img.isNull():
                    native_pixmap = QPixmap.fromImage(rotated_img)
                else: logger.error(f"Failed to rotate image for '{asset_editor_key}'")
            else: logger.error(f"Failed to convert pixmap to image for rotation for '{asset_editor_key}'")
        except Exception as e_rotate:
            logger.error(f"Error rotating pixmap for '{asset_editor_key}': {e_rotate}", exc_info=True)

    if get_native_size_only:
        orig_size_data = asset_data_entry.get("original_size_pixels")
        if orig_size_data and isinstance(orig_size_data, tuple) and len(orig_size_data) == 2 and native_pixmap:
            target_native_w, target_native_h = orig_size_data
            # Note: After rotation, width and height might have swapped.
            # If we must strictly return the original_size_pixels, scaling might be needed again.
            # For now, assume rotation changes effective dimensions for 'native' size if rotated by 90/270.
            current_w, current_h = native_pixmap.width(), native_pixmap.height()
            if rotation % 180 != 0: # 90 or 270 degrees rotation
                 current_w, current_h = current_h, current_w # Swap effective dimensions

            if current_w != target_native_w or current_h != target_native_h:
                 if target_native_w > 0 and target_native_h > 0:
                    return native_pixmap.scaled(target_native_w, target_native_h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation) # This might distort if aspect changed due to rotation
        return native_pixmap 
    
    if native_pixmap and native_pixmap.size() != requested_target_size and requested_target_size.isValid() and requested_target_size.width() > 0 and requested_target_size.height() > 0 :
        scaled_pixmap = native_pixmap.scaled(requested_target_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        return scaled_pixmap
    else:
        return native_pixmap 


def load_editor_palette_assets(editor_state: EditorState, main_window_ref: Optional[Any] = None):
    editor_state.assets_palette.clear()
    if QApplication.instance() is None:
        logger.critical("QApplication not instantiated before load_editor_palette_assets!")
    
    logger.info("Loading editor palette assets for Qt...")
    successful_loads = 0; failed_loads = 0
    target_thumb_size = QSize(ED_CONFIG.ASSET_THUMBNAIL_SIZE, ED_CONFIG.ASSET_THUMBNAIL_SIZE) # type: ignore
    ts = ED_CONFIG.BASE_GRID_SIZE # type: ignore

    fallback_qcolor_red = QColor(*getattr(ED_CONFIG.C, 'RED', (255,0,0))) # type: ignore
    fallback_qcolor_blue = QColor(*getattr(ED_CONFIG.C, 'BLUE', (0,0,255))) # type: ignore

    for asset_key, asset_info_def in ED_CONFIG.EDITOR_PALETTE_ASSETS.items(): # type: ignore
        asset_data_entry: Dict[str, Any] = {
            "game_type_id": asset_info_def.get("game_type_id", asset_key),
            "category": asset_info_def.get("category", "unknown"),
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

        original_w, original_h = ts, ts 
        native_pixmap_for_size_determination = get_asset_pixmap(asset_key, asset_data_entry, 
                                                                QSize(1,1), 
                                                                override_color=None, 
                                                                get_native_size_only=True,
                                                                is_flipped_h=False, rotation=0) 
        if native_pixmap_for_size_determination and not native_pixmap_for_size_determination.isNull():
            original_w, original_h = native_pixmap_for_size_determination.width(), native_pixmap_for_size_determination.height()
        elif "surface_params" in asset_info_def:
            params = asset_info_def["surface_params"]
            if params and isinstance(params, tuple) and len(params) >= 2:
                original_w, original_h = params[0], params[1]
        asset_data_entry["original_size_pixels"] = (original_w, original_h)
        
        # Palette icons are always default orientation
        pixmap_for_palette = get_asset_pixmap(asset_key, asset_data_entry, target_thumb_size, get_native_size_only=False, is_flipped_h=False, rotation=0)
        
        intended_pixmap_created_successfully = False
        if pixmap_for_palette and not pixmap_for_palette.isNull():
            is_fallback_red_check_img = pixmap_for_palette.toImage()
            if not is_fallback_red_check_img.isNull(): 
                is_fallback_red = (pixmap_for_palette.size() == target_thumb_size and
                                   is_fallback_red_check_img.pixelColor(0,0) == fallback_qcolor_red and
                                   is_fallback_red_check_img.pixelColor(target_thumb_size.width()-1, 0) == fallback_qcolor_red)
                if not is_fallback_red:
                    intended_pixmap_created_successfully = True
            else: 
                logger.warning(f"Pixmap toImage() failed for palette asset '{asset_key}'")
        
        if not pixmap_for_palette or pixmap_for_palette.isNull():
            fb_w = target_thumb_size.width() if target_thumb_size.width() > 0 else ED_CONFIG.ASSET_THUMBNAIL_SIZE # type: ignore
            fb_h = target_thumb_size.height() if target_thumb_size.height() > 0 else ED_CONFIG.ASSET_THUMBNAIL_SIZE # type: ignore
            pixmap_for_palette = QPixmap(max(1, fb_w), max(1, fb_h))
            
            if pixmap_for_palette.isNull():
                logger.error(f"Palette fallback pixmap for '{asset_key}' is ALSO NULL. Size: {fb_w}x{fb_h}")
                pixmap_for_palette = QPixmap() 
            else:
                pixmap_for_palette.fill(fallback_qcolor_red)
                painter = QPainter()
                if painter.begin(pixmap_for_palette):
                    try:
                        painter.setPen(QColor(Qt.GlobalColor.black))
                        painter.drawLine(0,0,pixmap_for_palette.width()-1,pixmap_for_palette.height()-1)
                        painter.drawLine(0,pixmap_for_palette.height()-1,pixmap_for_palette.width()-1,0)
                    finally:
                        painter.end()
                else:
                    logger.error(f"Failed to begin painter on palette fallback pixmap for {asset_key}")
        
        asset_data_entry["q_pixmap"] = pixmap_for_palette

        # Cursor pixmap is also initially unflipped/unrotated; MapViewWidget handles dynamic cursor visuals
        cursor_base_pixmap_native = get_asset_pixmap(asset_key, asset_data_entry, 
                                                     QSize(max(1,original_w), max(1,original_h)), 
                                                     override_color=None, 
                                                     get_native_size_only=True,
                                                     is_flipped_h=False, rotation=0) 
        pixmap_for_cursor: Optional[QPixmap] = None
        if cursor_base_pixmap_native and not cursor_base_pixmap_native.isNull():
            try:
                img_for_cursor_alpha = cursor_base_pixmap_native.toImage().convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
                if img_for_cursor_alpha.isNull() or img_for_cursor_alpha.width() == 0 or img_for_cursor_alpha.height() == 0:
                    logger.warning(f"Cursor base image for '{asset_key}' is invalid. Size: {img_for_cursor_alpha.size()}")
                    pixmap_for_cursor = QPixmap(max(1, original_w), max(1, original_h))
                    if not pixmap_for_cursor.isNull(): pixmap_for_cursor.fill(fallback_qcolor_blue)
                    else: pixmap_for_cursor = QPixmap()
                else:
                    cursor_image_with_alpha = QImage(img_for_cursor_alpha.size(), QImage.Format.Format_ARGB32_Premultiplied)
                    if cursor_image_with_alpha.isNull():
                        logger.error(f"Failed to create QImage for cursor alpha mask for '{asset_key}'")
                        pixmap_for_cursor = QPixmap(max(1, original_w), max(1, original_h))
                        if not pixmap_for_cursor.isNull(): pixmap_for_cursor.fill(fallback_qcolor_blue)
                        else: pixmap_for_cursor = QPixmap()
                    else:
                        cursor_image_with_alpha.fill(Qt.GlobalColor.transparent) 
                        painter = QPainter()
                        if painter.begin(cursor_image_with_alpha):
                            try:
                                painter.setOpacity(ED_CONFIG.CURSOR_ASSET_ALPHA / 255.0) # type: ignore
                                painter.drawImage(0, 0, img_for_cursor_alpha) 
                            finally:
                                painter.end()
                            pixmap_for_cursor = QPixmap.fromImage(cursor_image_with_alpha)
                            if pixmap_for_cursor.isNull():
                                logger.error(f"Pixmap.fromImage for cursor failed for '{asset_key}'")
                                pixmap_for_cursor = QPixmap(max(1, original_w), max(1, original_h)); 
                                if not pixmap_for_cursor.isNull(): pixmap_for_cursor.fill(fallback_qcolor_blue)
                                else: pixmap_for_cursor = QPixmap()
                        else:
                            logger.error(f"Failed to begin painter on cursor alpha image for '{asset_key}'")
                            pixmap_for_cursor = QPixmap(max(1, original_w), max(1, original_h))
                            if not pixmap_for_cursor.isNull(): pixmap_for_cursor.fill(fallback_qcolor_blue)
                            else: pixmap_for_cursor = QPixmap()
            except Exception as e_cursor_alpha:
                logger.error(f"Error applying alpha to cursor for '{asset_key}': {e_cursor_alpha}", exc_info=True)
                pixmap_for_cursor = QPixmap(max(1, original_w), max(1, original_h))
                if not pixmap_for_cursor.isNull(): pixmap_for_cursor.fill(fallback_qcolor_blue)
                else: pixmap_for_cursor = QPixmap() 
        else:
            pixmap_for_cursor = QPixmap(max(1, original_w), max(1, original_h))
            if not pixmap_for_cursor.isNull(): pixmap_for_cursor.fill(fallback_qcolor_blue)
            else: pixmap_for_cursor = QPixmap()
        
        asset_data_entry["q_pixmap_cursor"] = pixmap_for_cursor
        editor_state.assets_palette[asset_key] = asset_data_entry

        if intended_pixmap_created_successfully: successful_loads += 1
        else: failed_loads += 1

    logger.info(f"Palette asset loading complete. Success: {successful_loads}, Failed/Fallback: {failed_loads}.")

#################### END OF FILE: editor_assets.py ####################