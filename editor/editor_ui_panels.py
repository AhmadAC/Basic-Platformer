#################### START OF FILE: editor_ui_panels.py ####################

# editor_ui_panels.py
# -*- coding: utf-8 -*-
"""
Custom Qt Widgets for UI Panels (Asset Palette, Properties Editor)
in the PySide6 Level Editor.
Version 2.2.2 (Asset Flip/Cycle and Selection Tool)
- Asset Palette handles right-click for flipping and wall variant cycling.
- Icons update to reflect current orientation/variant.
- Selection tool logic separated.
"""
import logging
import os
from typing import Optional, Dict, Any, List, Tuple

from PySide6.QtWidgets import (
    QWidget, QListWidget, QListWidgetItem, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QCheckBox, QComboBox, QPushButton, QScrollArea,
    QFormLayout, QSpinBox, QDoubleSpinBox, QColorDialog,
    QGroupBox, QSizePolicy, QApplication, QAbstractItemView, QFileDialog,
    QMenu
)
from PySide6.QtGui import QIcon, QPalette, QColor, QPixmap, QFocusEvent, QKeyEvent, QPainter, QImage, QMouseEvent
from PySide6.QtCore import Qt, Signal, Slot, QSize, QPoint

from . import editor_config as ED_CONFIG
from .editor_state import EditorState
from . import editor_history
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
                # Do not call super().mousePressEvent(event) here if we want to suppress
                # the default right-click behavior (like selection change).
                # If we want selection to still happen on right-click, then call super.
                # For this feature, we want the left-click to do the selection for placement.
                return 
        super().mousePressEvent(event)


class AssetPaletteWidget(QWidget):
    asset_selected_for_placement = Signal(str, bool, int) # asset_key, is_flipped, wall_variant_idx
    tool_selected = Signal(str) # tool_key
    asset_info_selected = Signal(str) # For properties panel: asset_editor_key or custom:filename.ext
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
        self._controller_list_current_index = 0

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

        self.asset_list_widget = CustomAssetListWidget(self) # Use custom list widget
        self.asset_list_widget.setIconSize(QSize(ED_CONFIG.ASSET_THUMBNAIL_SIZE, ED_CONFIG.ASSET_THUMBNAIL_SIZE)) 
        self.asset_list_widget.setViewMode(QListWidget.ViewMode.IconMode)
        self.asset_list_widget.setFlow(QListWidget.Flow.LeftToRight)
        self.asset_list_widget.setWrapping(True)
        self.asset_list_widget.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.asset_list_widget.setSpacing(5)
        self.asset_list_widget.itemClicked.connect(self.on_item_left_clicked) # Renamed for clarity
        self.asset_list_widget.item_right_clicked.connect(self.on_item_right_clicked) # Connect new signal
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
            if app_instance:
                self.paint_color_button.setPalette(app_instance.style().standardPalette())
            else:
                self.paint_color_button.setPalette(QWidget().palette())
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
        is_flipped = False
        effective_asset_key_for_icon = asset_key

        if asset_key == self.editor_state.palette_current_asset_key:
            is_flipped = self.editor_state.palette_asset_is_flipped_h
            if asset_key == ED_CONFIG.WALL_BASE_KEY:
                if 0 <= self.editor_state.palette_wall_variant_index < len(ED_CONFIG.WALL_VARIANTS_CYCLE):
                    effective_asset_key_for_icon = ED_CONFIG.WALL_VARIANTS_CYCLE[self.editor_state.palette_wall_variant_index]
                    # If the variant itself is what's stored in editor_state.assets_palette, use its data
                    asset_data_for_icon = self.editor_state.assets_palette.get(effective_asset_key_for_icon, asset_data)
                else:
                    asset_data_for_icon = asset_data # Fallback to base wall data
            else:
                asset_data_for_icon = asset_data
        else:
            asset_data_for_icon = asset_data
            # If this asset_key is a wall variant but not the currently active one, show its base form
            if asset_key in ED_CONFIG.WALL_VARIANTS_CYCLE and asset_key != ED_CONFIG.WALL_BASE_KEY:
                 effective_asset_key_for_icon = asset_key 
                 # (already points to the correct variant from iteration)


        pixmap_for_palette: Optional[QPixmap] = None
        if asset_key.startswith(ED_CONFIG.CUSTOM_ASSET_PALETTE_PREFIX): 
            temp_qimage = QImage(asset_data_for_icon["source_file"])
            if not temp_qimage.isNull():
                asset_data_for_icon["original_size_pixels"] = (temp_qimage.width(), temp_qimage.height())
                pixmap_for_palette = get_asset_pixmap(asset_key, asset_data_for_icon,
                                                      QSize(ED_CONFIG.ASSET_THUMBNAIL_SIZE, ED_CONFIG.ASSET_THUMBNAIL_SIZE), 
                                                      get_native_size_only=False,
                                                      is_flipped_h=is_flipped)
        else:
            # Use the effective_asset_key_for_icon to get data if it's a wall variant
            data_for_get_pixmap = self.editor_state.assets_palette.get(effective_asset_key_for_icon, asset_data_for_icon)

            pixmap_for_palette = get_asset_pixmap(effective_asset_key_for_icon, 
                                                 data_for_get_pixmap,
                                                 QSize(ED_CONFIG.ASSET_THUMBNAIL_SIZE, ED_CONFIG.ASSET_THUMBNAIL_SIZE),
                                                 get_native_size_only=False,
                                                 is_flipped_h=is_flipped)

        if not pixmap_for_palette or pixmap_for_palette.isNull():
            # Fallback if pixmap creation failed
            pixmap_for_palette = QPixmap(ED_CONFIG.ASSET_THUMBNAIL_SIZE, ED_CONFIG.ASSET_THUMBNAIL_SIZE)
            pixmap_for_palette.fill(Qt.GlobalColor.magenta)
        return pixmap_for_palette


    def populate_assets(self, filter_override: Optional[str] = None):
        self._populate_category_combo_if_needed()
        current_filter_text = filter_override if filter_override is not None else self.category_filter_combo.currentText()
        
        old_selected_item_user_data: Optional[str] = None
        current_qt_item = self.asset_list_widget.currentItem()
        if current_qt_item:
            old_selected_item_user_data = current_qt_item.data(Qt.ItemDataRole.UserRole) 

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


        new_selected_item_index = -1
        for idx, (key, data) in enumerate(assets_to_display_tuples):
            pixmap_for_item = self._get_pixmap_for_palette_item(key, data)
            
            item_text_for_tooltip = data.get("name_in_palette", key.replace("_", " ").title())
            list_item = QListWidgetItem(QIcon(pixmap_for_item), "") # Text is usually not shown in IconMode well
            list_item.setToolTip(item_text_for_tooltip)
            list_item.setData(Qt.ItemDataRole.UserRole, key)
            self.asset_list_widget.addItem(list_item)
            if key == old_selected_item_user_data: # Try to reselect based on actual asset key
                new_selected_item_index = idx
        
        if self.asset_list_widget.count() > 0:
            if new_selected_item_index != -1:
                self._controller_list_current_index = new_selected_item_index
            elif self._controller_list_current_index >= self.asset_list_widget.count():
                 self._controller_list_current_index = self.asset_list_widget.count() -1
            elif self._controller_list_current_index < 0:
                 self._controller_list_current_index = 0
            
            self.asset_list_widget.setCurrentRow(self._controller_list_current_index)
            # Ensure the visual selection matches the editor_state's placement intent
            if self.editor_state.palette_current_asset_key:
                for i in range(self.asset_list_widget.count()):
                    item = self.asset_list_widget.item(i)
                    if item.data(Qt.ItemDataRole.UserRole) == self.editor_state.palette_current_asset_key:
                        self.asset_list_widget.setCurrentItem(item)
                        break
        else:
            self._controller_list_current_index = -1

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
            return
        
        display_name_for_status = item.toolTip()
        self.editor_state.current_tool_mode = "place" # Default to place when an asset is left-clicked

        # Update editor_state for placement
        self.editor_state.palette_current_asset_key = asset_key_or_custom_id
        
        # Reset flip/variant if this is not the wall_base_key or not already the selected item
        # If it IS the wall_base_key, the existing variant_index is preserved.
        # If it's a different asset, flip is reset.
        is_wall_base = (asset_key_or_custom_id == ED_CONFIG.WALL_BASE_KEY)
        if not is_wall_base:
            self.editor_state.palette_wall_variant_index = 0 # Reset for non-wall base
        # Flip state is generally reset unless it's the same asset being re-clicked
        # The actual flip happens on right click. This just sets the *current* asset.

        self.asset_info_selected.emit(asset_key_or_custom_id) # For properties panel

        if asset_key_or_custom_id == "tool_select":
            self.editor_state.current_tool_mode = "select"
            self.tool_selected.emit(asset_key_or_custom_id)
            if hasattr(self.parent_window, 'show_status_message'):
                self.parent_window.show_status_message(f"Tool selected: {display_name_for_status}")
        elif asset_key_or_custom_id.startswith("tool_"):
            self.editor_state.current_tool_mode = asset_key_or_custom_id # e.g. "tool_eraser"
            self.tool_selected.emit(asset_key_or_custom_id)
            if hasattr(self.parent_window, 'show_status_message'):
                self.parent_window.show_status_message(f"Tool selected: {display_name_for_status}")
        else: # It's a placeable asset
            self.asset_selected_for_placement.emit(
                self.editor_state.palette_current_asset_key,
                self.editor_state.palette_asset_is_flipped_h,
                self.editor_state.palette_wall_variant_index
            )
            if hasattr(self.parent_window, 'show_status_message'):
                current_variant_name = ""
                if self.editor_state.palette_current_asset_key == ED_CONFIG.WALL_BASE_KEY:
                    effective_key = ED_CONFIG.WALL_VARIANTS_CYCLE[self.editor_state.palette_wall_variant_index]
                    variant_data = self.editor_state.assets_palette.get(effective_key)
                    if variant_data:
                        current_variant_name = f" ({variant_data.get('name_in_palette', effective_key)})"

                flip_status = " (Flipped)" if self.editor_state.palette_asset_is_flipped_h else ""
                self.parent_window.show_status_message(f"Asset for placement: {display_name_for_status}{current_variant_name}{flip_status}")
        
        self.populate_assets() # Repopulate to update icon if necessary


    @Slot(QListWidgetItem, QPoint)
    def on_item_right_clicked(self, item: QListWidgetItem, global_pos: QPoint):
        if not (item.flags() & Qt.ItemFlag.ItemIsEnabled):
            return
        
        asset_key_clicked = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(asset_key_clicked, str):
            return
        
        # If right-clicking a different asset, make it the current one first
        if self.editor_state.palette_current_asset_key != asset_key_clicked:
            self.editor_state.palette_current_asset_key = asset_key_clicked
            self.editor_state.palette_asset_is_flipped_h = False # Reset flip for new asset
            if asset_key_clicked == ED_CONFIG.WALL_BASE_KEY:
                 self.editor_state.palette_wall_variant_index = 0
            else:
                 self.editor_state.palette_wall_variant_index = 0 # Reset variant for non-wall

        if asset_key_clicked == ED_CONFIG.WALL_BASE_KEY:
            # Cycle through wall variants
            num_variants = len(ED_CONFIG.WALL_VARIANTS_CYCLE)
            if num_variants > 0:
                self.editor_state.palette_wall_variant_index = (self.editor_state.palette_wall_variant_index + 1) % num_variants
            effective_key = ED_CONFIG.WALL_VARIANTS_CYCLE[self.editor_state.palette_wall_variant_index]
            variant_data = self.editor_state.assets_palette.get(effective_key)
            variant_name = variant_data.get('name_in_palette', effective_key) if variant_data else effective_key
            self.show_status_message(f"Wall variant: {variant_name}")
        elif not asset_key_clicked.startswith("tool_"): # Tools are not flippable
            # Toggle horizontal flip
            self.editor_state.palette_asset_is_flipped_h = not self.editor_state.palette_asset_is_flipped_h
            flip_status = "Flipped" if self.editor_state.palette_asset_is_flipped_h else "Normal"
            self.show_status_message(f"{item.toolTip()} orientation: {flip_status}")
        
        self.populate_assets() # Update icon
        # Emit signal so MapView can update hover preview if needed
        if self.editor_state.palette_current_asset_key and not asset_key_clicked.startswith("tool_"):
            self.asset_selected_for_placement.emit(
                self.editor_state.palette_current_asset_key,
                self.editor_state.palette_asset_is_flipped_h,
                self.editor_state.palette_wall_variant_index
            )
        elif asset_key_clicked.startswith("tool_"):
            self.tool_selected.emit(asset_key_clicked) # Re-signal tool selection if right-clicked


    def show_status_message(self, message: str, timeout: int = 3000):
        if hasattr(self.parent_window, "show_status_message"):
            self.parent_window.show_status_message(message, timeout)
        else:
            logger.info(f"Status (AssetPalette): {message}")
    
    def clear_selection(self):
        self.asset_list_widget.clearSelection()
        # Also clear the editor state's placement intent
        self.editor_state.palette_current_asset_key = None
        self.editor_state.palette_asset_is_flipped_h = False
        self.editor_state.palette_wall_variant_index = 0
        
        if self.asset_list_widget.count() > 0:
            self._controller_list_current_index = 0
            # Do not automatically setCurrentRow(0) as it might imply selection.
            # Visual deselection is enough.
        else:
            self._controller_list_current_index = -1
        self._update_sub_focus_visuals()
        self.populate_assets() # Refresh icons (e.g. if a selected wall variant needs to revert to base icon)


    def _update_sub_focus_visuals(self):
        list_border = "1px solid transparent"
        combo_border = "1px solid gray"
        
        # Base style for selected items, ensuring it's applied
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
                list_border = focus_border_style_str
                self.asset_list_widget.setStyleSheet(f"""
                    {selected_item_style}
                    QListWidget {{ border: {list_border}; }}
                """)
                if self.asset_list_widget.count() > 0:
                    self.asset_list_widget.setFocus()
            elif self._controller_sub_focus_index == self.SUBFOCUS_CATEGORY_COMBO:
                combo_border = focus_border_style_str
                self.category_filter_combo.setStyleSheet(f"QComboBox {{ border: {combo_border}; }}")
                self.category_filter_combo.setFocus()
            elif self._controller_sub_focus_index == self.SUBFOCUS_PAINT_COLOR_BTN:
                self._update_paint_color_button_visuals() 
                self.paint_color_button.setFocus()

    def on_controller_focus_gained(self):
        self._controller_has_focus = True
        self._controller_sub_focus_index = self.SUBFOCUS_LIST
        if self.asset_list_widget.count() > 0:
            if not (0 <= self._controller_list_current_index < self.asset_list_widget.count()):
                self._controller_list_current_index = 0
            # Ensure the item corresponding to palette_current_asset_key is selected if set
            item_to_select_by_controller = None
            if self.editor_state.palette_current_asset_key:
                for i in range(self.asset_list_widget.count()):
                    item = self.asset_list_widget.item(i)
                    if item.data(Qt.ItemDataRole.UserRole) == self.editor_state.palette_current_asset_key:
                        item_to_select_by_controller = item
                        self._controller_list_current_index = i
                        break
            
            if item_to_select_by_controller:
                 self.asset_list_widget.setCurrentItem(item_to_select_by_controller)
                 self.asset_list_widget.scrollToItem(item_to_select_by_controller, QAbstractItemView.ScrollHint.EnsureVisible)
            elif self._controller_list_current_index >=0 and self._controller_list_current_index < self.asset_list_widget.count():
                self.asset_list_widget.setCurrentRow(self._controller_list_current_index)
                current_item = self.asset_list_widget.item(self._controller_list_current_index)
                if current_item:
                    self.asset_list_widget.scrollToItem(current_item, QAbstractItemView.ScrollHint.EnsureVisible)
        self._update_sub_focus_visuals()
        if logger: logger.debug("AssetPalette: Controller focus gained.")

    def on_controller_focus_lost(self):
        self._controller_has_focus = False
        self._update_sub_focus_visuals()
        if logger: logger.debug("AssetPalette: Controller focus lost.")

    def handle_controller_action(self, action: str, value: Any):
        if not self._controller_has_focus:
            return

        if self._controller_sub_focus_index == self.SUBFOCUS_LIST:
            count = self.asset_list_widget.count()
            if count == 0:
                if action == ACTION_UI_TAB_NEXT or action == ACTION_UI_RIGHT: self._cycle_sub_focus(1)
                elif action == ACTION_UI_TAB_PREV or action == ACTION_UI_LEFT: self._cycle_sub_focus(-1)
                return

            if action == ACTION_UI_UP:
                num_cols = self.asset_list_widget.width() // self.asset_list_widget.gridSize().width() if self.asset_list_widget.gridSize().width() > 0 else 1
                num_cols = max(1, num_cols)
                self._controller_list_current_index = max(0, self._controller_list_current_index - num_cols)
            elif action == ACTION_UI_DOWN:
                num_cols = self.asset_list_widget.width() // self.asset_list_widget.gridSize().width() if self.asset_list_widget.gridSize().width() > 0 else 1
                num_cols = max(1, num_cols)
                self._controller_list_current_index = min(count - 1, self._controller_list_current_index + num_cols)
            elif action == ACTION_UI_LEFT:
                self._controller_list_current_index = max(0, self._controller_list_current_index - 1)
            elif action == ACTION_UI_RIGHT:
                self._controller_list_current_index = min(count - 1, self._controller_list_current_index + 1)
            elif action == ACTION_UI_ACCEPT: # Corresponds to Left Click
                item = self.asset_list_widget.item(self._controller_list_current_index)
                if item:
                    self.on_item_left_clicked(item) # Use the left click handler
            elif action == ACTION_UI_CANCEL: # Corresponds to Right Click for flip/cycle
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
        if logger: logger.debug(f"AssetPalette: Sub-focus cycled to index {self._controller_sub_focus_index}")


class PropertiesEditorDockWidget(QWidget):
    properties_changed = Signal(dict) 
    controller_focus_requested_elsewhere = Signal()
    upload_image_for_trigger_requested = Signal(dict) 

    def __init__(self, editor_state: EditorState, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.editor_state = editor_state
        self.parent_window = parent
        self.current_object_data_ref: Optional[Dict[str, Any]] = None
        self.current_asset_type_for_defaults: Optional[str] = None # This is the asset_editor_key from palette
        self.input_widgets: Dict[str, QWidget] = {}
        
        self._controller_has_focus = False
        self._controller_property_widgets_ordered: List[Tuple[str, QWidget, Optional[QLabel]]] = []
        self._controller_focused_property_index: int = -1

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(5,5,5,5)

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_widget = QWidget()
        self.form_layout = QFormLayout(self.scroll_widget)
        self.form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.form_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        self.form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.scroll_area.setWidget(self.scroll_widget)
        self.main_layout.addWidget(self.scroll_area)
        
        self.no_selection_label = QLabel("Select an object or asset to see properties.")
        self.no_selection_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.no_selection_label.setWordWrap(True)
        
        self.no_selection_container = QWidget()
        no_sel_layout = QVBoxLayout(self.no_selection_container)
        no_sel_layout.addWidget(self.no_selection_label)
        no_sel_layout.addStretch()
        self.form_layout.addRow(self.no_selection_container)
        self.clear_display()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def _clear_dynamic_widgets_from_form(self):
        self.input_widgets.clear()
        self._controller_property_widgets_ordered.clear()
        self._controller_focused_property_index = -1

        for i in range(self.form_layout.rowCount() -1, -1, -1):
            layout_item = self.form_layout.itemAt(i, QFormLayout.ItemRole.SpanningRole)
            if layout_item and layout_item.widget() is self.no_selection_container:
                continue

            label_item = self.form_layout.itemAt(i, QFormLayout.ItemRole.LabelRole)
            field_item = self.form_layout.itemAt(i, QFormLayout.ItemRole.FieldRole)

            if label_item and label_item.widget():
                label_item.widget().deleteLater()
            if field_item:
                if field_item.widget():
                    field_item.widget().deleteLater()
                elif field_item.layout():
                    inner_layout = field_item.layout()
                    while inner_layout.count():
                        child = inner_layout.takeAt(0)
                        if child.widget():
                            child.widget().deleteLater()
            
            if not label_item and not field_item and layout_item and layout_item.widget():
                 layout_item.widget().deleteLater()

            if not (layout_item and layout_item.widget() is self.no_selection_container):
                self.form_layout.removeRow(i)
        self._update_focused_property_visuals()

    @Slot(object)
    def display_map_object_properties(self, map_object_data_ref: Optional[Dict[str, Any]]):
        self._clear_dynamic_widgets_from_form()
        self.current_object_data_ref = None
        self.current_asset_type_for_defaults = None # Clear this when an object is selected
        if not map_object_data_ref or not isinstance(map_object_data_ref, dict):
            self.no_selection_label.setText("Select an object on the map to edit its properties.")
            self.no_selection_container.setVisible(True)
            self.scroll_widget.adjustSize()
            return
        self.no_selection_container.setVisible(False)
        self.current_object_data_ref = map_object_data_ref
        
        asset_editor_key = str(map_object_data_ref.get("asset_editor_key", "N/A"))
        game_type_id_str = str(map_object_data_ref.get("game_type_id", "Unknown"))
        display_name_for_title = game_type_id_str
        
        is_custom_image_type = (asset_editor_key == ED_CONFIG.CUSTOM_IMAGE_ASSET_KEY)
        is_trigger_square_type = (asset_editor_key == ED_CONFIG.TRIGGER_SQUARE_ASSET_KEY)

        if is_custom_image_type:
            display_name_for_title = "Custom Image"
            src_path = map_object_data_ref.get("source_file_path", "")
            if src_path:
                display_name_for_title += f" ({os.path.basename(src_path)})"
        elif is_trigger_square_type:
            display_name_for_title = "Trigger Square"
        else:
            asset_data_for_title = self.editor_state.assets_palette.get(asset_editor_key)
            if asset_data_for_title and asset_data_for_title.get("name_in_palette"):
                display_name_for_title = asset_data_for_title["name_in_palette"]
            elif "_" in display_name_for_title:
                display_name_for_title = display_name_for_title.replace("_", " ").title()
        
        title_label = QLabel(f"Object: {display_name_for_title}")
        font_title = title_label.font()
        font_title.setBold(True)
        font_title.setPointSize(ED_CONFIG.FONT_SIZE_MEDIUM) 
        title_label.setFont(font_title)
        self.form_layout.addRow(title_label)

        if not is_custom_image_type and not is_trigger_square_type:
            asset_key_label_text = QLabel("Asset Key:")
            asset_key_label_text.setWordWrap(True)
            asset_key_value_label = QLabel(asset_editor_key)
            asset_key_value_label.setWordWrap(True)
            self.form_layout.addRow(asset_key_label_text, asset_key_value_label)
        
        coords_label_text = QLabel("Coords (X,Y):")
        coords_label_text.setWordWrap(True)
        coords_value_label = QLabel(f"({map_object_data_ref.get('world_x')}, {map_object_data_ref.get('world_y')})")
        self.form_layout.addRow(coords_label_text, coords_value_label)

        if is_custom_image_type or is_trigger_square_type or \
           (asset_editor_key in self.editor_state.assets_palette and not asset_editor_key.startswith("tool_")): # Standard placeable assets
            self._create_property_field("layer_order",
                                        {"type": "int", "default": 0, "label": "Layer Order", "min": -100, "max": 100},
                                        map_object_data_ref.get("layer_order", 0), self.form_layout)
            if is_custom_image_type or is_trigger_square_type : # Only these have custom dimensions
                self._create_dimension_fields(map_object_data_ref, self.form_layout)

            if is_custom_image_type:
                self._create_crop_fields(map_object_data_ref, self.form_layout)
            
            # Add flip property for custom images, triggers (if they have images), and standard non-tool assets
            self._create_property_field("is_flipped_h",
                                        {"type": "bool", "default": False, "label": "Horizontally Flipped"},
                                        map_object_data_ref.get("is_flipped_h", False), self.form_layout)


        asset_palette_data = self.editor_state.assets_palette.get(asset_editor_key)
        if asset_palette_data and asset_palette_data.get("colorable") and \
           not is_custom_image_type and not is_trigger_square_type:
            color_label_text = QLabel("Color:")
            color_label_text.setWordWrap(True)
            color_button = QPushButton()
            self.input_widgets["_color_button"] = color_button
            self._update_color_button_visuals(color_button, map_object_data_ref)
            color_button.clicked.connect(lambda _checked=False, obj_ref=map_object_data_ref: self._change_object_color(obj_ref))
            self.form_layout.addRow(color_label_text, color_button)
            self._controller_property_widgets_ordered.append(("_color_button", color_button, color_label_text))

        object_custom_props = map_object_data_ref.get("properties", {})
        if not isinstance(object_custom_props, dict):
            object_custom_props = {}
            map_object_data_ref["properties"] = object_custom_props
        
        editable_vars_config_key = game_type_id_str
        if editable_vars_config_key and editable_vars_config_key in ED_CONFIG.EDITABLE_ASSET_VARIABLES: 
            prop_definitions = ED_CONFIG.EDITABLE_ASSET_VARIABLES[editable_vars_config_key] 
            if prop_definitions:
                props_group = QGroupBox("Object Properties") 
                props_group.setFlat(False)
                props_layout_internal = QFormLayout(props_group)
                props_layout_internal.setContentsMargins(6, 10, 6, 6)
                props_layout_internal.setSpacing(6)
                props_layout_internal.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
                props_layout_internal.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
                for var_name, definition in prop_definitions.items():
                    current_value = object_custom_props.get(var_name, definition["default"])
                    self._create_property_field(var_name, definition, current_value, props_layout_internal)
                self.form_layout.addRow(props_group)
        elif not is_custom_image_type and not is_trigger_square_type:
            no_props_label = QLabel("No custom properties for this object type.")
            self.form_layout.addRow(no_props_label)
        
        self.scroll_widget.adjustSize()
        if self._controller_has_focus:
            self._set_controller_focused_property(0)

    @Slot(str)
    def display_asset_properties(self, asset_key_or_custom_id: Optional[str]):
        """Displays properties for an asset type from the palette, not a placed object."""
        self._clear_dynamic_widgets_from_form()
        self.current_object_data_ref = None # Ensure no object is considered selected here
        self.current_asset_type_for_defaults = asset_key_or_custom_id

        if not asset_key_or_custom_id:
            if not self.current_object_data_ref: # Only show if no map object is selected either
                self.no_selection_label.setText("Select an object or asset...")
                self.no_selection_container.setVisible(True)
            self.scroll_widget.adjustSize()
            return
        
        self.no_selection_container.setVisible(False)
        
        asset_data: Optional[Dict] = None 
        display_name_for_title = asset_key_or_custom_id
        game_type_id_for_props: Optional[str] = None

        if asset_key_or_custom_id.startswith(ED_CONFIG.CUSTOM_ASSET_PALETTE_PREFIX): 
            # self.current_asset_type_for_defaults = asset_key_or_custom_id # Already set
            filename = asset_key_or_custom_id.split(ED_CONFIG.CUSTOM_ASSET_PALETTE_PREFIX)[1] 
            display_name_for_title = f"Custom Asset: {filename}"
            game_type_id_for_props = ED_CONFIG.CUSTOM_IMAGE_ASSET_KEY 
        else:
            # self.current_asset_type_for_defaults = asset_key_or_custom_id # Already set
            asset_data = self.editor_state.assets_palette.get(str(asset_key_or_custom_id))
            if not asset_data:
                self.scroll_widget.adjustSize()
                return # Should not happen if called from palette
            game_type_id_for_props = str(asset_data.get("game_type_id", "Unknown"))
            display_name_for_title = asset_data.get('name_in_palette', game_type_id_for_props)
            if display_name_for_title == game_type_id_for_props and "_" in display_name_for_title:
                display_name_for_title = display_name_for_title.replace("_", " ").title()
            
        title_label = QLabel(f"Asset Type: {display_name_for_title}")
        font_title = title_label.font()
        font_title.setBold(True)
        font_title.setPointSize(ED_CONFIG.FONT_SIZE_MEDIUM) 
        title_label.setFont(font_title)
        self.form_layout.addRow(title_label)

        if asset_data and asset_data.get("colorable"):
            colorable_label_text = QLabel("Colorable:")
            colorable_label_text.setWordWrap(True)
            colorable_info_label = QLabel("Yes (by tool or properties)")
            self.form_layout.addRow(colorable_label_text, colorable_info_label)
            default_color_val = asset_data.get("base_color_tuple")
            if not default_color_val: 
                _sp = asset_data.get("surface_params")
                if _sp and isinstance(_sp, tuple) and len(_sp) == 3: default_color_val = _sp[2] 
            if default_color_val:
                default_color_label_text = QLabel("Default Asset Color:")
                default_color_label_text.setWordWrap(True)
                default_color_value_label = QLabel(str(default_color_val))
                self.form_layout.addRow(default_color_label_text, default_color_value_label)


        if game_type_id_for_props and game_type_id_for_props in ED_CONFIG.EDITABLE_ASSET_VARIABLES: 
            props_group = QGroupBox("Default Editable Properties")
            props_group.setFlat(False)
            props_layout_internal = QFormLayout(props_group)
            props_layout_internal.setContentsMargins(6,10,6,6)
            props_layout_internal.setSpacing(6)
            props_layout_internal.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            props_layout_internal.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
            prop_definitions = ED_CONFIG.EDITABLE_ASSET_VARIABLES[game_type_id_for_props] 
            for var_name, definition in prop_definitions.items():
                prop_name_label = QLabel(definition.get('label', var_name.replace('_', ' ').title()) + ":")
                default_val_label = QLabel(str(definition["default"]))
                props_layout_internal.addRow(prop_name_label, default_val_label)
            self.form_layout.addRow(props_group)
        else:
            no_props_label = QLabel("No editable default properties for this asset type.")
            self.form_layout.addRow(no_props_label)
        
        self.scroll_widget.adjustSize()

    def display_custom_asset_palette_info(self, custom_asset_id: str): # This seems redundant with display_asset_properties
        self.display_asset_properties(custom_asset_id)

    def clear_display(self):
        self._clear_dynamic_widgets_from_form()
        self.current_object_data_ref = None
        self.current_asset_type_for_defaults = None
        self.no_selection_label.setText("Select an object on the map or an asset type from the palette to see its properties.")
        self.no_selection_container.setVisible(True)
        self.scroll_widget.adjustSize()

    def _update_color_button_visuals(self, button: QPushButton, object_data_ref: Optional[Dict[str, Any]]):
        if not object_data_ref:
            return
        color_tuple = object_data_ref.get("override_color")
        is_overridden = bool(color_tuple)
        _sp = None
        if not color_tuple:
            asset_key = object_data_ref.get("asset_editor_key")
            asset_palette_data = self.editor_state.assets_palette.get(str(asset_key))
            if asset_palette_data:
                color_tuple = asset_palette_data.get("base_color_tuple")
                if not color_tuple: _sp = asset_palette_data.get("surface_params")
                if _sp and isinstance(_sp, tuple) and len(_sp) == 3:
                    color_tuple = _sp[2] 
            if not color_tuple:
                color_tuple = (128,128,128)
        button_text = f"RGB: {color_tuple}"
        button.setText(button_text + (" (Default)" if not is_overridden else ""))
        if color_tuple:
            q_color = QColor(*color_tuple) 
            palette = button.palette()
            palette.setColor(QPalette.ColorRole.Button, q_color)
            luma = 0.299 * color_tuple[0] + 0.587 * color_tuple[1] + 0.114 * color_tuple[2] 
            text_q_color = QColor(Qt.GlobalColor.black) if luma > 128 else QColor(Qt.GlobalColor.white)
            palette.setColor(QPalette.ColorRole.ButtonText, text_q_color)
            button.setPalette(palette)
            button.setAutoFillBackground(True)
            border_style = "1px solid black"
            if self._controller_has_focus and self._controller_focused_property_index >= 0 and \
               self._controller_focused_property_index < len(self._controller_property_widgets_ordered) and \
               self._controller_property_widgets_ordered[self._controller_focused_property_index][1] is button:
                border_style = ED_CONFIG.PROPERTIES_EDITOR_CONTROLLER_FOCUS_BORDER 
            button.setStyleSheet(f"QPushButton {{ border: {border_style}; min-height: 20px; padding: 2px; }}")
            button.update()

    def _create_property_field(self, var_name: str, definition: Dict[str, Any], current_value: Any, layout: QFormLayout):
        label_text_for_field = definition.get("label", var_name.replace("_", " ").title())
        property_name_label = QLabel(label_text_for_field + ":")
        property_name_label.setWordWrap(True)
        widget: Optional[QWidget] = None
        prop_type = definition["type"]
        
        if prop_type == "int":
            spinner = QSpinBox()
            widget = spinner
            spinner.setMinimum(definition.get("min", -2147483648))
            spinner.setMaximum(definition.get("max", 2147483647))
            try: spinner.setValue(int(current_value))
            except (ValueError, TypeError): spinner.setValue(int(definition["default"]))
            spinner.valueChanged.connect(lambda val, vn=var_name: self._on_property_value_changed(vn, val))
        elif prop_type == "float":
            double_spinner = QDoubleSpinBox()
            widget = double_spinner
            double_spinner.setMinimum(definition.get("min", -1.79e+308))
            double_spinner.setMaximum(definition.get("max", 1.79e+308))
            try: double_spinner.setValue(float(current_value))
            except (ValueError, TypeError): double_spinner.setValue(float(definition["default"]))
            double_spinner.setDecimals(definition.get("decimals", 2))
            double_spinner.valueChanged.connect(lambda val, vn=var_name: self._on_property_value_changed(vn, val))
        elif prop_type == "str":
            if "options" in definition and isinstance(definition["options"], list):
                combo = QComboBox()
                widget = combo
                combo.addItems(definition["options"])
                try: combo.setCurrentIndex(definition["options"].index(str(current_value)))
                except ValueError: 
                    if str(definition["default"]) in definition["options"]:
                        combo.setCurrentText(str(definition["default"]))
                    elif definition["options"]:
                        combo.setCurrentIndex(0)
                combo.currentTextChanged.connect(lambda val, vn=var_name: self._on_property_value_changed(vn, val))
            else:
                line_edit = QLineEdit(str(current_value))
                widget = line_edit
                line_edit.editingFinished.connect(lambda le=line_edit, vn=var_name: self._on_line_edit_finished(vn, le.text()))
        elif prop_type == "bool":
            # For bool, the label is part of the checkbox itself for better layout
            checkbox = QCheckBox(label_text_for_field) # Use the field label for the checkbox text
            widget = checkbox
            try: checkbox.setChecked(bool(current_value))
            except (ValueError, TypeError): checkbox.setChecked(bool(definition["default"]))
            checkbox.stateChanged.connect(lambda state_int, vn=var_name: self._on_property_value_changed(vn, state_int == Qt.CheckState.Checked.value))
        
        elif prop_type == "tuple_color_rgba":
            color_val_prop = current_value if isinstance(current_value, (list,tuple)) and len(current_value) == 4 else definition["default"]
            color_button = QPushButton(str(color_val_prop))
            self._update_rgba_color_button_style(color_button, color_val_prop) 
            color_button.clicked.connect(lambda _ch, vn=var_name, btn=color_button: self._change_rgba_color_property(vn, btn))
            widget = color_button
        elif prop_type == "image_path_custom":
            hbox = QHBoxLayout()
            line_edit = QLineEdit(str(current_value))
            line_edit.setReadOnly(True)
            browse_button = QPushButton("Browse...")
            browse_button.clicked.connect(lambda _ch, vn=var_name: self._browse_for_trigger_image(vn))
            clear_button = QPushButton("Clear")
            clear_button.clicked.connect(lambda _ch, vn=var_name: self._clear_trigger_image(vn))
            hbox.addWidget(line_edit, 1)
            hbox.addWidget(browse_button)
            hbox.addWidget(clear_button)
            container_widget = QWidget()
            container_widget.setLayout(hbox)
            widget = container_widget
            self.input_widgets[f"{var_name}_lineedit"] = line_edit
        
        if widget:
            widget.setObjectName(f"prop_widget_{var_name}")
            if not isinstance(widget, QCheckBox): # Checkbox already has its label
                widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
                layout.addRow(property_name_label, widget)
                self._controller_property_widgets_ordered.append((var_name, widget, property_name_label))
            else: # QCheckBox takes the whole row
                layout.addRow(widget) 
                self._controller_property_widgets_ordered.append((var_name, widget, None)) # No separate label widget
            self.input_widgets[var_name] = widget
        else:
            layout.addRow(property_name_label, QLabel(f"Unsupported type: {prop_type}"))
    
    def _create_dimension_fields(self, obj_data_ref: Dict[str, Any], layout: QFormLayout):
        width_label = QLabel("Width:")
        width_label.setWordWrap(True)
        width_spinner = QSpinBox()
        width_spinner.setMinimum(int(ED_CONFIG.BASE_GRID_SIZE / 4)) 
        width_spinner.setMaximum(int(ED_CONFIG.BASE_GRID_SIZE * 100)) 
        width_spinner.setValue(int(obj_data_ref.get("current_width", ED_CONFIG.BASE_GRID_SIZE))) 
        width_spinner.valueChanged.connect(lambda val: self._on_dimension_changed("current_width", val))
        layout.addRow(width_label, width_spinner)
        self.input_widgets["current_width"] = width_spinner
        self._controller_property_widgets_ordered.append(("current_width", width_spinner, width_label))
        
        height_label = QLabel("Height:")
        height_label.setWordWrap(True)
        height_spinner = QSpinBox()
        height_spinner.setMinimum(int(ED_CONFIG.BASE_GRID_SIZE / 4)) 
        height_spinner.setMaximum(int(ED_CONFIG.BASE_GRID_SIZE * 100)) 
        height_spinner.setValue(int(obj_data_ref.get("current_height", ED_CONFIG.BASE_GRID_SIZE))) 
        height_spinner.valueChanged.connect(lambda val: self._on_dimension_changed("current_height", val))
        layout.addRow(height_label, height_spinner)
        self.input_widgets["current_height"] = height_spinner
        self._controller_property_widgets_ordered.append(("current_height", height_spinner, height_label))

    def _create_crop_fields(self, obj_data_ref: Dict[str, Any], parent_layout: QFormLayout):
        crop_group = QGroupBox("Image Cropping")
        crop_group.setFlat(False)
        crop_layout = QFormLayout(crop_group)
        crop_layout.setContentsMargins(6, 10, 6, 6)
        crop_layout.setSpacing(6)

        original_w = obj_data_ref.get("original_width", 0)
        original_h = obj_data_ref.get("original_height", 0)
        
        current_crop = obj_data_ref.get("crop_rect")
        crop_x_val = 0
        crop_y_val = 0
        crop_w_val = original_w
        crop_h_val = original_h

        if isinstance(current_crop, dict):
            crop_x_val = current_crop.get("x", 0)
            crop_y_val = current_crop.get("y", 0)
            crop_w_val = current_crop.get("width", original_w)
            crop_h_val = current_crop.get("height", original_h)

        crop_x_label = QLabel("Crop X:")
        crop_x_spinner = QSpinBox()
        crop_x_spinner.setMinimum(0)
        crop_x_spinner.setMaximum(max(0, original_w -1)) 
        crop_x_spinner.setValue(crop_x_val)
        crop_x_spinner.valueChanged.connect(self._on_crop_value_changed)
        crop_layout.addRow(crop_x_label, crop_x_spinner)
        self.input_widgets["crop_x"] = crop_x_spinner
        self._controller_property_widgets_ordered.append(("crop_x", crop_x_spinner, crop_x_label))

        crop_y_label = QLabel("Crop Y:")
        crop_y_spinner = QSpinBox()
        crop_y_spinner.setMinimum(0)
        crop_y_spinner.setMaximum(max(0, original_h - 1))
        crop_y_spinner.setValue(crop_y_val)
        crop_y_spinner.valueChanged.connect(self._on_crop_value_changed)
        crop_layout.addRow(crop_y_label, crop_y_spinner)
        self.input_widgets["crop_y"] = crop_y_spinner
        self._controller_property_widgets_ordered.append(("crop_y", crop_y_spinner, crop_y_label))

        crop_w_label = QLabel("Crop Width:")
        crop_w_spinner = QSpinBox()
        crop_w_spinner.setMinimum(1)
        crop_w_spinner.setMaximum(max(1, original_w))
        crop_w_spinner.setValue(crop_w_val)
        crop_w_spinner.valueChanged.connect(self._on_crop_value_changed)
        crop_layout.addRow(crop_w_label, crop_w_spinner)
        self.input_widgets["crop_width"] = crop_w_spinner
        self._controller_property_widgets_ordered.append(("crop_width", crop_w_spinner, crop_w_label))

        crop_h_label = QLabel("Crop Height:")
        crop_h_spinner = QSpinBox()
        crop_h_spinner.setMinimum(1)
        crop_h_spinner.setMaximum(max(1, original_h))
        crop_h_spinner.setValue(crop_h_val)
        crop_h_spinner.valueChanged.connect(self._on_crop_value_changed)
        crop_layout.addRow(crop_h_label, crop_h_spinner)
        self.input_widgets["crop_height"] = crop_h_spinner
        self._controller_property_widgets_ordered.append(("crop_height", crop_h_spinner, crop_h_label))

        reset_crop_button = QPushButton("Reset Crop to Full Image")
        reset_crop_button.clicked.connect(self._on_reset_crop)
        crop_layout.addRow(reset_crop_button)
        self.input_widgets["reset_crop"] = reset_crop_button
        self._controller_property_widgets_ordered.append(("reset_crop", reset_crop_button, None))
        
        parent_layout.addRow(crop_group)

    def _on_crop_value_changed(self):
        if not self.current_object_data_ref: return

        cx_spin = self.input_widgets.get("crop_x")
        cy_spin = self.input_widgets.get("crop_y")
        cw_spin = self.input_widgets.get("crop_width")
        ch_spin = self.input_widgets.get("crop_height")

        if not all(isinstance(s, QSpinBox) for s in [cx_spin, cy_spin, cw_spin, ch_spin]):
            logger.error("Crop spinners not found or not QSpinBox.")
            return

        new_crop_x = cx_spin.value() 
        new_crop_y = cy_spin.value() 
        new_crop_w = cw_spin.value() 
        new_crop_h = ch_spin.value() 

        original_w = self.current_object_data_ref.get("original_width", 0)
        original_h = self.current_object_data_ref.get("original_height", 0)
        
        if new_crop_w < 1 or new_crop_h < 1 or \
           new_crop_x < 0 or new_crop_y < 0 or \
           new_crop_x + new_crop_w > original_w or \
           new_crop_y + new_crop_h > original_h:
            logger.warning(f"Attempted to set invalid crop values: X={new_crop_x}, Y={new_crop_y}, W={new_crop_w}, H={new_crop_h} for original {original_w}x{original_h}")

        new_crop_rect = {
            "x": new_crop_x, "y": new_crop_y,
            "width": new_crop_w, "height": new_crop_h
        }
        
        current_rect = self.current_object_data_ref.get("crop_rect")
        if current_rect != new_crop_rect:
            editor_history.push_undo_state(self.editor_state)
            self.current_object_data_ref["crop_rect"] = new_crop_rect
            self.properties_changed.emit(self.current_object_data_ref)
            if logger: logger.debug(f"Crop rect changed to: {new_crop_rect}")

    def _on_reset_crop(self):
        if not self.current_object_data_ref: return

        if self.current_object_data_ref.get("crop_rect") is not None:
            editor_history.push_undo_state(self.editor_state)
            self.current_object_data_ref["crop_rect"] = None
            
            original_w = self.current_object_data_ref.get("original_width", 0)
            original_h = self.current_object_data_ref.get("original_height", 0)

            cx_spin = self.input_widgets.get("crop_x")
            cy_spin = self.input_widgets.get("crop_y")
            cw_spin = self.input_widgets.get("crop_width")
            ch_spin = self.input_widgets.get("crop_height")

            if isinstance(cx_spin, QSpinBox): cx_spin.setValue(0)
            if isinstance(cy_spin, QSpinBox): cy_spin.setValue(0)
            if isinstance(cw_spin, QSpinBox): cw_spin.setValue(original_w)
            if isinstance(ch_spin, QSpinBox): ch_spin.setValue(original_h)
            
            self.properties_changed.emit(self.current_object_data_ref)
            if logger: logger.debug("Crop rect reset to None (full image).")


    def _on_dimension_changed(self, dimension_key: str, new_value: int):
        if not self.current_object_data_ref:
            return
        if self.current_object_data_ref.get(dimension_key) != new_value:
            editor_history.push_undo_state(self.editor_state) 
            self.current_object_data_ref[dimension_key] = new_value
            self.properties_changed.emit(self.current_object_data_ref)

    def _update_rgba_color_button_style(self, button: QPushButton, color_tuple_rgba: Tuple[int,int,int,int]):
        if not color_tuple_rgba or len(color_tuple_rgba) != 4:
            button.setText("Invalid Color")
            button.setIcon(QIcon())
            return
        button.setText(f"RGBA: {color_tuple_rgba}")
        q_color = QColor(*color_tuple_rgba)
        
        btn_width = max(60, button.width())
        btn_height = max(20, button.height())

        pm = QPixmap(btn_width, btn_height)
        pm.fill(Qt.GlobalColor.transparent)
        checker_painter = QPainter(pm)
        checker_size = 8
        for y_coord in range(0, pm.height(), checker_size):
            for x_coord in range(0, pm.width(), checker_size):
                if (x_coord // checker_size + y_coord // checker_size) % 2 == 0:
                    checker_painter.fillRect(x_coord, y_coord, checker_size, checker_size, QColor(200,200,200))
                else:
                    checker_painter.fillRect(x_coord, y_coord, checker_size, checker_size, QColor(230,230,230))
        checker_painter.fillRect(pm.rect(), q_color)
        checker_painter.end()
        
        button.setIcon(QIcon(pm))
        button.setIconSize(QSize(btn_width - 8, btn_height - 8 ))
        
        luma = 0.299 * color_tuple_rgba[0] + 0.587 * color_tuple_rgba[1] + 0.114 * color_tuple_rgba[2]
        alpha = color_tuple_rgba[3]
        text_q_color = QColor(Qt.GlobalColor.black)
        if alpha > 128 and luma < 128 :
            text_q_color = QColor(Qt.GlobalColor.white)
        
        button.setStyleSheet(f"QPushButton {{ color: {text_q_color.name()}; text-align: left; padding-left: 5px; }}")

    def _change_rgba_color_property(self, var_name: str, button_ref: QPushButton):
        if not self.current_object_data_ref:
            return
        props = self.current_object_data_ref.get("properties", {})
        current_color_val = props.get(var_name, (0,0,0,255))
        
        dialog = QColorDialog(self)
        dialog.setOption(QColorDialog.ColorDialogOption.ShowAlphaChannel, True)
        dialog.setCurrentColor(QColor(*current_color_val)) 
        
        if dialog.exec():
            new_q_color = dialog.selectedColor()
            new_color_tuple_rgba = new_q_color.getRgb()
            
            if props.get(var_name) != new_color_tuple_rgba: 
                editor_history.push_undo_state(self.editor_state) 
                props[var_name] = new_color_tuple_rgba 
                self._update_rgba_color_button_style(button_ref, new_color_tuple_rgba) 
                self.properties_changed.emit(self.current_object_data_ref)

    def _browse_for_trigger_image(self, var_name: str):
        if not self.current_object_data_ref:
            return
        self.upload_image_for_trigger_requested.emit(self.current_object_data_ref)

    def _clear_trigger_image(self, var_name: str):
        if not self.current_object_data_ref:
            return
        props = self.current_object_data_ref.get("properties", {})
        if props.get(var_name, "") != "":
            editor_history.push_undo_state(self.editor_state) 
            props[var_name] = ""
            self.update_property_field_value(self.current_object_data_ref, var_name, "")
            self.properties_changed.emit(self.current_object_data_ref)

    def update_property_field_value(self, obj_data_ref: Dict[str, Any], prop_name: str, new_value: Any):
        if self.current_object_data_ref is not obj_data_ref:
            return
        
        widget_key_for_lineedit = f"{prop_name}_lineedit"
        widget = self.input_widgets.get(widget_key_for_lineedit) or self.input_widgets.get(prop_name)

        if isinstance(widget, QLineEdit):
            widget.setText(str(new_value))
        elif isinstance(widget, QSpinBox):
            widget.setValue(int(new_value))
        elif isinstance(widget, QDoubleSpinBox):
            widget.setValue(float(new_value))
        elif isinstance(widget, QCheckBox):
            widget.setChecked(bool(new_value))
        elif isinstance(widget, QComboBox):
            widget.setCurrentText(str(new_value))
        elif isinstance(widget, QPushButton) and prop_name.endswith("_color_rgba"):
             self._update_rgba_color_button_style(widget, new_value) 
        
        if logger: logger.debug(f"PropertiesEditor: Externally updated field '{prop_name}' to '{new_value}'")

    def _on_line_edit_finished(self, var_name: str, text_value: str):
        self._on_property_value_changed(var_name, text_value)

    def _on_property_value_changed(self, var_name: str, new_value: Any):
        if not self.current_object_data_ref:
            return
        
        target_dict_for_prop = self.current_object_data_ref
        # Check if var_name is a direct attribute or a sub-property in "properties"
        if var_name not in self.current_object_data_ref:
            if "properties" not in self.current_object_data_ref or \
               not isinstance(self.current_object_data_ref.get("properties"), dict):
                self.current_object_data_ref["properties"] = {}
            target_dict_for_prop = self.current_object_data_ref["properties"]
        
        game_type_id = str(self.current_object_data_ref.get("game_type_id"))
        definition: Optional[Dict] = None
        
        if var_name == "layer_order": definition = {"type": "int", "default": 0}
        elif var_name == "current_width": definition = {"type": "int", "default": ED_CONFIG.BASE_GRID_SIZE}
        elif var_name == "current_height": definition = {"type": "int", "default": ED_CONFIG.BASE_GRID_SIZE}
        elif var_name == "is_flipped_h": definition = {"type": "bool", "default": False}
        else: 
            definition = ED_CONFIG.EDITABLE_ASSET_VARIABLES.get(game_type_id, {}).get(var_name) 
        
        if not definition:
            if logger: logger.warning(f"No definition for prop '{var_name}' (GameID: '{game_type_id}'). Cannot process change.")
            return

        prop_type = definition["type"]
        current_stored_value = target_dict_for_prop.get(var_name, definition["default"])
        typed_new_value = new_value
        try:
            if prop_type == "int": typed_new_value = int(new_value)
            elif prop_type == "float": typed_new_value = float(new_value)
            elif prop_type == "bool": typed_new_value = bool(new_value)
            elif prop_type == "str": typed_new_value = str(new_value)
            elif prop_type == "tuple_color_rgba":
                if not (isinstance(new_value, (list, tuple)) and len(new_value) == 4):
                    raise ValueError("Invalid RGBA tuple for property change")
            elif prop_type == "image_path_custom":
                 typed_new_value = str(new_value)
        except (ValueError, TypeError) as e:
            if logger: logger.warning(f"Casting error for '{var_name}': '{new_value}' to {prop_type}. Error: {e}")
            widget_to_revert = self.input_widgets.get(var_name)
            if widget_to_revert and hasattr(widget_to_revert, 'setValue'): widget_to_revert.setValue(current_stored_value) 
            elif widget_to_revert and hasattr(widget_to_revert, 'setText'): widget_to_revert.setText(str(current_stored_value)) 
            return
        
        if current_stored_value != typed_new_value:
            editor_history.push_undo_state(self.editor_state) 
            target_dict_for_prop[var_name] = typed_new_value
            self.properties_changed.emit(self.current_object_data_ref)
            if logger: logger.debug(f"Property '{var_name}' changed to '{typed_new_value}'.")

    def _change_object_color(self, map_object_data_ref: Optional[Dict[str, Any]]):
        if not map_object_data_ref:
            return
        current_color_tuple = map_object_data_ref.get("override_color")
        _sp = None
        if not current_color_tuple:
            asset_key = map_object_data_ref.get("asset_editor_key")
            asset_palette_data = self.editor_state.assets_palette.get(str(asset_key))
            if asset_palette_data:
                current_color_tuple = asset_palette_data.get("base_color_tuple")
                if not current_color_tuple: _sp = asset_palette_data.get("surface_params")
                if _sp and isinstance(_sp, tuple) and len(_sp) == 3: current_color_tuple = _sp[2] 
            if not current_color_tuple: current_color_tuple = (128,128,128)
        q_current_color = QColor(*current_color_tuple) 
        new_q_color = QColorDialog.getColor(q_current_color, self, "Select Object Color")
        if new_q_color.isValid():
            new_color_tuple = new_q_color.getRgb()[:3] 
            if map_object_data_ref.get("override_color") != new_color_tuple:
                editor_history.push_undo_state(self.editor_state) 
                map_object_data_ref["override_color"] = new_color_tuple
                self.properties_changed.emit(map_object_data_ref)
                color_button = self.input_widgets.get("_color_button")
                if isinstance(color_button, QPushButton): self._update_color_button_visuals(color_button, map_object_data_ref)
    
    def _update_focused_property_visuals(self):
        for var_name, widget, label_widget in self._controller_property_widgets_ordered:
            if widget is self.input_widgets.get("_color_button"):
                self._update_color_button_visuals(widget, self.current_object_data_ref) 
            elif self.current_object_data_ref and self.current_object_data_ref.get("game_type_id"):
                definition = ED_CONFIG.EDITABLE_ASSET_VARIABLES.get(self.current_object_data_ref.get("game_type_id", ""), {}).get(var_name) 
                if definition and definition.get("type") == "tuple_color_rgba":
                     props = self.current_object_data_ref.get("properties", {})
                     self._update_rgba_color_button_style(widget, props.get(var_name, definition["default"])) 
                else:
                     widget.setStyleSheet("") 
            elif var_name.startswith("crop_") or var_name == "reset_crop": 
                widget.setStyleSheet("") 
            else: 
                widget.setStyleSheet("")


            if label_widget:
                label_widget.setStyleSheet("")

        if self._controller_has_focus and self._controller_focused_property_index >= 0 and \
           self._controller_focused_property_index < len(self._controller_property_widgets_ordered):
            var_name, widget, label_widget = self._controller_property_widgets_ordered[self._controller_focused_property_index]
            focus_style_str = str(ED_CONFIG.PROPERTIES_EDITOR_CONTROLLER_FOCUS_BORDER) 
            
            if widget is not self.input_widgets.get("_color_button"):
                if self.current_object_data_ref and self.current_object_data_ref.get("game_type_id"):
                    definition = ED_CONFIG.EDITABLE_ASSET_VARIABLES.get(self.current_object_data_ref.get("game_type_id", ""), {}).get(var_name) 
                    if not (definition and definition.get("type") == "tuple_color_rgba"): 
                        widget.setStyleSheet(f"border: {focus_style_str};")
                elif not var_name.startswith("crop_") and not var_name == "reset_crop": 
                     widget.setStyleSheet(f"border: {focus_style_str};")


            if label_widget:
                 label_widget.setStyleSheet("QLabel { color: " + focus_style_str.split(' ')[-1] + "; font-weight: bold; }")
            
            widget.setFocus(Qt.FocusReason.OtherFocusReason)
            self.scroll_area.ensureWidgetVisible(widget, 10, 10)

    def _set_controller_focused_property(self, index: int):
        if not self._controller_property_widgets_ordered:
            self._controller_focused_property_index = -1
            return
        new_index = max(0, min(index, len(self._controller_property_widgets_ordered) - 1))
        if self._controller_focused_property_index == new_index and self._controller_has_focus:
             return
        self._controller_focused_property_index = new_index
        self._update_focused_property_visuals()
        if logger: logger.debug(f"PropertiesEditor: Controller focus on property index {new_index}")

    def on_controller_focus_gained(self):
        self._controller_has_focus = True
        if self._controller_property_widgets_ordered:
            self._set_controller_focused_property(0)
        else:
            self._controller_focused_property_index = -1
        self._update_focused_property_visuals()
        if logger: logger.debug("PropertiesEditor: Controller focus gained.")

    def on_controller_focus_lost(self):
        self._controller_has_focus = False
        if self._controller_focused_property_index >= 0 and \
           self._controller_focused_property_index < len(self._controller_property_widgets_ordered):
            var_name, widget, label_widget = self._controller_property_widgets_ordered[self._controller_focused_property_index]
            
            if widget is not self.input_widgets.get("_color_button"):
                if self.current_object_data_ref and self.current_object_data_ref.get("game_type_id"):
                    definition = ED_CONFIG.EDITABLE_ASSET_VARIABLES.get(self.current_object_data_ref.get("game_type_id", ""), {}).get(var_name) 
                    if definition and definition.get("type") == "tuple_color_rgba":
                        props = self.current_object_data_ref.get("properties",{})
                        self._update_rgba_color_button_style(widget, props.get(var_name, definition["default"])) 
                    else:
                        widget.setStyleSheet("") 
                elif var_name.startswith("crop_") or var_name == "reset_crop":
                     widget.setStyleSheet("")
                else:
                     widget.setStyleSheet("")
            else: 
                self._update_color_button_visuals(widget, self.current_object_data_ref) 

            if label_widget:
                label_widget.setStyleSheet("")
        self._controller_focused_property_index = -1 
        if logger: logger.debug("PropertiesEditor: Controller focus lost.")

    def handle_controller_action(self, action: str, value: Any):
        if not self._controller_has_focus or not self._controller_property_widgets_ordered:
            if action == ACTION_UI_TAB_NEXT or action == ACTION_UI_TAB_PREV:
                self.controller_focus_requested_elsewhere.emit()
            return

        current_idx = self._controller_focused_property_index
        if not (0 <= current_idx < len(self._controller_property_widgets_ordered)):
            if self._controller_property_widgets_ordered:
                self._set_controller_focused_property(0) 
            return 

        var_name, widget, _ = self._controller_property_widgets_ordered[current_idx]

        if action == ACTION_UI_UP:
            self._set_controller_focused_property(current_idx - 1)
        elif action == ACTION_UI_DOWN:
            self._set_controller_focused_property(current_idx + 1)
        elif action == ACTION_UI_ACCEPT:
            if isinstance(widget, QPushButton):
                widget.click()
            elif isinstance(widget, QCheckBox):
                widget.toggle()
            elif isinstance(widget, QComboBox):
                widget.showPopup()
            elif isinstance(widget, QWidget) and widget.layout() is not None: 
                 children_buttons = widget.findChildren(QPushButton)
                 if children_buttons:
                     children_buttons[0].click()
        elif action == ACTION_UI_LEFT or action == ACTION_UI_RIGHT:
            step = 1 if action == ACTION_UI_RIGHT else -1
            if isinstance(widget, QSpinBox):
                new_val = widget.value() + step * widget.singleStep()
                if new_val >= widget.minimum() and new_val <= widget.maximum():
                    widget.setValue(new_val)
            elif isinstance(widget, QDoubleSpinBox):
                new_val = widget.value() + step * widget.singleStep()
                if new_val >= widget.minimum() and new_val <= widget.maximum():
                    widget.setValue(new_val)
            elif isinstance(widget, QComboBox):
                new_combo_idx = widget.currentIndex() + step
                if 0 <= new_combo_idx < widget.count():
                    widget.setCurrentIndex(new_combo_idx)
        elif action == ACTION_UI_TAB_NEXT or action == ACTION_UI_TAB_PREV:
            self.controller_focus_requested_elsewhere.emit()
            
#################### END OF FILE: editor_ui_panels.py ####################