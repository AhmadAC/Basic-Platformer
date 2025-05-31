# editor/editor_assets.py
# -*- coding: utf-8 -*-
"""
## version 2.1.10 (Fixed asset_editor_key not defined in _create_icon_pixmap)
Handles loading and managing assets for the editor's palette using PySide6.
- Verified compatibility with refactored asset paths (e.g., "assets/category/file.ext")
  provided by ED_CONFIG, resolved via resource_path.
- Includes placeholder icon generation for trigger squares.
- get_asset_pixmap correctly handles absolute source_file paths (custom assets)
  and relative paths (palette assets) via resource_path.
- Includes rotation and flip support in get_asset_pixmap.
- Added 'select_cursor_icon' case to _create_icon_pixmap.
- Implemented `render_as_rotated_segment` for specific tile assets.
"""
import os
import sys
import logging
from typing import Optional, Dict, Any, Tuple, List, Union

from PySide6.QtGui import QPixmap, QImage, QPainter, QColor, QPen, QImageReader, QBrush, QTransform,QPainterPath, QFont
from PySide6.QtCore import QRectF, QPointF, QSize, Qt, QSizeF
from PySide6.QtWidgets import QApplication

_EDITOR_ASSETS_DIR = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
_PROJECT_ROOT_FROM_EDITOR_ASSETS = os.path.dirname(_EDITOR_ASSETS_DIR)
if _PROJECT_ROOT_FROM_EDITOR_ASSETS not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT_FROM_EDITOR_ASSETS)

logger = logging.getLogger(__name__)

try:
    from main_game.assets import resource_path
    logger.info("EditorAssets: Imported 'resource_path' from 'main_game.assets'.")
except ImportError:
    logger.warning("EditorAssets: Could not import 'resource_path' from 'main_game.assets'. Using fallback resource_path.")
    def resource_path(relative_path: str) -> str:
        return os.path.join(_PROJECT_ROOT_FROM_EDITOR_ASSETS, relative_path)

from editor import editor_config as ED_CONFIG
from editor.editor_state import EditorState

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
        else: logger.warning(f"_create_half_tile_pixmap: Unknown half_type '{half_type}'.")
        if not rect_to_draw.isNull() and rect_to_draw.isValid():
            painter.drawRect(rect_to_draw)
        else:
            logger.warning(f"_create_half_tile_pixmap: rect_to_draw is null or invalid for half_type '{half_type}'.")
    finally:
        painter.end()
    return pixmap

# Modified signature to include asset_editor_key
def _create_icon_pixmap(base_size: int, icon_type: str, color_tuple_rgba: Tuple[int,int,int, Optional[int]], asset_editor_key_for_icon: str) -> QPixmap:
    safe_base_size = max(1, base_size)
    pixmap = QPixmap(safe_base_size, safe_base_size)
    if pixmap.isNull():
        logger.error(f"_create_icon_pixmap: QPixmap is null for size {safe_base_size}x{safe_base_size}. Returning empty pixmap.")
        return QPixmap()
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter()
    if not painter.begin(pixmap):
        logger.error(f"_create_icon_pixmap: QPainter.begin() failed for pixmap size {safe_base_size}x{safe_base_size}. Pixmap might be invalid.")
        return pixmap
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        s = float(safe_base_size)
        if len(color_tuple_rgba) == 4 and color_tuple_rgba[3] is not None:
            icon_qcolor = QColor(color_tuple_rgba[0], color_tuple_rgba[1], color_tuple_rgba[2], color_tuple_rgba[3])
        else:
            icon_qcolor = QColor(color_tuple_rgba[0], color_tuple_rgba[1], color_tuple_rgba[2], 255)
        border_qcolor = QColor(Qt.GlobalColor.black)

        if icon_type == "select_cursor_icon":
            painter.setPen(QPen(icon_qcolor, 2)); painter.setBrush(Qt.BrushStyle.NoBrush)
            path = QPainterPath()
            path.moveTo(s * 0.2, s * 0.2); path.lineTo(s * 0.2, s * 0.8); path.lineTo(s * 0.4, s * 0.65)
            path.lineTo(s * 0.65, s * 0.9); path.lineTo(s * 0.75, s * 0.8); path.lineTo(s * 0.55, s * 0.6)
            path.lineTo(s * 0.8, s * 0.2); path.closeSubpath()          
            painter.fillPath(path, icon_qcolor); painter.drawPath(path)
        elif icon_type == "2x2_placer":
            rect_size = s * 0.35; gap = s * 0.1
            painter.setBrush(icon_qcolor); painter.setPen(border_qcolor)
            painter.drawRect(QRectF(gap, gap, rect_size, rect_size)); painter.drawRect(QRectF(s - gap - rect_size, gap, rect_size, rect_size))
            painter.drawRect(QRectF(gap, s - gap - rect_size, rect_size, rect_size)); painter.drawRect(QRectF(s - gap - rect_size, s - gap - rect_size, rect_size, rect_size))
        elif icon_type == "eraser":
            painter.setBrush(icon_qcolor); painter.setPen(border_qcolor)
            painter.drawRect(QRectF(s * 0.1, s * 0.3, s * 0.8, s * 0.4))
            pen = QPen(border_qcolor, 2); pen.setCapStyle(Qt.PenCapStyle.RoundCap); painter.setPen(pen)
            painter.drawLine(QPointF(s*0.25, s*0.25), QPointF(s*0.75, s*0.75)); painter.drawLine(QPointF(s*0.25, s*0.75), QPointF(s*0.75, s*0.25))
        elif icon_type == "color_swatch":
            painter.setBrush(icon_qcolor); painter.setPen(border_qcolor); painter.drawRect(QRectF(s*0.1, s*0.1, s*0.8, s*0.8))
        elif icon_type == "generic_square_icon":
            painter.setBrush(QBrush(icon_qcolor)); painter.setPen(QPen(border_qcolor, 1))
            inner_rect = QRectF(s * 0.15, s * 0.15, s * 0.7, s * 0.7); painter.drawRect(inner_rect)
            text_color = Qt.GlobalColor.black if icon_qcolor.lightnessF() > 0.5 else Qt.GlobalColor.white
            if icon_qcolor.alphaF() < 0.3: text_color = Qt.GlobalColor.black
            painter.setPen(text_color); font = painter.font(); font.setPointSize(int(s * 0.35)); font.setBold(True); painter.setFont(font)
            
            text_to_draw = "TRG" # Default
            if asset_editor_key_for_icon == ED_CONFIG.INVISIBLE_WALL_ASSET_KEY_PALETTE: # Use passed key
                text_to_draw = "INV"
            elif asset_editor_key_for_icon == ED_CONFIG.TRIGGER_SQUARE_ASSET_KEY: # Use passed key
                text_to_draw = "TRG"
            # Add other conditions if needed for different text on generic icons
            painter.drawText(inner_rect, Qt.AlignmentFlag.AlignCenter, text_to_draw)
        else:
            logger.warning(f"_create_icon_pixmap: Unknown icon_type '{icon_type}'. Drawing '?'")
            painter.setPen(icon_qcolor); font = painter.font(); font.setPointSize(int(s * 0.6)); font.setBold(True); painter.setFont(font)
            painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "?")
    finally:
        painter.end()
    return pixmap


def get_asset_pixmap(asset_editor_key: str,
                     asset_data_entry: Dict[str, Any],
                     requested_target_size: Union[QSize, QSizeF],
                     override_color: Optional[Tuple[int,int,int]] = None,
                     get_native_size_only: bool = False,
                     is_flipped_h: bool = False,
                     rotation: int = 0) -> Optional[QPixmap]:
    
    initial_native_pixmap: Optional[QPixmap] = None
    ts = float(ED_CONFIG.BASE_GRID_SIZE)
    color_to_use_tuple = override_color
    if not color_to_use_tuple and asset_data_entry.get("colorable"):
        color_to_use_tuple = asset_data_entry.get("base_color_tuple")
        if not color_to_use_tuple:
            surface_params_val = asset_data_entry.get("surface_params")
            if surface_params_val and isinstance(surface_params_val, tuple) and len(surface_params_val) == 3:
                color_to_use_tuple = surface_params_val[2]

    source_file_path = asset_data_entry.get("source_file")

    if source_file_path:
        full_path_resolved = resource_path(source_file_path) if not os.path.isabs(source_file_path) else source_file_path
        full_path_norm = os.path.normpath(full_path_resolved)
        if not os.path.exists(full_path_norm): logger.error(f"File NOT FOUND: '{full_path_norm}' for asset '{asset_editor_key}'")
        else:
            reader = QImageReader(full_path_norm)
            if source_file_path.lower().endswith(".gif"): reader.setFormat(b"gif")
            if reader.canRead():
                image_from_reader: QImage = reader.read()
                if not image_from_reader.isNull(): initial_native_pixmap = QPixmap.fromImage(image_from_reader)
                else: logger.error(f"QImageReader.read() returned null for '{full_path_norm}'. Reader error: {reader.errorString()}")
            else: logger.error(f"QImageReader cannot read '{full_path_norm}'. Reader error: {reader.errorString()}")
            if initial_native_pixmap and not initial_native_pixmap.isNull() and color_to_use_tuple and asset_data_entry.get("colorable"):
                try:
                    temp_image = initial_native_pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
                    painter = QPainter();
                    if painter.begin(temp_image):
                        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                        painter.fillRect(temp_image.rect(), QColor(*color_to_use_tuple)); painter.end()
                        initial_native_pixmap = QPixmap.fromImage(temp_image)
                    else: logger.error(f"Failed to begin painter for colorizing '{asset_editor_key}'")
                except Exception as e_colorize: logger.error(f"Error colorizing '{asset_editor_key}': {e_colorize}", exc_info=True)
    elif "surface_params" in asset_data_entry and asset_data_entry.get("render_mode") is None and asset_data_entry.get("icon_type") is None:
        params = asset_data_entry["surface_params"]
        if params and isinstance(params, tuple) and len(params) == 3:
            w_int, h_int = int(params[0]), int(params[1]); default_color_tuple = params[2]
            initial_native_pixmap = _create_colored_pixmap(w_int, h_int, color_to_use_tuple or default_color_tuple)
    elif "render_mode" in asset_data_entry and asset_data_entry["render_mode"] == "half_tile":
        half_type = asset_data_entry.get("half_type", "left")
        default_color_proc = asset_data_entry.get("base_color_tuple", getattr(ED_CONFIG.C, 'MAGENTA', (255,0,255)))
        initial_native_pixmap = _create_half_tile_pixmap(int(ts), half_type, color_to_use_tuple or default_color_proc)
    elif "icon_type" in asset_data_entry:
        icon_type_str = asset_data_entry["icon_type"]
        default_color_icon_rgba = asset_data_entry.get("base_color_tuple", (*getattr(ED_CONFIG.C, 'YELLOW', (255,255,0)), 255) )
        effective_color_rgba: Tuple[int,int,int,Optional[int]] = (*color_to_use_tuple, default_color_icon_rgba[3]) if color_to_use_tuple else default_color_icon_rgba
        initial_native_pixmap = _create_icon_pixmap(int(ts), icon_type_str, effective_color_rgba, asset_editor_key) # Pass asset_editor_key
    
    target_qsize_fallback: QSize = requested_target_size.toSize() if isinstance(requested_target_size, QSizeF) else requested_target_size
    if not initial_native_pixmap or initial_native_pixmap.isNull():
        fb_w = target_qsize_fallback.width() if target_qsize_fallback.width() > 0 else int(ED_CONFIG.ASSET_THUMBNAIL_SIZE)
        fb_h = target_qsize_fallback.height() if target_qsize_fallback.height() > 0 else int(ED_CONFIG.ASSET_THUMBNAIL_SIZE)
        fb_pm = QPixmap(max(1, fb_w), max(1, fb_h))
        if fb_pm.isNull(): logger.error(f"Fallback pixmap for '{asset_editor_key}' ALSO NULL. Size: {fb_w}x{fb_h}"); return QPixmap()
        fb_pm.fill(QColor(*getattr(ED_CONFIG.C, 'RED', (255,0,0))))
        painter_fb = QPainter()
        if painter_fb.begin(fb_pm):
            try: painter_fb.setPen(QColor(Qt.GlobalColor.black)); painter_fb.drawLine(0,0, fb_pm.width()-1, fb_pm.height()-1); painter_fb.drawLine(0,fb_pm.height()-1, fb_pm.width()-1, 0)
            finally: painter_fb.end()
        else: logger.error(f"Failed painter on fallback for {asset_editor_key}")
        initial_native_pixmap = fb_pm
    
    transformed_pixmap = initial_native_pixmap 
    if (is_flipped_h or rotation != 0) and initial_native_pixmap and not initial_native_pixmap.isNull():
        img_to_transform = initial_native_pixmap.toImage()
        if not img_to_transform.isNull():
            if is_flipped_h: img_to_transform = img_to_transform.mirrored(True, False)
            if rotation != 0 and not img_to_transform.isNull():
                center_pt = QPointF(img_to_transform.width() / 2.0, img_to_transform.height() / 2.0)
                xform = QTransform().translate(center_pt.x(), center_pt.y()).rotate(float(rotation)).translate(-center_pt.x(), -center_pt.y())
                img_to_transform = img_to_transform.transformed(xform, Qt.TransformationMode.SmoothTransformation)
            if not img_to_transform.isNull(): transformed_pixmap = QPixmap.fromImage(img_to_transform)
            else: logger.error(f"Image became null after transform for '{asset_editor_key}'")
        else: logger.error(f"Failed to convert to image for transform: '{asset_editor_key}'")

    if get_native_size_only:
        return transformed_pixmap 

    final_pixmap_for_display = transformed_pixmap
    target_display_qsize: QSize = requested_target_size.toSize() if isinstance(requested_target_size, QSizeF) else requested_target_size

    if asset_data_entry.get("render_as_rotated_segment") and transformed_pixmap and not transformed_pixmap.isNull():
        canvas_qsize = QSize(target_display_qsize) 
        if canvas_qsize.width() <= 0 or canvas_qsize.height() <= 0:
            canvas_qsize = QSize(ED_CONFIG.ASSET_THUMBNAIL_SIZE, ED_CONFIG.ASSET_THUMBNAIL_SIZE)
        composed_canvas = QPixmap(canvas_qsize)
        composed_canvas.fill(Qt.GlobalColor.transparent)
        painter = QPainter(composed_canvas)
        seg_w, seg_h = float(transformed_pixmap.width()), float(transformed_pixmap.height())
        can_w, can_h = float(canvas_qsize.width()), float(canvas_qsize.height())
        px, py = 0.0, 0.0
        if rotation == 0: px = (can_w - seg_w) / 2.0; py = 0.0                           
        elif rotation == 90: px = can_w - seg_w; py = (can_h - seg_h) / 2.0             
        elif rotation == 180: px = (can_w - seg_w) / 2.0; py = can_h - seg_h            
        elif rotation == 270: px = 0.0; py = (can_h - seg_h) / 2.0                      
        painter.drawPixmap(QPointF(px, py), transformed_pixmap); painter.end()
        final_pixmap_for_display = composed_canvas
    
    if final_pixmap_for_display and final_pixmap_for_display.size() != target_display_qsize and \
       target_display_qsize.isValid() and target_display_qsize.width() > 0 and target_display_qsize.height() > 0:
        return final_pixmap_for_display.scaled(target_display_qsize, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    
    return final_pixmap_for_display


def load_editor_palette_assets(editor_state: EditorState, main_window_ref: Optional[Any] = None):
    editor_state.assets_palette.clear()
    if QApplication.instance() is None and main_window_ref is None:
        logger.critical("QApplication not instantiated, and no main_window_ref provided before load_editor_palette_assets!")

    logger.info("Loading editor palette assets for Qt...")
    successful_loads = 0; failed_loads = 0
    target_thumb_qsize = QSize(int(ED_CONFIG.ASSET_THUMBNAIL_SIZE), int(ED_CONFIG.ASSET_THUMBNAIL_SIZE))
    ts_float = float(ED_CONFIG.BASE_GRID_SIZE)
    fallback_qcolor_red = QColor(*getattr(ED_CONFIG.C, 'RED', (255,0,0)))
    fallback_qcolor_blue = QColor(*getattr(ED_CONFIG.C, 'BLUE', (0,0,255)))

    for asset_key, asset_info_def in ED_CONFIG.EDITOR_PALETTE_ASSETS.items():
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
            "icon_type": asset_info_def.get("icon_type"),
            "render_as_rotated_segment": asset_info_def.get("render_as_rotated_segment", False)
        }
        original_w_float, original_h_float = ts_float, ts_float
        native_pixmap_for_size_determination = get_asset_pixmap(
            asset_key, asset_data_entry, QSize(1, 1), override_color=None, 
            get_native_size_only=True, is_flipped_h=False, rotation=0 
        )
        if native_pixmap_for_size_determination and not native_pixmap_for_size_determination.isNull():
            original_w_float = float(native_pixmap_for_size_determination.width())
            original_h_float = float(native_pixmap_for_size_determination.height())
        elif "surface_params" in asset_info_def:
            params = asset_info_def["surface_params"]
            if params and isinstance(params, tuple) and len(params) >= 2:
                original_w_float, original_h_float = float(params[0]), float(params[1])
        asset_data_entry["original_size_pixels"] = (original_w_float, original_h_float)
        
        pixmap_for_palette = get_asset_pixmap(asset_key, asset_data_entry, target_thumb_qsize,
                                              get_native_size_only=False, is_flipped_h=False, rotation=0)
                                              
        intended_pixmap_created_successfully = False
        if pixmap_for_palette and not pixmap_for_palette.isNull():
            is_fallback_red_check_img = pixmap_for_palette.toImage()
            if not is_fallback_red_check_img.isNull():
                is_fallback_red = (pixmap_for_palette.size() == target_thumb_qsize and
                                   is_fallback_red_check_img.pixelColor(0,0) == fallback_qcolor_red and
                                   is_fallback_red_check_img.pixelColor(pixmap_for_palette.width()-1, 0) == fallback_qcolor_red)
                if not is_fallback_red: intended_pixmap_created_successfully = True
            else: logger.warning(f"Pixmap toImage() failed for palette asset '{asset_key}' during success check.")
        
        if not pixmap_for_palette or pixmap_for_palette.isNull():
            fb_w_thumb = target_thumb_qsize.width() if target_thumb_qsize.width() > 0 else int(ED_CONFIG.ASSET_THUMBNAIL_SIZE)
            fb_h_thumb = target_thumb_qsize.height() if target_thumb_qsize.height() > 0 else int(ED_CONFIG.ASSET_THUMBNAIL_SIZE)
            pixmap_for_palette = QPixmap(max(1, fb_w_thumb), max(1, fb_h_thumb))
            if pixmap_for_palette.isNull(): pixmap_for_palette = QPixmap()
            else: pixmap_for_palette.fill(fallback_qcolor_red)
        asset_data_entry["q_pixmap"] = pixmap_for_palette
        
        cursor_base_pixmap_native = get_asset_pixmap(
            asset_key, asset_data_entry, 
            QSize(int(max(1.0, original_w_float)), int(max(1.0, original_h_float))),
            override_color=None, get_native_size_only=True, is_flipped_h=False, rotation=0
        )
        pixmap_for_cursor: Optional[QPixmap] = None
        if cursor_base_pixmap_native and not cursor_base_pixmap_native.isNull():
            try:
                img_for_cursor_alpha = cursor_base_pixmap_native.toImage().convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
                if img_for_cursor_alpha.isNull() or img_for_cursor_alpha.width() == 0 or img_for_cursor_alpha.height() == 0:
                    cursor_fb_w, cursor_fb_h = int(max(1.0, original_w_float)), int(max(1.0, original_h_float))
                    pixmap_for_cursor = QPixmap(cursor_fb_w, cursor_fb_h); pixmap_for_cursor.fill(fallback_qcolor_blue)
                else:
                    cursor_image_with_alpha = QImage(img_for_cursor_alpha.size(), QImage.Format.Format_ARGB32_Premultiplied)
                    cursor_image_with_alpha.fill(Qt.GlobalColor.transparent)
                    painter_cursor = QPainter();
                    if painter_cursor.begin(cursor_image_with_alpha):
                        try: painter_cursor.setOpacity(float(ED_CONFIG.CURSOR_ASSET_ALPHA) / 255.0); painter_cursor.drawImage(0, 0, img_for_cursor_alpha)
                        finally: painter_cursor.end()
                        pixmap_for_cursor = QPixmap.fromImage(cursor_image_with_alpha)
                        if pixmap_for_cursor.isNull():
                            cursor_fb_w, cursor_fb_h = int(max(1.0, original_w_float)), int(max(1.0, original_h_float))
                            pixmap_for_cursor = QPixmap(cursor_fb_w, cursor_fb_h); pixmap_for_cursor.fill(fallback_qcolor_blue)
                    else: 
                        cursor_fb_w, cursor_fb_h = int(max(1.0, original_w_float)), int(max(1.0, original_h_float))
                        pixmap_for_cursor = QPixmap(cursor_fb_w, cursor_fb_h); pixmap_for_cursor.fill(fallback_qcolor_blue)
            except Exception as e_cursor_alpha:
                logger.error(f"Error applying alpha to cursor for '{asset_key}': {e_cursor_alpha}", exc_info=True)
                cursor_fb_w, cursor_fb_h = int(max(1.0, original_w_float)), int(max(1.0, original_h_float))
                pixmap_for_cursor = QPixmap(cursor_fb_w, cursor_fb_h); pixmap_for_cursor.fill(fallback_qcolor_blue)
        else: 
            cursor_fb_w, cursor_fb_h = int(max(1.0, original_w_float)), int(max(1.0, original_h_float))
            pixmap_for_cursor = QPixmap(cursor_fb_w, cursor_fb_h); pixmap_for_cursor.fill(fallback_qcolor_blue)
        asset_data_entry["q_pixmap_cursor"] = pixmap_for_cursor if pixmap_for_cursor else QPixmap()
        
        editor_state.assets_palette[asset_key] = asset_data_entry
        if intended_pixmap_created_successfully: successful_loads += 1
        else: failed_loads += 1
    logger.info(f"Palette asset loading complete. Success: {successful_loads}, Failed/Fallback: {failed_loads}.")