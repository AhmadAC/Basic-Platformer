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
            # If "Custom" is already an option OR if no specific map is loaded (meaning "Custom" shouldn't be an option yet anyway), skip repopulating
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
                all_asset_categories.discard("Custom") # Remove "Custom" so it's not added again
            elif cat_name_ordered in all_asset_categories:
                combo_items.append(cat_name_ordered.title()) # Use title case for display
                all_asset_categories.discard(cat_name_ordered)

        # Add any remaining categories not in the predefined order, sorted alphabetically
        for remaining_cat in sorted(list(all_asset_categories)):
             combo_items.append(remaining_cat.title())

        self.category_filter_combo.blockSignals(True)
        current_text_selection = self.category_filter_combo.currentText()
        self.category_filter_combo.clear()
        self.category_filter_combo.addItems(combo_items)
        idx = self.category_filter_combo.findText(current_text_selection)
        self.category_filter_combo.setCurrentIndex(idx if idx != -1 else 0) # Restore selection or default to "All"
        self.category_filter_combo.blockSignals(False)
        self.categories_populated_in_combo = True

    def _get_pixmap_for_palette_item(self, asset_key: str, asset_data: Dict[str, Any]) -> QPixmap:
        effective_asset_key_for_icon = asset_key
        # If the current asset_key being processed is the one selected in the editor_state for placement,
        # and it's the base wall key, get the icon for the currently selected wall variant.
        if asset_key == self.editor_state.palette_current_asset_key:
            if asset_key == ED_CONFIG.WALL_BASE_KEY:
                if 0 <= self.editor_state.palette_wall_variant_index < len(ED_CONFIG.WALL_VARIANTS_CYCLE):
                    effective_asset_key_for_icon = ED_CONFIG.WALL_VARIANTS_CYCLE[self.editor_state.palette_wall_variant_index]

        asset_data_for_icon = self.editor_state.assets_palette.get(effective_asset_key_for_icon, asset_data)

        pixmap_for_palette: Optional[QPixmap] = None
        if asset_key.startswith(ED_CONFIG.CUSTOM_ASSET_PALETTE_PREFIX):
            # Custom assets store the full path in 'source_file'
            temp_qimage = QImage(asset_data_for_icon["source_file"])
            if not temp_qimage.isNull():
                asset_data_for_icon["original_size_pixels"] = (temp_qimage.width(), temp_qimage.height()) # Store original size if not already present
                pixmap_for_palette = get_asset_pixmap(asset_key, asset_data_for_icon,
                                                      QSize(ED_CONFIG.ASSET_THUMBNAIL_SIZE, ED_CONFIG.ASSET_THUMBNAIL_SIZE),
                                                      get_native_size_only=False,
                                                      is_flipped_h=False, rotation=0)
        else:
            data_for_get_pixmap = self.editor_state.assets_palette.get(effective_asset_key_for_icon, asset_data_for_icon)
            pixmap_for_palette = get_asset_pixmap(effective_asset_key_for_icon,
                                                 data_for_get_pixmap,
                                                 QSize(ED_CONFIG.ASSET_THUMBNAIL_SIZE, ED_CONFIG.ASSET_THUMBNAIL_SIZE),
                                                 get_native_size_only=False,
                                                 is_flipped_h=False, rotation=0)

        if not pixmap_for_palette or pixmap_for_palette.isNull():
            logger.warning(f"Could not load/create pixmap for palette item: {asset_key}. Using placeholder.")
            pixmap_for_palette = QPixmap(ED_CONFIG.ASSET_THUMBNAIL_SIZE, ED_CONFIG.ASSET_THUMBNAIL_SIZE)
            pixmap_for_palette.fill(Qt.GlobalColor.magenta) # Fallback placeholder
        return pixmap_for_palette


    def populate_assets(self, filter_override: Optional[str] = None):
        self._populate_category_combo_if_needed()
        current_filter_text = filter_override if filter_override is not None else self.category_filter_combo.currentText()
        
        asset_key_to_reselect = self.editor_state.palette_current_asset_key

        self.asset_list_widget.clear()
        
        item_cell_width = 85 # Approximate width for icon + padding + short text line
        item_cell_height = ED_CONFIG.ASSET_THUMBNAIL_SIZE + 20 # Thumbnail height + padding + one line for text (if view mode was different)
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
                                "source_file": full_path, # Store full path for custom assets
                                "name_in_palette": filename,
                                "category": "Custom",
                                "game_type_id": ED_CONFIG.CUSTOM_IMAGE_ASSET_KEY,
                                "original_size_pixels": None # Will be determined by _get_pixmap_for_palette_item
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
                   category.title().lower() == current_filter_text.lower(): # Match title case too
                    assets_to_display_tuples.append((key, data))
        
        # Sort assets based on category order, then by key
        assets_to_display_tuples.sort(key=lambda x: (ED_CONFIG.EDITOR_PALETTE_ASSETS_CATEGORIES_ORDER.index(x[1].get("category", "unknown"))
                                                     if x[1].get("category", "unknown") in ED_CONFIG.EDITOR_PALETTE_ASSETS_CATEGORIES_ORDER else 99,
                                                     x[0]))

        # Populate the QListWidget
        newly_selected_q_item: Optional[QListWidgetItem] = None
        for idx, (key, data) in enumerate(assets_to_display_tuples):
            pixmap_for_item = self._get_pixmap_for_palette_item(key, data)
            
            item_text_for_tooltip = data.get("name_in_palette", key.replace("_", " ").title())
            list_item = QListWidgetItem(QIcon(pixmap_for_item), "") # Text is usually shown by tooltip in IconMode
            list_item.setToolTip(item_text_for_tooltip)
            list_item.setData(Qt.ItemDataRole.UserRole, key) # Store the asset key
            self.asset_list_widget.addItem(list_item)

            if key == asset_key_to_reselect:
                newly_selected_q_item = list_item

        # Set selection
        if newly_selected_q_item:
            self.asset_list_widget.setCurrentItem(newly_selected_q_item)
            self._controller_list_current_index = self.asset_list_widget.row(newly_selected_q_item)
        elif self.asset_list_widget.count() > 0:
            # Fallback selection if the reselect_key wasn't found
            if 0 <= self._controller_list_current_index < self.asset_list_widget.count():
                self.asset_list_widget.setCurrentRow(self._controller_list_current_index)
            else:
                self.asset_list_widget.setCurrentRow(0)
                self._controller_list_current_index = 0
            newly_selected_q_item = self.asset_list_widget.currentItem()
        else: # List is empty
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
        self.editor_state.current_tool_mode = "place" # Default to place mode when an asset is clicked

        # Update editor state directly
        self.editor_state.palette_current_asset_key = asset_key_or_custom_id
        self.editor_state.palette_asset_is_flipped_h = False # Reset orientation on new selection
        self.editor_state.palette_asset_rotation = 0
        
        if asset_key_or_custom_id == ED_CONFIG.WALL_BASE_KEY:
            self.editor_state.palette_wall_variant_index = 0 # Reset wall variant for base wall
        # For other assets, palette_wall_variant_index is not directly used,
        # but could be reset for consistency if needed, though current code doesn't imply this.

        self.asset_info_selected.emit(asset_key_or_custom_id) # For properties panel

        if asset_key_or_custom_id.startswith("tool_"):
            self.editor_state.current_tool_mode = asset_key_or_custom_id
            self.tool_selected.emit(asset_key_or_custom_id)
            self.show_status_message(f"Tool selected: {display_name_for_status}")
        else:
            self.asset_selected_for_placement.emit(
                str(self.editor_state.palette_current_asset_key),
                self.editor_state.palette_asset_is_flipped_h,
                self.editor_state.palette_wall_variant_index,
                self.editor_state.palette_asset_rotation
            )
            status_msg = f"Asset for placement: {display_name_for_status}"
            if self.editor_state.palette_current_asset_key == ED_CONFIG.WALL_BASE_KEY:
                # Get the name of the current wall variant for the status message
                effective_key_for_variant = ED_CONFIG.WALL_VARIANTS_CYCLE[self.editor_state.palette_wall_variant_index]
                variant_data = self.editor_state.assets_palette.get(effective_key_for_variant)
                if variant_data: status_msg += f" ({variant_data.get('name_in_palette', effective_key_for_variant)})"
            
            self.show_status_message(f"{status_msg} (Default Orientation)")
        
        self.populate_assets() # Repopulate to update icons (e.g., if wall variant changed active icon)


    @Slot(QListWidgetItem, QPoint)
    def on_item_right_clicked(self, item: QListWidgetItem, global_pos: QPoint):
        if not (item.flags() & Qt.ItemFlag.ItemIsEnabled):
            return
        
        asset_key_clicked = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(asset_key_clicked, str) or asset_key_clicked.startswith("tool_"):
            # Right-click doesn't apply to tools
            return

        # Ensure this item is selected as the current one for placement if it's not already
        if self.editor_state.palette_current_asset_key != asset_key_clicked:
            self.editor_state.palette_current_asset_key = asset_key_clicked
            self.editor_state.palette_asset_is_flipped_h = False
            self.editor_state.palette_asset_rotation = 0
            if asset_key_clicked == ED_CONFIG.WALL_BASE_KEY:
                self.editor_state.palette_wall_variant_index = 0
            else: # For non-wall assets, wall_variant_index is not used but can be reset
                self.editor_state.palette_wall_variant_index = 0
            self.asset_info_selected.emit(asset_key_clicked) # Update properties panel for the new selection
        
        # Cycle wall variant if it's the wall base key
        if self.editor_state.palette_current_asset_key == ED_CONFIG.WALL_BASE_KEY:
            num_variants = len(ED_CONFIG.WALL_VARIANTS_CYCLE)
            if num_variants > 0:
                self.editor_state.palette_wall_variant_index = (self.editor_state.palette_wall_variant_index + 1) % num_variants
            
            effective_key_variant = ED_CONFIG.WALL_VARIANTS_CYCLE[self.editor_state.palette_wall_variant_index]
            variant_data = self.editor_state.assets_palette.get(effective_key_variant)
            variant_name = variant_data.get('name_in_palette', effective_key_variant) if variant_data else effective_key_variant
            self.show_status_message(f"Wall variant (palette): {variant_name}")
        
        # Repopulate to update the icon of the selected wall item (if it changed)
        self.populate_assets()
        
        # Emit signal for placement preview with the new state (e.g., new wall variant)
        if self.editor_state.palette_current_asset_key and not asset_key_clicked.startswith("tool_"):
            self.asset_selected_for_placement.emit(
                str(self.editor_state.palette_current_asset_key), # Still emit the base key for walls
                self.editor_state.palette_asset_is_flipped_h,
                self.editor_state.palette_wall_variant_index,
                self.editor_state.palette_asset_rotation
            )

    def show_status_message(self, message: str, timeout: int = 3000):
        if hasattr(self.parent_window, "show_status_message"):
            self.parent_window.show_status_message(message, timeout)
        else:
            logger.info(f"Status (AssetPalette): {message}")
    
    def clear_selection(self):
        self.asset_list_widget.clearSelection()
        # Reset editor state for palette selection
        self.editor_state.palette_current_asset_key = None
        self.editor_state.palette_asset_is_flipped_h = False
        self.editor_state.palette_asset_rotation = 0
        self.editor_state.palette_wall_variant_index = 0
        
        # Reset controller's focus index within the list
        if self.asset_list_widget.count() > 0:
            self._controller_list_current_index = 0 # Default to first item if list exists
        else:
            self._controller_list_current_index = -1
        
        self._update_sub_focus_visuals() # Update visual styles
        self.populate_assets() # Repopulate to reflect cleared selection


    def _update_sub_focus_visuals(self):
        # Reset styles first
        list_border = "1px solid transparent" # Default border for list
        combo_border = "1px solid gray"       # Default border for combo
        
        # Base styles that should always apply
        selected_item_style = "QListWidget::item:selected { border: 1px solid #007ACC; background-color: #c0d5eA; color: black; }"
        
        self.asset_list_widget.setStyleSheet(f"""
            {selected_item_style}
            QListWidget {{ border: {list_border}; }}
        """)
        self.category_filter_combo.setStyleSheet(f"QComboBox {{ border: {combo_border}; }}")
        self._update_paint_color_button_visuals() # This applies its own focus border if needed

        if self._controller_has_focus:
            focus_border_style_str = str(ED_CONFIG.ASSET_PALETTE_CONTROLLER_SUBFOCUS_BORDER)
            if self._controller_sub_focus_index == self.SUBFOCUS_LIST:
                self.asset_list_widget.setStyleSheet(f"""
                    {selected_item_style}
                    QListWidget {{ border: {focus_border_style_str}; }}
                """)
                if self.asset_list_widget.count() > 0:
                    self.asset_list_widget.setFocus() # Give Qt focus
            elif self._controller_sub_focus_index == self.SUBFOCUS_CATEGORY_COMBO:
                self.category_filter_combo.setStyleSheet(f"QComboBox {{ border: {focus_border_style_str}; }}")
                self.category_filter_combo.setFocus() # Give Qt focus
            elif self._controller_sub_focus_index == self.SUBFOCUS_PAINT_COLOR_BTN:
                # _update_paint_color_button_visuals already handles focused style
                self.paint_color_button.setFocus() # Give Qt focus

    def on_controller_focus_gained(self):
        self._controller_has_focus = True
        # Default to list focus when palette gains controller focus
        self._controller_sub_focus_index = self.SUBFOCUS_LIST 
        
        if self.asset_list_widget.count() > 0:
            item_to_select_by_controller: Optional[QListWidgetItem] = None
            
            # Try to select item based on editor_state's current palette selection
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
                # Fallback to _controller_list_current_index if main state key not found
                self.asset_list_widget.setCurrentRow(self._controller_list_current_index)
                item_to_select_by_controller = self.asset_list_widget.item(self._controller_list_current_index)
            else: # Further fallback to the first item
                 self.asset_list_widget.setCurrentRow(0)
                 self._controller_list_current_index = 0
                 item_to_select_by_controller = self.asset_list_widget.item(0)

            if item_to_select_by_controller: # Ensure the selected item is visible
                self.asset_list_widget.scrollToItem(item_to_select_by_controller, QAbstractItemView.ScrollHint.EnsureVisible)
        
        self._update_sub_focus_visuals()
        logger.debug("AssetPalette: Controller focus gained.")

    def on_controller_focus_lost(self):
        self._controller_has_focus = False
        self._update_sub_focus_visuals() # Reset focus styles
        logger.debug("AssetPalette: Controller focus lost.")

    def handle_controller_action(self, action: str, value: Any):
        if not self._controller_has_focus:
            return

        if self._controller_sub_focus_index == self.SUBFOCUS_LIST:
            count = self.asset_list_widget.count()
            if count == 0: # No items in list
                if action == ACTION_UI_TAB_NEXT or action == ACTION_UI_RIGHT: self._cycle_sub_focus(1)
                elif action == ACTION_UI_TAB_PREV or action == ACTION_UI_LEFT: self._cycle_sub_focus(-1)
                return

            # Determine grid dimensions for Up/Down navigation
            # This assumes items are roughly same size, which setUniformItemSizes helps with.
            num_cols = 1
            if self.asset_list_widget.gridSize().width() > 0:
                num_cols = self.asset_list_widget.width() // self.asset_list_widget.gridSize().width()
            num_cols = max(1, num_cols) # Ensure at least 1 column

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
                    self.on_item_left_clicked(item) # Simulate left click
            elif action == ACTION_UI_CANCEL: # Simulate right click for variant cycling etc.
                item = self.asset_list_widget.item(self._controller_list_current_index)
                if item:
                    self.on_item_right_clicked(item, self.asset_list_widget.visualItemRect(item).center())
            elif action == ACTION_UI_TAB_NEXT: self._cycle_sub_focus(1)
            elif action == ACTION_UI_TAB_PREV: self._cycle_sub_focus(-1)
            
            # Ensure index is valid and update selection
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
                self.category_filter_combo.showPopup() # Open the combo box
            elif action == ACTION_UI_TAB_NEXT: self._cycle_sub_focus(1)
            elif action == ACTION_UI_TAB_PREV: self._cycle_sub_focus(-1)

        elif self._controller_sub_focus_index == self.SUBFOCUS_PAINT_COLOR_BTN:
            if action == ACTION_UI_ACCEPT:
                self.paint_color_button.click() # Activate the button
            elif action == ACTION_UI_TAB_NEXT: self._cycle_sub_focus(1)
            elif action == ACTION_UI_TAB_PREV: self._cycle_sub_focus(-1)
        
        self._update_sub_focus_visuals() # Update styles after action

    def _cycle_sub_focus(self, direction: int):
        num_sub_items = 3 # List, Category Combo, Paint Button
        self._controller_sub_focus_index = (self._controller_sub_focus_index + direction + num_sub_items) % num_sub_items
        self._update_sub_focus_visuals()
        logger.debug(f"AssetPalette: Sub-focus cycled to index {self._controller_sub_focus_index}")