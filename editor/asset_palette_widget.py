# editor/asset_palette_widget.py
# -*- coding: utf-8 -*-
"""
Asset Palette Widget for the Platformer Level Editor.
Refactored for cleaner logger usage and selection logic.
"""
import logging
import os
from typing import Optional, Dict, Any, List, Tuple

from PySide6.QtWidgets import (
    QWidget, QListWidget, QListWidgetItem, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QPushButton,
    QColorDialog, QApplication, QAbstractItemView
)
from PySide6.QtGui import QIcon, QPalette, QColor, QPixmap, QPainter, QImage, QMouseEvent
from PySide6.QtCore import Qt, Signal, Slot, QSize, QPoint

# Corrected relative imports
from . import editor_config as ED_CONFIG
from .editor_state import EditorState
from . import editor_map_utils
from .editor_assets import get_asset_pixmap
from .editor_actions import (ACTION_UI_UP, ACTION_UI_DOWN, ACTION_UI_LEFT, ACTION_UI_RIGHT,
                             ACTION_UI_ACCEPT, ACTION_UI_CANCEL, ACTION_UI_TAB_NEXT, ACTION_UI_TAB_PREV)

logger = logging.getLogger(__name__)

class CustomAssetListWidget(QListWidget):
    """Subclass QListWidget to handle right-click events on items."""
    item_right_clicked = Signal(QListWidgetItem, QPoint)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.RightButton:
            item = self.itemAt(event.pos())
            if item:
                self.item_right_clicked.emit(item, event.globalPos())
                return
        super().mousePressEvent(event)


class AssetPaletteWidget(QWidget):
    asset_selected_for_placement = Signal(str, bool, int, int)
    tool_selected = Signal(str)
    asset_info_selected = Signal(str)
    paint_color_changed_for_status = Signal(str)
    controller_focus_requested_elsewhere = Signal()

    SUBFOCUS_LIST = 0
    SUBFOCUS_CATEGORY_COMBO = 1
    SUBFOCUS_PAINT_COLOR_BTN = 2

    def __init__(self, editor_state: EditorState, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.editor_state = editor_state
        self.parent_window = parent
        self.categories_populated_in_combo = False
        self._controller_has_focus = False
        self._controller_sub_focus_index = self.SUBFOCUS_LIST
        self._controller_list_current_index = 0 # Tracks the desired controller-focused row index

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(2,2,2,2)
        self.main_layout.setSpacing(3)

        filter_area_layout = QHBoxLayout()

        self.category_filter_combo = QComboBox(self)
        self.category_filter_combo.addItem("All")
        self.category_filter_combo.currentIndexChanged.connect(self._on_category_filter_changed)
        self.category_filter_combo.setObjectName("AssetCategoryFilterCombo")
        filter_area_layout.addWidget(self.category_filter_combo, 1)

        self.paint_color_button = QPushButton("Paint Color")
        self.paint_color_button.setToolTip("Set the color for the next placed colorable asset. Current color shown by button background.")
        self.paint_color_button.clicked.connect(self._on_select_paint_color)
        self.paint_color_button.setObjectName("AssetPaintColorButton")
        self._update_paint_color_button_visuals()
        filter_area_layout.addWidget(self.paint_color_button, 0)

        self.main_layout.addLayout(filter_area_layout)

        self.asset_list_widget = CustomAssetListWidget(self)
        self.asset_list_widget.setIconSize(QSize(ED_CONFIG.ASSET_THUMBNAIL_SIZE, ED_CONFIG.ASSET_THUMBNAIL_SIZE))
        self.asset_list_widget.setViewMode(QListWidget.ViewMode.IconMode)
        self.asset_list_widget.setFlow(QListWidget.Flow.LeftToRight)
        self.asset_list_widget.setWrapping(True)
        self.asset_list_widget.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.asset_list_widget.setSpacing(5)
        self.asset_list_widget.itemClicked.connect(self.on_item_left_clicked)
        self.asset_list_widget.item_right_clicked.connect(self.on_item_right_clicked)
        self.asset_list_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.asset_list_widget.setObjectName("AssetListWidget")
        self.asset_list_widget.setStyleSheet("""
            QListWidget::item { padding: 4px; border: 1px solid transparent; }
            QListWidget::item:hover { background-color: #e0e0e0; color: black; }
            QListWidget::item:selected { border: 1px solid #333; background-color: #c0d5eA; color: black;}
        """)
        self.main_layout.addWidget(self.asset_list_widget)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def _update_paint_color_button_visuals(self):
        color_tuple = self.editor_state.current_selected_asset_paint_color
        self.paint_color_button.setText("Paint Color")
        base_style = "QPushButton { min-height: 20px; padding: 2px; }"
        focus_border_style = ""
        if self._controller_has_focus and self._controller_sub_focus_index == self.SUBFOCUS_PAINT_COLOR_BTN:
            focus_border_style = f"border: {ED_CONFIG.ASSET_PALETTE_CONTROLLER_SUBFOCUS_BORDER};"
        else:
            focus_border_style = "border: 1px solid #555;"

        if color_tuple:
            q_color = QColor(*color_tuple)
            palette = self.paint_color_button.palette()
            palette.setColor(QPalette.ColorRole.Button, q_color)
            luma = 0.299 * color_tuple[0] + 0.587 * color_tuple[1] + 0.114 * color_tuple[2]
            text_q_color = QColor(Qt.GlobalColor.black) if luma > 128 else QColor(Qt.GlobalColor.white)
            palette.setColor(QPalette.ColorRole.ButtonText, text_q_color)
            self.paint_color_button.setPalette(palette)
            self.paint_color_button.setAutoFillBackground(True)
            self.paint_color_button.setStyleSheet(base_style + focus_border_style)
        else:
            self.paint_color_button.setAutoFillBackground(False)
            app_instance = QApplication.instance()
            # Use style's standard palette if app_instance exists, otherwise default QWidget palette
            self.paint_color_button.setPalette(app_instance.style().standardPalette() if app_instance else QWidget().palette())
            self.paint_color_button.setStyleSheet(base_style + focus_border_style)
        self.paint_color_button.update()

    @Slot()
    def _on_select_paint_color(self):
        current_q_color = QColor(*self.editor_state.current_selected_asset_paint_color) if self.editor_state.current_selected_asset_paint_color else QColor(Qt.GlobalColor.white)
        new_q_color = QColorDialog.getColor(current_q_color, self, "Select Asset Paint Color")
        if new_q_color.isValid():
            self.editor_state.current_selected_asset_paint_color = new_q_color.getRgb()[:3]
            status_msg = f"Asset paint color set to: {self.editor_state.current_selected_asset_paint_color}"
        else:
            status_msg = "Asset paint color selection cancelled."
        self._update_paint_color_button_visuals()
        self.paint_color_changed_for_status.emit(status_msg)

    def _populate_category_combo_if_needed(self):
        if self.categories_populated_in_combo and self.category_filter_combo.count() > 1:
            if self.category_filter_combo.findText("Custom") != -1 or \
               not (self.editor_state.map_name_for_function and self.editor_state.map_name_for_function != "untitled_map"):
                return

        all_asset_categories = set()
        for data in self.editor_state.assets_palette.values():
            all_asset_categories.add(data.get("category", "unknown"))

        if "Custom" in ED_CONFIG.EDITOR_PALETTE_ASSETS_CATEGORIES_ORDER:
             all_asset_categories.add("Custom")

        combo_items = ["All"]

        for cat_name_ordered in ED_CONFIG.EDITOR_PALETTE_ASSETS_CATEGORIES_ORDER:
            if cat_name_ordered == "Custom":
                if self.editor_state.map_name_for_function and self.editor_state.map_name_for_function != "untitled_map":
                    custom_folder = editor_map_utils.get_map_specific_folder_path(self.editor_state, self.editor_state.map_name_for_function, subfolder="Custom")
                    if custom_folder and os.path.exists(custom_folder):
                        has_custom_content = any(
                            f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif'))
                            for f in os.listdir(custom_folder)
                        )
                        if has_custom_content:
                            combo_items.append("Custom")
                all_asset_categories.discard("Custom") 
            elif cat_name_ordered in all_asset_categories:
                combo_items.append(cat_name_ordered.title()) 
                all_asset_categories.discard(cat_name_ordered)

        for remaining_cat in sorted(list(all_asset_categories)):
             combo_items.append(remaining_cat.title())

        self.category_filter_combo.blockSignals(True)
        current_text_selection = self.category_filter_combo.currentText()
        self.category_filter_combo.clear()
        self.category_filter_combo.addItems(combo_items)
        idx = self.category_filter_combo.findText(current_text_selection)
        self.category_filter_combo.setCurrentIndex(idx if idx != -1 else 0) 
        self.category_filter_combo.blockSignals(False)
        self.categories_populated_in_combo = True

    def _get_pixmap_for_palette_item(self, asset_key: str, asset_data: Dict[str, Any]) -> QPixmap:
        # Determine effective asset key and rotation for icon
        effective_asset_key_for_icon = asset_key
        rotation_for_icon = 0
        
        if asset_key == self.editor_state.palette_current_asset_key:
            if asset_key == ED_CONFIG.WALL_BASE_KEY:
                if 0 <= self.editor_state.palette_wall_variant_index < len(ED_CONFIG.WALL_VARIANTS_CYCLE):
                    variant_key = ED_CONFIG.WALL_VARIANTS_CYCLE[self.editor_state.palette_wall_variant_index]
                    # Check if this variant is the special segment type
                    variant_asset_data = self.editor_state.assets_palette.get(variant_key)
                    if variant_asset_data and variant_asset_data.get("render_as_rotated_segment"):
                        effective_asset_key_for_icon = variant_key 
                        rotation_for_icon = self.editor_state.palette_asset_rotation
                    else: # It's a standard wall variant, not the 1/4 segment
                        effective_asset_key_for_icon = variant_key
                        rotation_for_icon = self.editor_state.palette_asset_rotation # Use general rotation
            elif asset_data.get("render_as_rotated_segment"): # If the base selected key is the segment itself
                rotation_for_icon = self.editor_state.palette_asset_rotation
            else: # For other non-wall, non-segment assets, use general rotation if any logic supports it
                rotation_for_icon = self.editor_state.palette_asset_rotation

        asset_data_for_icon = self.editor_state.assets_palette.get(effective_asset_key_for_icon, asset_data)

        pixmap_for_palette: Optional[QPixmap] = None
        if asset_key.startswith(ED_CONFIG.CUSTOM_ASSET_PALETTE_PREFIX):
            temp_qimage = QImage(asset_data_for_icon["source_file"])
            if not temp_qimage.isNull():
                asset_data_for_icon["original_size_pixels"] = (temp_qimage.width(), temp_qimage.height())
                pixmap_for_palette = get_asset_pixmap(asset_key, asset_data_for_icon,
                                                      QSize(ED_CONFIG.ASSET_THUMBNAIL_SIZE, ED_CONFIG.ASSET_THUMBNAIL_SIZE),
                                                      get_native_size_only=False,
                                                      is_flipped_h=False, rotation=rotation_for_icon) # Pass rotation
        else:
            data_for_get_pixmap = self.editor_state.assets_palette.get(effective_asset_key_for_icon, asset_data_for_icon)
            pixmap_for_palette = get_asset_pixmap(effective_asset_key_for_icon,
                                                 data_for_get_pixmap,
                                                 QSize(ED_CONFIG.ASSET_THUMBNAIL_SIZE, ED_CONFIG.ASSET_THUMBNAIL_SIZE),
                                                 get_native_size_only=False,
                                                 is_flipped_h=False, rotation=rotation_for_icon) # Pass rotation

        if not pixmap_for_palette or pixmap_for_palette.isNull():
            logger.warning(f"Could not load/create pixmap for palette item: {asset_key} (effective: {effective_asset_key_for_icon}, rot: {rotation_for_icon}). Using placeholder.")
            pixmap_for_palette = QPixmap(ED_CONFIG.ASSET_THUMBNAIL_SIZE, ED_CONFIG.ASSET_THUMBNAIL_SIZE)
            pixmap_for_palette.fill(Qt.GlobalColor.magenta) 
        return pixmap_for_palette


    def populate_assets(self, filter_override: Optional[str] = None):
        self._populate_category_combo_if_needed()
        current_filter_text = filter_override if filter_override is not None else self.category_filter_combo.currentText()
        
        asset_key_to_reselect = self.editor_state.palette_current_asset_key

        self.asset_list_widget.clear()
        
        item_cell_width = 85 
        item_cell_height = ED_CONFIG.ASSET_THUMBNAIL_SIZE + 20 
        self.asset_list_widget.setGridSize(QSize(item_cell_width, item_cell_height))
        self.asset_list_widget.setUniformItemSizes(True)

        assets_to_display_tuples: List[Tuple[str, Dict[str, Any]]] = []

        if current_filter_text.lower() == "custom":
            if self.editor_state.map_name_for_function and self.editor_state.map_name_for_function != "untitled_map":
                map_name = self.editor_state.map_name_for_function
                custom_folder = editor_map_utils.get_map_specific_folder_path(self.editor_state, map_name, subfolder="Custom")
                if custom_folder and os.path.exists(custom_folder):
                    for filename in sorted(os.listdir(custom_folder)):
                        if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                            full_path = os.path.join(custom_folder, filename)
                            custom_asset_key = f"{ED_CONFIG.CUSTOM_ASSET_PALETTE_PREFIX}{filename}"
                            asset_data_entry_temp = {
                                "source_file": full_path, 
                                "name_in_palette": filename,
                                "category": "Custom",
                                "game_type_id": ED_CONFIG.CUSTOM_IMAGE_ASSET_KEY,
                                "original_size_pixels": None 
                            }
                            assets_to_display_tuples.append((custom_asset_key, asset_data_entry_temp))
            else:
                no_map_item = QListWidgetItem("Load/Save a map to use Custom Assets")
                no_map_item.setFlags(no_map_item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
                self.asset_list_widget.addItem(no_map_item)
        
        elif self.editor_state.assets_palette:
            for key, data in self.editor_state.assets_palette.items():
                category = data.get("category", "unknown")
                if current_filter_text.lower() == "all" or \
                   category.lower() == current_filter_text.lower() or \
                   category.title().lower() == current_filter_text.lower(): 
                    assets_to_display_tuples.append((key, data))
        
        assets_to_display_tuples.sort(key=lambda x: (ED_CONFIG.EDITOR_PALETTE_ASSETS_CATEGORIES_ORDER.index(x[1].get("category", "unknown"))
                                                     if x[1].get("category", "unknown") in ED_CONFIG.EDITOR_PALETTE_ASSETS_CATEGORIES_ORDER else 99,
                                                     x[0]))

        newly_selected_q_item: Optional[QListWidgetItem] = None
        for idx, (key, data) in enumerate(assets_to_display_tuples):
            pixmap_for_item = self._get_pixmap_for_palette_item(key, data) # This now uses rotation
            
            item_text_for_tooltip = data.get("name_in_palette", key.replace("_", " ").title())
            list_item = QListWidgetItem(QIcon(pixmap_for_item), "") 
            list_item.setToolTip(item_text_for_tooltip)
            list_item.setData(Qt.ItemDataRole.UserRole, key) 
            self.asset_list_widget.addItem(list_item)

            if key == asset_key_to_reselect:
                newly_selected_q_item = list_item

        if newly_selected_q_item:
            self.asset_list_widget.setCurrentItem(newly_selected_q_item)
            self._controller_list_current_index = self.asset_list_widget.row(newly_selected_q_item)
        elif self.asset_list_widget.count() > 0:
            if 0 <= self._controller_list_current_index < self.asset_list_widget.count():
                self.asset_list_widget.setCurrentRow(self._controller_list_current_index)
            else:
                self.asset_list_widget.setCurrentRow(0)
                self._controller_list_current_index = 0
            newly_selected_q_item = self.asset_list_widget.currentItem()
        else: 
            self._controller_list_current_index = -1

        if newly_selected_q_item:
            self.asset_list_widget.scrollToItem(newly_selected_q_item, QAbstractItemView.ScrollHint.EnsureVisible)
        
        self._update_sub_focus_visuals()

    @Slot(int)
    def _on_category_filter_changed(self, index: int):
        self.populate_assets()

    @Slot(QListWidgetItem)
    def on_item_left_clicked(self, item: QListWidgetItem):
        if not (item.flags() & Qt.ItemFlag.ItemIsEnabled):
            return
        self._controller_list_current_index = self.asset_list_widget.row(item)
        
        asset_key_or_custom_id = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(asset_key_or_custom_id, str):
            logger.warning("AssetPalette: Clicked item has no valid string UserRole data.")
            return
        
        display_name_for_status = item.toolTip()
        self.editor_state.current_tool_mode = "place" 

        self.editor_state.palette_current_asset_key = asset_key_or_custom_id
        self.editor_state.palette_asset_is_flipped_h = False 
        self.editor_state.palette_asset_rotation = 0
        
        # Reset wall variant index if the base wall key is selected,
        # or if the selected asset is the 1/4 segment type.
        # For the 1/4 segment, its rotation is handled by palette_asset_rotation.
        asset_data = self.editor_state.assets_palette.get(asset_key_or_custom_id)
        if asset_key_or_custom_id == ED_CONFIG.WALL_BASE_KEY:
            self.editor_state.palette_wall_variant_index = 0
        elif asset_data and asset_data.get("render_as_rotated_segment"):
            self.editor_state.palette_wall_variant_index = ED_CONFIG.WALL_VARIANTS_CYCLE.index(asset_key_or_custom_id) if asset_key_or_custom_id in ED_CONFIG.WALL_VARIANTS_CYCLE else 0
            # palette_asset_rotation is already 0 from above
        else:
            self.editor_state.palette_wall_variant_index = 0


        self.asset_info_selected.emit(asset_key_or_custom_id) 

        if asset_key_or_custom_id.startswith("tool_"):
            self.editor_state.current_tool_mode = asset_key_or_custom_id
            self.tool_selected.emit(asset_key_or_custom_id)
            self.show_status_message(f"Tool selected: {display_name_for_status}")
        else:
            self.asset_selected_for_placement.emit(
                str(self.editor_state.palette_current_asset_key),
                self.editor_state.palette_asset_is_flipped_h,
                self.editor_state.palette_wall_variant_index, # For standard walls
                self.editor_state.palette_asset_rotation     # For rotatable segments
            )
            status_msg = f"Asset for placement: {display_name_for_status}"
            
            effective_key_for_status = self.editor_state.palette_current_asset_key
            current_rotation_for_status = self.editor_state.palette_asset_rotation
            is_segment_type = False
            
            if self.editor_state.palette_current_asset_key == ED_CONFIG.WALL_BASE_KEY:
                effective_key_for_status = ED_CONFIG.WALL_VARIANTS_CYCLE[self.editor_state.palette_wall_variant_index]
                variant_data = self.editor_state.assets_palette.get(effective_key_for_status)
                if variant_data:
                    status_msg += f" ({variant_data.get('name_in_palette', effective_key_for_status)})"
                    if variant_data.get("render_as_rotated_segment"):
                        is_segment_type = True
            elif asset_data and asset_data.get("render_as_rotated_segment"):
                is_segment_type = True

            orientation_status = "Default Orientation"
            if self.editor_state.palette_asset_is_flipped_h: orientation_status = "Flipped"
            if is_segment_type: # Use rotation for segment status
                 orientation_status = f"Rotated to {current_rotation_for_status}°"
            elif current_rotation_for_status != 0: # For other rotatable items
                 orientation_status = f"Rotated to {current_rotation_for_status}°"


            self.show_status_message(f"{status_msg} ({orientation_status})")
        
        self.populate_assets() 


    @Slot(QListWidgetItem, QPoint)
    def on_item_right_clicked(self, item: QListWidgetItem, global_pos: QPoint):
        if not (item.flags() & Qt.ItemFlag.ItemIsEnabled):
            return
        
        asset_key_clicked = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(asset_key_clicked, str) or asset_key_clicked.startswith("tool_"):
            return

        if self.editor_state.palette_current_asset_key != asset_key_clicked:
            self.editor_state.palette_current_asset_key = asset_key_clicked
            self.editor_state.palette_asset_is_flipped_h = False
            self.editor_state.palette_asset_rotation = 0
            if asset_key_clicked == ED_CONFIG.WALL_BASE_KEY:
                self.editor_state.palette_wall_variant_index = 0
            # For 1/4 segment, rotation is handled below.
            self.asset_info_selected.emit(asset_key_clicked)
        
        status_msg_part = ""
        asset_data = self.editor_state.assets_palette.get(self.editor_state.palette_current_asset_key)

        if asset_data and asset_data.get("render_as_rotated_segment"):
            # This is the 1/4 segment, cycle its rotation
            self.editor_state.palette_asset_rotation = (self.editor_state.palette_asset_rotation + 90) % 360
            status_msg_part = f"{asset_data.get('name_in_palette', self.editor_state.palette_current_asset_key)} rotated to {self.editor_state.palette_asset_rotation}°"
            # Ensure wall_variant_index points to this segment type if it's in WALL_VARIANTS_CYCLE
            try:
                self.editor_state.palette_wall_variant_index = ED_CONFIG.WALL_VARIANTS_CYCLE.index(self.editor_state.palette_current_asset_key)
            except ValueError:
                logger.warning(f"Segment {self.editor_state.palette_current_asset_key} not in WALL_VARIANTS_CYCLE, variant index might be incorrect.")
                self.editor_state.palette_wall_variant_index = 0 # Fallback

        elif self.editor_state.palette_current_asset_key == ED_CONFIG.WALL_BASE_KEY:
            # This is the standard wall, cycle its variants
            num_variants = len(ED_CONFIG.WALL_VARIANTS_CYCLE)
            if num_variants > 0:
                self.editor_state.palette_wall_variant_index = (self.editor_state.palette_wall_variant_index + 1) % num_variants
            
            effective_key_variant = ED_CONFIG.WALL_VARIANTS_CYCLE[self.editor_state.palette_wall_variant_index]
            variant_data = self.editor_state.assets_palette.get(effective_key_variant)
            variant_name = variant_data.get('name_in_palette', effective_key_variant) if variant_data else effective_key_variant
            status_msg_part = f"Wall variant (palette): {variant_name}"
            # If the new variant is the 1/4 segment, reset its rotation
            if variant_data and variant_data.get("render_as_rotated_segment"):
                self.editor_state.palette_asset_rotation = 0
        
        if status_msg_part:
            self.show_status_message(status_msg_part)
        
        self.populate_assets()
        
        if self.editor_state.palette_current_asset_key and not asset_key_clicked.startswith("tool_"):
            # Emit with current state (base key for walls, specific key if segment is directly selected)
            # The emitted asset_key should be the one used by game logic (e.g. platform_wall_gray_1_4_top)
            # The variant index is mostly for standard wall cycling, less so for direct segment selection
            
            key_to_emit = self.editor_state.palette_current_asset_key
            wall_variant_idx_to_emit = self.editor_state.palette_wall_variant_index
            
            # If the current *selected item in palette* is WALL_BASE_KEY,
            # and the *cycled variant* is the 1/4 segment, we need to adjust what's emitted.
            if self.editor_state.palette_current_asset_key == ED_CONFIG.WALL_BASE_KEY:
                cycled_variant_key = ED_CONFIG.WALL_VARIANTS_CYCLE[self.editor_state.palette_wall_variant_index]
                cycled_variant_data = self.editor_state.assets_palette.get(cycled_variant_key)
                if cycled_variant_data and cycled_variant_data.get("render_as_rotated_segment"):
                    key_to_emit = cycled_variant_key # Emit the segment key directly
                    # wall_variant_idx_to_emit becomes less relevant here as rotation handles orientation
            
            self.asset_selected_for_placement.emit(
                str(key_to_emit),
                self.editor_state.palette_asset_is_flipped_h,
                wall_variant_idx_to_emit, # For standard wall cycles
                self.editor_state.palette_asset_rotation # Important for segments
            )

    def show_status_message(self, message: str, timeout: int = 3000):
        if hasattr(self.parent_window, "show_status_message"):
            self.parent_window.show_status_message(message, timeout)
        else:
            logger.info(f"Status (AssetPalette): {message}")
    
    def clear_selection(self):
        self.asset_list_widget.clearSelection()
        self.editor_state.palette_current_asset_key = None
        self.editor_state.palette_asset_is_flipped_h = False
        self.editor_state.palette_asset_rotation = 0
        self.editor_state.palette_wall_variant_index = 0
        
        if self.asset_list_widget.count() > 0:
            self._controller_list_current_index = 0 
        else:
            self._controller_list_current_index = -1
        
        self._update_sub_focus_visuals() 
        self.populate_assets() 


    def _update_sub_focus_visuals(self):
        list_border = "1px solid transparent" 
        combo_border = "1px solid gray"       
        
        selected_item_style = "QListWidget::item:selected { border: 1px solid #007ACC; background-color: #c0d5eA; color: black; }"
        
        self.asset_list_widget.setStyleSheet(f"""
            {selected_item_style}
            QListWidget {{ border: {list_border}; }}
        """)
        self.category_filter_combo.setStyleSheet(f"QComboBox {{ border: {combo_border}; }}")
        self._update_paint_color_button_visuals() 

        if self._controller_has_focus:
            focus_border_style_str = str(ED_CONFIG.ASSET_PALETTE_CONTROLLER_SUBFOCUS_BORDER)
            if self._controller_sub_focus_index == self.SUBFOCUS_LIST:
                self.asset_list_widget.setStyleSheet(f"""
                    {selected_item_style}
                    QListWidget {{ border: {focus_border_style_str}; }}
                """)
                if self.asset_list_widget.count() > 0:
                    self.asset_list_widget.setFocus() 
            elif self._controller_sub_focus_index == self.SUBFOCUS_CATEGORY_COMBO:
                self.category_filter_combo.setStyleSheet(f"QComboBox {{ border: {focus_border_style_str}; }}")
                self.category_filter_combo.setFocus() 
            elif self._controller_sub_focus_index == self.SUBFOCUS_PAINT_COLOR_BTN:
                self.paint_color_button.setFocus() 

    def on_controller_focus_gained(self):
        self._controller_has_focus = True
        self._controller_sub_focus_index = self.SUBFOCUS_LIST 
        
        if self.asset_list_widget.count() > 0:
            item_to_select_by_controller: Optional[QListWidgetItem] = None
            
            if self.editor_state.palette_current_asset_key:
                for i in range(self.asset_list_widget.count()):
                    item = self.asset_list_widget.item(i)
                    if item.data(Qt.ItemDataRole.UserRole) == self.editor_state.palette_current_asset_key:
                        item_to_select_by_controller = item
                        self._controller_list_current_index = i
                        break
            
            if item_to_select_by_controller:
                 self.asset_list_widget.setCurrentItem(item_to_select_by_controller)
            elif 0 <= self._controller_list_current_index < self.asset_list_widget.count():
                self.asset_list_widget.setCurrentRow(self._controller_list_current_index)
                item_to_select_by_controller = self.asset_list_widget.item(self._controller_list_current_index)
            else: 
                 self.asset_list_widget.setCurrentRow(0)
                 self._controller_list_current_index = 0
                 item_to_select_by_controller = self.asset_list_widget.item(0)

            if item_to_select_by_controller: 
                self.asset_list_widget.scrollToItem(item_to_select_by_controller, QAbstractItemView.ScrollHint.EnsureVisible)
        
        self._update_sub_focus_visuals()
        logger.debug("AssetPalette: Controller focus gained.")

    def on_controller_focus_lost(self):
        self._controller_has_focus = False
        self._update_sub_focus_visuals() 
        logger.debug("AssetPalette: Controller focus lost.")

    def handle_controller_action(self, action: str, value: Any):
        if not self._controller_has_focus:
            return

        if self._controller_sub_focus_index == self.SUBFOCUS_LIST:
            count = self.asset_list_widget.count()
            if count == 0: 
                if action == ACTION_UI_TAB_NEXT or action == ACTION_UI_RIGHT: self._cycle_sub_focus(1)
                elif action == ACTION_UI_TAB_PREV or action == ACTION_UI_LEFT: self._cycle_sub_focus(-1)
                return

            num_cols = 1
            if self.asset_list_widget.gridSize().width() > 0:
                num_cols = self.asset_list_widget.width() // self.asset_list_widget.gridSize().width()
            num_cols = max(1, num_cols) 

            if action == ACTION_UI_UP:
                self._controller_list_current_index = max(0, self._controller_list_current_index - num_cols)
            elif action == ACTION_UI_DOWN:
                self._controller_list_current_index = min(count - 1, self._controller_list_current_index + num_cols)
            elif action == ACTION_UI_LEFT:
                self._controller_list_current_index = max(0, self._controller_list_current_index - 1)
            elif action == ACTION_UI_RIGHT:
                self._controller_list_current_index = min(count - 1, self._controller_list_current_index + 1)
            elif action == ACTION_UI_ACCEPT:
                item = self.asset_list_widget.item(self._controller_list_current_index)
                if item:
                    self.on_item_left_clicked(item) 
            elif action == ACTION_UI_CANCEL: 
                item = self.asset_list_widget.item(self._controller_list_current_index)
                if item:
                    self.on_item_right_clicked(item, self.asset_list_widget.visualItemRect(item).center())
            elif action == ACTION_UI_TAB_NEXT: self._cycle_sub_focus(1)
            elif action == ACTION_UI_TAB_PREV: self._cycle_sub_focus(-1)
            
            if 0 <= self._controller_list_current_index < count:
                self.asset_list_widget.setCurrentRow(self._controller_list_current_index)
                current_item = self.asset_list_widget.item(self._controller_list_current_index)
                if current_item:
                    self.asset_list_widget.scrollToItem(current_item, QAbstractItemView.ScrollHint.EnsureVisible)

        elif self._controller_sub_focus_index == self.SUBFOCUS_CATEGORY_COMBO:
            if action == ACTION_UI_UP or action == ACTION_UI_DOWN:
                current_idx = self.category_filter_combo.currentIndex()
                new_idx = current_idx + (-1 if action == ACTION_UI_UP else 1)
                if 0 <= new_idx < self.category_filter_combo.count():
                    self.category_filter_combo.setCurrentIndex(new_idx)
            elif action == ACTION_UI_ACCEPT:
                self.category_filter_combo.showPopup() 
            elif action == ACTION_UI_TAB_NEXT: self._cycle_sub_focus(1)
            elif action == ACTION_UI_TAB_PREV: self._cycle_sub_focus(-1)

        elif self._controller_sub_focus_index == self.SUBFOCUS_PAINT_COLOR_BTN:
            if action == ACTION_UI_ACCEPT:
                self.paint_color_button.click() 
            elif action == ACTION_UI_TAB_NEXT: self._cycle_sub_focus(1)
            elif action == ACTION_UI_TAB_PREV: self._cycle_sub_focus(-1)
        
        self._update_sub_focus_visuals() 

    def _cycle_sub_focus(self, direction: int):
        num_sub_items = 3 
        self._controller_sub_focus_index = (self._controller_sub_focus_index + direction + num_sub_items) % num_sub_items
        self._update_sub_focus_visuals()
        logger.debug(f"AssetPalette: Sub-focus cycled to index {self._controller_sub_focus_index}")