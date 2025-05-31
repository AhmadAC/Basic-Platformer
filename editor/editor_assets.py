# editor/editor_assets.py
# -*- coding: utf-8 -*-
"""
## version 2.1.3 (Corrected typo _scaled_image_cache to _image_scaled_for_render)
Handles loading and managing assets for the editor's palette using PySide6.
- Verified compatibility with refactored asset paths (e.g., "assets/category/file.ext")
  provided by ED_CONFIG, resolved via resource_path.
- Includes placeholder icon generation for trigger squares.
- get_asset_pixmap correctly handles absolute source_file paths (custom assets)
  and relative paths (palette assets) via resource_path.
- Includes rotation and flip support in get_asset_pixmap.
"""
import os
import sys
import logging
from typing import Optional, Dict, Any, Tuple, List

from PySide6.QtGui import QPixmap, QImage, QPainter, QColor, QPen, QImageReader, QBrush, QTransform
from PySide6.QtCore import QRectF, QPointF, QSize, Qt, QSizeF # Added QSizeF
from PySide6.QtWidgets import QApplication

# --- Sys.path manipulation for robust imports ---
_EDITOR_ASSETS_DIR = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
_PROJECT_ROOT_FROM_EDITOR_ASSETS = os.path.dirname(_EDITOR_ASSETS_DIR)
if _PROJECT_ROOT_FROM_EDITOR_ASSETS not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT_FROM_EDITOR_ASSETS)

logger = logging.getLogger(__name__)

try:
    from main_game.assets import resource_path # Assuming assets.py is in main_game now
    logger.info("EditorAssets: Imported 'resource_path' from 'main_game.assets'.")
except ImportError:
    logger.warning("EditorAssets: Could not import 'resource_path' from 'main_game.assets'. Using fallback resource_path.")
    def resource_path(relative_path: str) -> str:
        # Fallback assumes this script (editor_assets.py) is in editor/,
        # so _PROJECT_ROOT_FROM_EDITOR_ASSETS is the project root.
        return os.path.join(_PROJECT_ROOT_FROM_EDITOR_ASSETS, relative_path)

from . import editor_config as ED_CONFIG
from .editor_state import EditorState # For type hinting if needed, though not directly used in this version

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
        return pixmap # Return the transparent pixmap

    try:
        painter.setBrush(QColor(*color_tuple))
        painter.setPen(Qt.GlobalColor.transparent) # No border for the half tile itself
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

def _create_icon_pixmap(base_size: int, icon_type: str, color_tuple_rgba: Tuple[int,int,int, Optional[int]]) -> QPixmap:
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
        else: # Assume full alpha if not specified
            icon_qcolor = QColor(color_tuple_rgba[0], color_tuple_rgba[1], color_tuple_rgba[2], 255)

        border_qcolor = QColor(Qt.GlobalColor.black) # Default border color

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
            pen = QPen(border_qcolor, 2); pen.setCapStyle(Qt.PenCapStyle.RoundCap); painter.setPen(pen)
            painter.drawLine(QPointF(s*0.25, s*0.25), QPointF(s*0.75, s*0.75)) # Cross lines
            painter.drawLine(QPointF(s*0.25, s*0.75), QPointF(s*0.75, s*0.25))
        elif icon_type == "color_swatch":
            painter.setBrush(icon_qcolor); painter.setPen(border_qcolor)
            painter.drawRect(QRectF(s*0.1, s*0.1, s*0.8, s*0.8))
        elif icon_type == "generic_square_icon": # For Trigger Square
            painter.setBrush(QBrush(icon_qcolor)) # Brush uses the icon_qcolor (which includes alpha)
            painter.setPen(QPen(border_qcolor, 1))
            inner_rect = QRectF(s * 0.15, s * 0.15, s * 0.7, s * 0.7)
            painter.drawRect(inner_rect)
            # Determine text color based on background lightness and alpha
            text_color = Qt.GlobalColor.black if icon_qcolor.lightnessF() > 0.5 else Qt.GlobalColor.white
            if icon_qcolor.alphaF() < 0.3: # If very transparent, use black text for visibility
                 text_color = Qt.GlobalColor.black
            painter.setPen(text_color)
            font = painter.font(); font.setPointSize(int(s * 0.35)); font.setBold(True); painter.setFont(font)
            painter.drawText(inner_rect, Qt.AlignmentFlag.AlignCenter, "TRG")
        else: # Default fallback for unknown icon_type
            logger.warning(f"_create_icon_pixmap: Unknown icon_type '{icon_type}'. Drawing '?'")
            painter.setPen(icon_qcolor) # Use the icon's color for the '?'
            font = painter.font(); font.setPointSize(int(s * 0.6)); font.setBold(True); painter.setFont(font)
            painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "?")
    finally:
        painter.end()
    return pixmap


def get_asset_pixmap(asset_editor_key: str,
                     asset_data_entry: Dict[str, Any],
                     requested_target_size_qsizef: QSizeF, # Changed to QSizeF for float precision
                     override_color: Optional[Tuple[int,int,int]] = None,
                     get_native_size_only: bool = False,
                     is_flipped_h: bool = False,
                     rotation: int = 0) -> Optional[QPixmap]: # Can return None on critical failure
    native_pixmap: Optional[QPixmap] = None
    ts = float(ED_CONFIG.BASE_GRID_SIZE) # Ensure ts is float

    color_to_use_tuple = override_color
    # Determine effective color for colorable assets
    if not color_to_use_tuple and asset_data_entry.get("colorable"):
        color_to_use_tuple = asset_data_entry.get("base_color_tuple")
        # Fallback to surface_params color if base_color_tuple is missing
        if not color_to_use_tuple:
            surface_params_val = asset_data_entry.get("surface_params")
            if surface_params_val and isinstance(surface_params_val, tuple) and len(surface_params_val) == 3:
                color_to_use_tuple = surface_params_val[2]

    source_file_path = asset_data_entry.get("source_file")

    if source_file_path:
        # resource_path handles making it absolute if needed.
        # For custom assets, source_file_path is already absolute (set by editor_map_utils).
        # For palette assets, it's relative to project root (e.g., "assets/category/file.gif").
        full_path_resolved = resource_path(source_file_path) if not os.path.isabs(source_file_path) else source_file_path
        full_path_norm = os.path.normpath(full_path_resolved)

        if not os.path.exists(full_path_norm):
            logger.error(f"File NOT FOUND: '{full_path_norm}' for asset '{asset_editor_key}'")
        else:
            reader = QImageReader(full_path_norm)
            if source_file_path.lower().endswith(".gif"): reader.setFormat(b"gif")

            if reader.canRead():
                image_from_reader: QImage = reader.read() # Reads the first frame for GIFs, or whole image for PNG/JPG
                if not image_from_reader.isNull():
                    native_pixmap = QPixmap.fromImage(image_from_reader)
                    if native_pixmap.isNull():
                        logger.error(f"QPixmap.fromImage failed for '{full_path_norm}'. Reader error: {reader.errorString()}")
                else:
                    logger.error(f"QImageReader.read() returned null for '{full_path_norm}'. Reader error: {reader.errorString()}")
            else:
                logger.error(f"QImageReader cannot read '{full_path_norm}'. Reader error: {reader.errorString()}")

            # Apply color tint if applicable
            if native_pixmap and not native_pixmap.isNull() and color_to_use_tuple and asset_data_entry.get("colorable"):
                try:
                    temp_image = native_pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
                    painter = QPainter()
                    if painter.begin(temp_image):
                        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                        painter.fillRect(temp_image.rect(), QColor(*color_to_use_tuple))
                        painter.end()
                        native_pixmap = QPixmap.fromImage(temp_image)
                    else: logger.error(f"Failed to begin painter for colorizing '{asset_editor_key}'")
                except Exception as e_colorize: logger.error(f"Error colorizing '{asset_editor_key}': {e_colorize}", exc_info=True)

    # --- Procedural asset generation ---
    elif "surface_params" in asset_data_entry and asset_data_entry.get("render_mode") is None and asset_data_entry.get("icon_type") is None:
        params = asset_data_entry["surface_params"]
        if params and isinstance(params, tuple) and len(params) == 3:
            w_int, h_int = int(params[0]), int(params[1])
            default_color_tuple = params[2]
            native_pixmap = _create_colored_pixmap(w_int, h_int, color_to_use_tuple or default_color_tuple)
    elif "render_mode" in asset_data_entry and asset_data_entry["render_mode"] == "half_tile":
        half_type = asset_data_entry.get("half_type", "left")
        default_color_proc = asset_data_entry.get("base_color_tuple", getattr(ED_CONFIG.C, 'MAGENTA', (255,0,255)))
        native_pixmap = _create_half_tile_pixmap(int(ts), half_type, color_to_use_tuple or default_color_proc)
    elif "icon_type" in asset_data_entry:
        icon_type_str = asset_data_entry["icon_type"]
        default_color_icon_with_alpha_rgba = asset_data_entry.get("base_color_tuple", (*getattr(ED_CONFIG.C, 'YELLOW', (255,255,0)), 255) )
        # Ensure color_to_use_tuple (if override) has alpha for icon, or use default with alpha
        effective_color_for_icon_rgba: Tuple[int,int,int,Optional[int]]
        if color_to_use_tuple: # Override exists
             effective_color_for_icon_rgba = (*color_to_use_tuple, default_color_icon_with_alpha_rgba[3]) # Use override RGB, default alpha
        else: effective_color_for_icon_rgba = default_color_icon_with_alpha_rgba
        native_pixmap = _create_icon_pixmap(int(ts), icon_type_str, effective_color_for_icon_rgba)

    # --- Fallback if native_pixmap is still None or Null ---
    if not native_pixmap or native_pixmap.isNull():
        logger.warning(f"Native pixmap for '{asset_editor_key}' failed or is null. Creating RED fallback.")
        target_qsize = requested_target_size_qsizef.toSize()
        fb_w = target_qsize.width() if target_qsize.width() > 0 else int(ED_CONFIG.ASSET_THUMBNAIL_SIZE)
        fb_h = target_qsize.height() if target_qsize.height() > 0 else int(ED_CONFIG.ASSET_THUMBNAIL_SIZE)

        fallback_pixmap = QPixmap(max(1, fb_w), max(1, fb_h))
        if fallback_pixmap.isNull():
            logger.error(f"Fallback pixmap for '{asset_editor_key}' is ALSO NULL. Size: {fb_w}x{fb_h}")
            return QPixmap() # Return an empty (but valid) QPixmap to avoid crashing consumers

        fallback_pixmap.fill(QColor(*getattr(ED_CONFIG.C, 'RED', (255,0,0))))
        painter = QPainter()
        if painter.begin(fallback_pixmap):
            try:
                painter.setPen(QColor(Qt.GlobalColor.black))
                painter.drawLine(0,0, fallback_pixmap.width()-1, fallback_pixmap.height()-1)
                painter.drawLine(0,fallback_pixmap.height()-1, fallback_pixmap.width()-1, 0)
            finally: painter.end()
        else: logger.error(f"Failed to begin painter on fallback pixmap for {asset_editor_key}")
        native_pixmap = fallback_pixmap # Use this fallback as the native_pixmap for further processing

    # --- Apply Transformations (Flip, Rotation) to the native_pixmap ---
    if (is_flipped_h or rotation != 0) and native_pixmap and not native_pixmap.isNull():
        temp_img = native_pixmap.toImage()
        if not temp_img.isNull():
            if is_flipped_h:
                temp_img = temp_img.mirrored(True, False)
                if temp_img.isNull(): logger.error(f"Failed to mirror image for '{asset_editor_key}'")

            if rotation != 0 and not temp_img.isNull(): # Apply rotation to potentially flipped image
                img_center = QPointF(temp_img.width() / 2.0, temp_img.height() / 2.0)
                transform = QTransform().translate(img_center.x(), img_center.y()).rotate(float(rotation)).translate(-img_center.x(), -img_center.y())
                rotated_img = temp_img.transformed(transform, Qt.TransformationMode.SmoothTransformation)
                if not rotated_img.isNull(): temp_img = rotated_img
                else: logger.error(f"Failed to rotate image for '{asset_editor_key}'")

            if not temp_img.isNull(): native_pixmap = QPixmap.fromImage(temp_img)
            else: logger.error(f"Image became null after transformations for '{asset_editor_key}'")
        else: logger.error(f"Failed to convert pixmap to image for transformations for '{asset_editor_key}'")

    # --- Handle get_native_size_only ---
    if get_native_size_only:
        orig_size_data = asset_data_entry.get("original_size_pixels")
        if orig_size_data and isinstance(orig_size_data, tuple) and len(orig_size_data) == 2 and native_pixmap:
            target_native_w_float, target_native_h_float = float(orig_size_data[0]), float(orig_size_data[1])
            
            # Account for rotation swapping dimensions
            effective_target_w_float, effective_target_h_float = target_native_w_float, target_native_h_float
            if rotation % 180 != 0:
                effective_target_w_float, effective_target_h_float = target_native_h_float, target_native_w_float
            
            # If current pixmap size doesn't match the (potentially rotated) original_size_pixels, scale it.
            # This is mainly for procedural assets whose native_pixmap might be 'ts' but original_size_pixels is different.
            if abs(native_pixmap.width() - effective_target_w_float) > 1e-3 or \
               abs(native_pixmap.height() - effective_target_h_float) > 1e-3:
                 if effective_target_w_float > 0 and effective_target_h_float > 0:
                    return native_pixmap.scaled(int(effective_target_w_float), int(effective_target_h_float),
                                                Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        return native_pixmap # Return (potentially transformed and native-sized) pixmap

    # --- Scale to requested_target_size if not getting native only ---
    target_qsize_for_scaling = requested_target_size_qsizef.toSize() # Convert QSizeF to QSize
    if native_pixmap and native_pixmap.size() != target_qsize_for_scaling and \
       target_qsize_for_scaling.isValid() and target_qsize_for_scaling.width() > 0 and target_qsize_for_scaling.height() > 0 :
        scaled_pixmap = native_pixmap.scaled(target_qsize_for_scaling, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        return scaled_pixmap
    else:
        return native_pixmap # Return if already correct size or if target size is invalid


def load_editor_palette_assets(editor_state: EditorState, main_window_ref: Optional[Any] = None):
    """
    Loads assets defined in ED_CONFIG.EDITOR_PALETTE_ASSETS into the editor_state.
    Creates QPixmaps for palette display and cursor preview.
    """
    editor_state.assets_palette.clear()
    if QApplication.instance() is None and main_window_ref is None:
        logger.critical("QApplication not instantiated, and no main_window_ref provided before load_editor_palette_assets!")
        # If this happens, QPixmap creation will likely fail.
        # For robust testing, a QApplication instance might be needed.

    logger.info("Loading editor palette assets for Qt...")
    successful_loads = 0; failed_loads = 0
    # Convert to QSizeF for get_asset_pixmap
    target_thumb_size_qsizef = QSizeF(float(ED_CONFIG.ASSET_THUMBNAIL_SIZE), float(ED_CONFIG.ASSET_THUMBNAIL_SIZE))
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
            "icon_type": asset_info_def.get("icon_type")
        }

        original_w_float, original_h_float = ts_float, ts_float # Default original size

        # Determine original_size_pixels (native size before transformations)
        # For get_native_size_only, requested_target_size is used for scaling procedural assets to their defined original_size_pixels
        # For image assets, it should return the image's natural dimensions.
        native_pixmap_for_size_determination = get_asset_pixmap(
            asset_key, asset_data_entry,
            QSizeF(1.0, 1.0), # Dummy target size, not strictly used if get_native_size_only finds image's own size
            override_color=None,
            get_native_size_only=True,
            is_flipped_h=False, rotation=0 # No transforms for native size check
        )
        if native_pixmap_for_size_determination and not native_pixmap_for_size_determination.isNull():
            original_w_float, original_h_float = float(native_pixmap_for_size_determination.width()), float(native_pixmap_for_size_determination.height())
        elif "surface_params" in asset_info_def: # For procedural tiles not from files
            params = asset_info_def["surface_params"]
            if params and isinstance(params, tuple) and len(params) >= 2:
                original_w_float, original_h_float = float(params[0]), float(params[1])
        asset_data_entry["original_size_pixels"] = (original_w_float, original_h_float)

        # Get the pixmap for the palette (thumbnail size, no transforms yet applied here)
        pixmap_for_palette = get_asset_pixmap(asset_key, asset_data_entry, target_thumb_size_qsizef,
                                              get_native_size_only=False, is_flipped_h=False, rotation=0)

        intended_pixmap_created_successfully = False
        if pixmap_for_palette and not pixmap_for_palette.isNull():
            # Check if it's likely our fallback by looking at common fallback color/size
            is_fallback_red_check_img = pixmap_for_palette.toImage()
            if not is_fallback_red_check_img.isNull():
                # A more robust fallback check would be to see if it matches the _create_error_placeholder output for this size.
                # For now, check if its pixel matches the RED fallback color AND size matches thumbnail target
                is_fallback_red = (pixmap_for_palette.size() == target_thumb_size_qsizef.toSize() and
                                   is_fallback_red_check_img.pixelColor(0,0) == fallback_qcolor_red and
                                   is_fallback_red_check_img.pixelColor(target_thumb_size_qsizef.toSize().width()-1, 0) == fallback_qcolor_red)
                if not is_fallback_red:
                    intended_pixmap_created_successfully = True
            else: logger.warning(f"Pixmap toImage() failed for palette asset '{asset_key}' during success check.")

        # If pixmap_for_palette is still None or Null (even after get_asset_pixmap's internal fallback attempt)
        if not pixmap_for_palette or pixmap_for_palette.isNull():
            target_qsize_thumb = target_thumb_size_qsizef.toSize()
            fb_w_thumb = target_qsize_thumb.width() if target_qsize_thumb.width() > 0 else int(ED_CONFIG.ASSET_THUMBNAIL_SIZE)
            fb_h_thumb = target_qsize_thumb.height() if target_qsize_thumb.height() > 0 else int(ED_CONFIG.ASSET_THUMBNAIL_SIZE)
            pixmap_for_palette = QPixmap(max(1, fb_w_thumb), max(1, fb_h_thumb))

            if pixmap_for_palette.isNull():
                logger.error(f"Palette fallback pixmap for '{asset_key}' is ALSO NULL. Size: {fb_w_thumb}x{fb_h_thumb}")
                pixmap_for_palette = QPixmap() # Assign an empty QPixmap
            else: pixmap_for_palette.fill(fallback_qcolor_red) # Standard fallback

        asset_data_entry["q_pixmap"] = pixmap_for_palette # Store the (potentially fallback) pixmap

        # --- Cursor Preview Pixmap ---
        # Use QSizeF for native size for cursor preview, converted to QSize by get_asset_pixmap if needed
        cursor_native_target_size_qsizef = QSizeF(max(1.0, original_w_float), max(1.0, original_h_float))
        cursor_base_pixmap_native = get_asset_pixmap(
            asset_key, asset_data_entry,
            cursor_native_target_size_qsizef,
            override_color=None, # Cursor preview uses default or selected palette color
            get_native_size_only=True, # Get it at its native (potentially transformed) size
            is_flipped_h=False, rotation=0 # Transformations are applied at draw time for cursor
        )

        pixmap_for_cursor: Optional[QPixmap] = None
        if cursor_base_pixmap_native and not cursor_base_pixmap_native.isNull():
            try:
                img_for_cursor_alpha = cursor_base_pixmap_native.toImage().convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
                
                if img_for_cursor_alpha.isNull() or img_for_cursor_alpha.width() == 0 or img_for_cursor_alpha.height() == 0:
                    logger.warning(f"Cursor base image for '{asset_key}' is invalid. Size: {img_for_cursor_alpha.size()}")
                    # Corrected: Use float for original_w/h then cast to int for QPixmap
                    cursor_fb_w, cursor_fb_h = int(max(1.0, original_w_float)), int(max(1.0, original_h_float))
                    pixmap_for_cursor = QPixmap(cursor_fb_w, cursor_fb_h)
                    if not pixmap_for_cursor.isNull(): pixmap_for_cursor.fill(fallback_qcolor_blue)
                    else: pixmap_for_cursor = QPixmap()
                else:
                    cursor_image_with_alpha = QImage(img_for_cursor_alpha.size(), QImage.Format.Format_ARGB32_Premultiplied)
                    if cursor_image_with_alpha.isNull():
                        logger.error(f"Failed to create QImage for cursor alpha mask for '{asset_key}'")
                        cursor_fb_w, cursor_fb_h = int(max(1.0, original_w_float)), int(max(1.0, original_h_float))
                        pixmap_for_cursor = QPixmap(cursor_fb_w, cursor_fb_h)
                        if not pixmap_for_cursor.isNull(): pixmap_for_cursor.fill(fallback_qcolor_blue)
                        else: pixmap_for_cursor = QPixmap()
                    else:
                        cursor_image_with_alpha.fill(Qt.GlobalColor.transparent)
                        painter = QPainter()
                        if painter.begin(cursor_image_with_alpha):
                            try:
                                painter.setOpacity(float(ED_CONFIG.CURSOR_ASSET_ALPHA) / 255.0)
                                painter.drawImage(0, 0, img_for_cursor_alpha)
                            finally: painter.end()
                            pixmap_for_cursor = QPixmap.fromImage(cursor_image_with_alpha)
                            if pixmap_for_cursor.isNull():
                                logger.error(f"Pixmap.fromImage for cursor failed for '{asset_key}'")
                                cursor_fb_w, cursor_fb_h = int(max(1.0, original_w_float)), int(max(1.0, original_h_float))
                                pixmap_for_cursor = QPixmap(cursor_fb_w, cursor_fb_h)
                                if not pixmap_for_cursor.isNull(): pixmap_for_cursor.fill(fallback_qcolor_blue)
                                else: pixmap_for_cursor = QPixmap()
                        else:
                            logger.error(f"Failed to begin painter on cursor alpha image for '{asset_key}'")
                            cursor_fb_w, cursor_fb_h = int(max(1.0, original_w_float)), int(max(1.0, original_h_float))
                            pixmap_for_cursor = QPixmap(cursor_fb_w, cursor_fb_h)
                            if not pixmap_for_cursor.isNull(): pixmap_for_cursor.fill(fallback_qcolor_blue)
                            else: pixmap_for_cursor = QPixmap()
            except Exception as e_cursor_alpha:
                logger.error(f"Error applying alpha to cursor for '{asset_key}': {e_cursor_alpha}", exc_info=True)
                cursor_fb_w, cursor_fb_h = int(max(1.0, original_w_float)), int(max(1.0, original_h_float))
                pixmap_for_cursor = QPixmap(cursor_fb_w, cursor_fb_h)
                if not pixmap_for_cursor.isNull(): pixmap_for_cursor.fill(fallback_qcolor_blue)
                else: pixmap_for_cursor = QPixmap()
        else: # Fallback if cursor_base_pixmap_native failed
            cursor_fb_w, cursor_fb_h = int(max(1.0, original_w_float)), int(max(1.0, original_h_float))
            pixmap_for_cursor = QPixmap(cursor_fb_w, cursor_fb_h)
            if not pixmap_for_cursor.isNull(): pixmap_for_cursor.fill(fallback_qcolor_blue)
            else: pixmap_for_cursor = QPixmap()

        asset_data_entry["q_pixmap_cursor"] = pixmap_for_cursor
        editor_state.assets_palette[asset_key] = asset_data_entry

        if intended_pixmap_created_successfully: successful_loads += 1
        else: failed_loads += 1

    logger.info(f"Palette asset loading complete. Success: {successful_loads}, Failed/Fallback: {failed_loads}.")