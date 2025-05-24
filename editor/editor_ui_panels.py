#################### START OF FILE: editor_ui_panels.py ####################

# editor_ui_panels.py
# -*- coding: utf-8 -*-
"""
Custom Qt Widgets for UI Panels (Asset Palette, Properties Editor)
in the PySide6 Level Editor.
Version 2.0.9 (Controller Navigation Foundations)
"""
import logging
from typing import Optional, Dict, Any, List, Tuple

from PySide6.QtWidgets import (
    QWidget, QListWidget, QListWidgetItem, QVBoxLayout, QHBoxLayout, 
    QLabel, QLineEdit, QCheckBox, QComboBox, QPushButton, QScrollArea,
    QFormLayout, QSpinBox, QDoubleSpinBox, QColorDialog,
    QGroupBox, QSizePolicy, QApplication, QAbstractItemView
)
from PySide6.QtGui import QIcon, QPalette, QColor, QPixmap, QFocusEvent, QKeyEvent, QPainter
from PySide6.QtCore import Qt, Signal, Slot, QSize

from . import editor_config as ED_CONFIG # Use relative import
from .editor_state import EditorState # Use relative import
from . import editor_history # Use relative import
# MODIFIED: Import editor action constants from editor_actions.py
from .editor_actions import (ACTION_UI_UP, ACTION_UI_DOWN, ACTION_UI_LEFT, ACTION_UI_RIGHT,
                             ACTION_UI_ACCEPT, ACTION_UI_CANCEL, ACTION_UI_TAB_NEXT, ACTION_UI_TAB_PREV)


logger = logging.getLogger(__name__) # Uses logger configured in editor.py

class AssetPaletteWidget(QWidget):
    asset_selected = Signal(str)
    tool_selected = Signal(str)
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

        self.asset_list_widget = QListWidget(self)
        self.asset_list_widget.setIconSize(QSize(ED_CONFIG.ASSET_PALETTE_ICON_SIZE_W, ED_CONFIG.ASSET_PALETTE_ICON_SIZE_H)) # type: ignore
        self.asset_list_widget.setViewMode(QListWidget.ViewMode.IconMode)
        self.asset_list_widget.setFlow(QListWidget.Flow.LeftToRight)
        self.asset_list_widget.setWrapping(True)
        self.asset_list_widget.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.asset_list_widget.setSpacing(5) 
        self.asset_list_widget.itemClicked.connect(self.on_item_clicked)
        self.asset_list_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.asset_list_widget.setObjectName("AssetListWidget") 
        self.asset_list_widget.setStyleSheet("""
            QListWidget::item { padding: 4px; border: 1px solid transparent; }
            QListWidget::item:hover { background-color: #e0e0e0; }
            QListWidget::item:selected { border: 1px solid #333; background-color: #c0d5eA; }
        """)
        self.main_layout.addWidget(self.asset_list_widget)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def _update_paint_color_button_visuals(self):
        color_tuple = self.editor_state.current_selected_asset_paint_color
        self.paint_color_button.setText("Paint Color") 
        base_style = "QPushButton { min-height: 20px; padding: 2px; }"
        focus_border_style = ""
        if self._controller_has_focus and self._controller_sub_focus_index == self.SUBFOCUS_PAINT_COLOR_BTN:
            focus_border_style = f"border: {ED_CONFIG.ASSET_PALETTE_CONTROLLER_SUBFOCUS_BORDER};" # type: ignore
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
            if app_instance: self.paint_color_button.setPalette(app_instance.style().standardPalette())
            else: self.paint_color_button.setPalette(QWidget().palette())
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
        if self.categories_populated_in_combo or not self.editor_state.assets_palette: return
        all_asset_categories = set()
        for data in self.editor_state.assets_palette.values():
            all_asset_categories.add(data.get("category", "unknown"))
        combo_items = ["All"]
        for cat_name_ordered in ED_CONFIG.EDITOR_PALETTE_ASSETS_CATEGORIES_ORDER: # type: ignore
            if cat_name_ordered in all_asset_categories:
                combo_items.append(cat_name_ordered.title())
                all_asset_categories.discard(cat_name_ordered)
        for remaining_cat in sorted(list(all_asset_categories)):
             combo_items.append(remaining_cat.title())
        self.category_filter_combo.blockSignals(True)
        current_text_selection = self.category_filter_combo.currentText()
        self.category_filter_combo.clear(); self.category_filter_combo.addItems(combo_items)
        idx = self.category_filter_combo.findText(current_text_selection)
        self.category_filter_combo.setCurrentIndex(idx if idx != -1 else 0)
        self.category_filter_combo.blockSignals(False)
        self.categories_populated_in_combo = True

    def populate_assets(self, filter_override: Optional[str] = None):
        self._populate_category_combo_if_needed()
        current_filter_text = filter_override if filter_override is not None else self.category_filter_combo.currentText()
        
        old_selected_asset_key: Optional[str] = None
        if self.asset_list_widget.currentItem():
            old_selected_asset_key = self.asset_list_widget.currentItem().data(Qt.ItemDataRole.UserRole) # type: ignore

        self.asset_list_widget.clear()
        if not self.editor_state.assets_palette: return
        
        item_cell_width = 85 
        item_cell_height = ED_CONFIG.ASSET_PALETTE_ICON_SIZE_H + 20  # type: ignore
        self.asset_list_widget.setGridSize(QSize(item_cell_width, item_cell_height))
        self.asset_list_widget.setUniformItemSizes(True)
        assets_to_display: List[Tuple[str, Dict[str, Any]]] = []
        for key, data in self.editor_state.assets_palette.items():
            category = data.get("category", "unknown")
            if current_filter_text.lower() == "all" or \
               category.lower() == current_filter_text.lower() or \
               category.title().lower() == current_filter_text.lower():
                assets_to_display.append((key, data))
        assets_to_display.sort(key=lambda x: x[0]) # Sort by key for consistent order

        new_selected_item_index = -1
        for idx, (key, data) in enumerate(assets_to_display):
            pixmap: Optional[QPixmap] = data.get("q_pixmap")
            if pixmap and not pixmap.isNull():
                item_text_for_tooltip = data.get("name_in_palette", key.replace("_", " ").title())
                list_item = QListWidgetItem(QIcon(pixmap), "") 
                list_item.setToolTip(item_text_for_tooltip) 
                list_item.setData(Qt.ItemDataRole.UserRole, key)
                self.asset_list_widget.addItem(list_item)
                if key == old_selected_asset_key:
                    new_selected_item_index = idx
        
        if self.asset_list_widget.count() > 0:
            if new_selected_item_index != -1:
                self._controller_list_current_index = new_selected_item_index
            elif self._controller_list_current_index >= self.asset_list_widget.count():
                 self._controller_list_current_index = self.asset_list_widget.count() -1
            elif self._controller_list_current_index < 0:
                 self._controller_list_current_index = 0
            
            self.asset_list_widget.setCurrentRow(self._controller_list_current_index)
        else:
            self._controller_list_current_index = -1

        self._update_sub_focus_visuals()

    @Slot(int)
    def _on_category_filter_changed(self, index: int):
        self.populate_assets()

    @Slot(QListWidgetItem)
    def on_item_clicked(self, item: QListWidgetItem):
        if not (item.flags() & Qt.ItemFlag.ItemIsEnabled): return
        self._controller_list_current_index = self.asset_list_widget.row(item) # Sync controller index
        asset_key = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(asset_key, str):
            asset_data = self.editor_state.assets_palette.get(asset_key)
            if asset_data:
                current_name = asset_data.get("name_in_palette", asset_key)
                if asset_data.get("category") == "tool" or str(asset_data.get("game_type_id", "")).startswith("tool_"):
                    self.tool_selected.emit(asset_key)
                    if hasattr(self.parent_window, 'show_status_message'): self.parent_window.show_status_message(f"Tool selected: {current_name}") # type: ignore
                else:
                    self.asset_selected.emit(asset_key)
                    if hasattr(self.parent_window, 'show_status_message'): self.parent_window.show_status_message(f"Asset selected: {current_name}") # type: ignore
    
    def clear_selection(self):
        self.asset_list_widget.clearSelection()
        if self.asset_list_widget.count() > 0:
            self._controller_list_current_index = 0
            self.asset_list_widget.setCurrentRow(0) 
        else:
            self._controller_list_current_index = -1
        self._update_sub_focus_visuals()

    def _update_sub_focus_visuals(self):
        list_border = "1px solid transparent"
        combo_border = "1px solid gray"
        # Paint button border is handled by _update_paint_color_button_visuals

        if self._controller_has_focus:
            if self._controller_sub_focus_index == self.SUBFOCUS_LIST:
                list_border = ED_CONFIG.ASSET_PALETTE_CONTROLLER_SUBFOCUS_BORDER # type: ignore
                if self.asset_list_widget.count() > 0: self.asset_list_widget.setFocus()
            elif self._controller_sub_focus_index == self.SUBFOCUS_CATEGORY_COMBO:
                combo_border = ED_CONFIG.ASSET_PALETTE_CONTROLLER_SUBFOCUS_BORDER # type: ignore
                self.category_filter_combo.setFocus()
            elif self._controller_sub_focus_index == self.SUBFOCUS_PAINT_COLOR_BTN:
                self.paint_color_button.setFocus()
        
        self.asset_list_widget.setStyleSheet(f"QListWidget::item:selected {{ border: 1px solid #007ACC; background-color: #c0d5eA; }} QListWidget {{ border: {list_border}; }}")
        self.category_filter_combo.setStyleSheet(f"QComboBox {{ border: {combo_border}; }}")
        self._update_paint_color_button_visuals() # This will apply its own focus border if needed

    
    def on_controller_focus_gained(self):
        self._controller_has_focus = True
        self._controller_sub_focus_index = self.SUBFOCUS_LIST 
        if self.asset_list_widget.count() > 0:
            if not (0 <= self._controller_list_current_index < self.asset_list_widget.count()):
                self._controller_list_current_index = 0
            self.asset_list_widget.setCurrentRow(self._controller_list_current_index)
            self.asset_list_widget.scrollToItem(self.asset_list_widget.item(self._controller_list_current_index), QAbstractItemView.ScrollHint.EnsureVisible)
        self._update_sub_focus_visuals()
        logger.debug("AssetPalette: Controller focus gained.")

    def on_controller_focus_lost(self):
        self._controller_has_focus = False
        self._update_sub_focus_visuals() 
        logger.debug("AssetPalette: Controller focus lost.")

    def handle_controller_action(self, action: str, value: Any):
        if not self._controller_has_focus: return

        if self._controller_sub_focus_index == self.SUBFOCUS_LIST:
            count = self.asset_list_widget.count()
            if count == 0: 
                if action == ACTION_UI_TAB_NEXT or action == ACTION_UI_RIGHT: self._cycle_sub_focus(1)
                elif action == ACTION_UI_TAB_PREV or action == ACTION_UI_LEFT: self._cycle_sub_focus(-1)
                return

            if action == ACTION_UI_UP:
                num_cols = self.asset_list_widget.width() // self.asset_list_widget.gridSize().width()
                num_cols = max(1, num_cols)
                self._controller_list_current_index = max(0, self._controller_list_current_index - num_cols)
            elif action == ACTION_UI_DOWN:
                num_cols = self.asset_list_widget.width() // self.asset_list_widget.gridSize().width()
                num_cols = max(1, num_cols)
                self._controller_list_current_index = min(count - 1, self._controller_list_current_index + num_cols)
            elif action == ACTION_UI_LEFT:
                self._controller_list_current_index = max(0, self._controller_list_current_index - 1)
            elif action == ACTION_UI_RIGHT:
                self._controller_list_current_index = min(count - 1, self._controller_list_current_index + 1)
            elif action == ACTION_UI_ACCEPT:
                item = self.asset_list_widget.item(self._controller_list_current_index)
                if item: self.on_item_clicked(item)
            elif action == ACTION_UI_TAB_NEXT: self._cycle_sub_focus(1)
            elif action == ACTION_UI_TAB_PREV: self._cycle_sub_focus(-1)
            
            if 0 <= self._controller_list_current_index < count:
                self.asset_list_widget.setCurrentRow(self._controller_list_current_index)
                self.asset_list_widget.scrollToItem(self.asset_list_widget.item(self._controller_list_current_index), QAbstractItemView.ScrollHint.EnsureVisible)

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


# --- PropertiesEditorDockWidget ---
class PropertiesEditorDockWidget(QWidget):
    properties_changed = Signal(dict)
    controller_focus_requested_elsewhere = Signal() 

    def __init__(self, editor_state: EditorState, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.editor_state = editor_state
        self.parent_window = parent 
        self.current_object_data_ref: Optional[Dict[str, Any]] = None
        self.current_asset_type_for_defaults: Optional[str] = None
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

        for i in range(self.form_layout.rowCount() -1, -1, -1): # type: ignore
            item_at_i = self.form_layout.itemAt(i) 
            if item_at_i is None: continue
            if item_at_i.widget() is self.no_selection_container or \
               (item_at_i.layout() and item_at_i.layout().indexOf(self.no_selection_container) != -1): # type: ignore
                continue
            row_items = self.form_layout.takeRow(i) # type: ignore
            if row_items.labelItem and row_items.labelItem.widget():
                row_items.labelItem.widget().deleteLater()
            if row_items.fieldItem and row_items.fieldItem.widget():
                row_items.fieldItem.widget().deleteLater()
            if row_items.fieldItem and row_items.fieldItem.layout():
                layout_to_clear = row_items.fieldItem.layout()
                while layout_to_clear.count():
                    child = layout_to_clear.takeAt(0)
                    if child.widget(): child.widget().deleteLater()
        self._update_focused_property_visuals() 

    @Slot(object)
    def display_map_object_properties(self, map_object_data_ref: Optional[Dict[str, Any]]):
        self._clear_dynamic_widgets_from_form()
        self.current_object_data_ref = None; self.current_asset_type_for_defaults = None
        if not map_object_data_ref or not isinstance(map_object_data_ref, dict):
            self.no_selection_label.setText("Select an object on the map to edit its properties.")
            self.no_selection_container.setVisible(True); self.scroll_widget.adjustSize(); return
        self.no_selection_container.setVisible(False); self.current_object_data_ref = map_object_data_ref
        
        asset_editor_key = str(map_object_data_ref.get("asset_editor_key", "N/A"))
        game_type_id_str = str(map_object_data_ref.get("game_type_id", "Unknown"))
        display_name_for_title = game_type_id_str 
        asset_data_for_title = self.editor_state.assets_palette.get(asset_editor_key)
        if asset_data_for_title and asset_data_for_title.get("name_in_palette"):
            display_name_for_title = asset_data_for_title["name_in_palette"]
        elif "_" in display_name_for_title: display_name_for_title = display_name_for_title.replace("_", " ").title()
        
        title_label = QLabel(f"Object Properties: {display_name_for_title}")
        font_title = title_label.font(); font_title.setBold(True); font_title.setPointSize(ED_CONFIG.FONT_SIZE_MEDIUM); title_label.setFont(font_title) # type: ignore
        self.form_layout.addRow(title_label)

        asset_key_label_text = QLabel("Asset Key:"); asset_key_label_text.setWordWrap(True)
        asset_key_value_label = QLabel(asset_editor_key); asset_key_value_label.setWordWrap(True)
        self.form_layout.addRow(asset_key_label_text, asset_key_value_label)
        
        coords_label_text = QLabel("Coords (X,Y):"); coords_label_text.setWordWrap(True) 
        coords_value_label = QLabel(f"({map_object_data_ref.get('world_x')}, {map_object_data_ref.get('world_y')})")
        self.form_layout.addRow(coords_label_text, coords_value_label)

        asset_palette_data = self.editor_state.assets_palette.get(asset_editor_key)
        if asset_palette_data and asset_palette_data.get("colorable"):
            color_label_text = QLabel("Color:"); color_label_text.setWordWrap(True)
            color_button = QPushButton()
            self.input_widgets["_color_button"] = color_button 
            self._update_color_button_visuals(color_button, map_object_data_ref) 
            color_button.clicked.connect(lambda _checked=False, obj_ref=map_object_data_ref: self._change_object_color(obj_ref)) 
            self.form_layout.addRow(color_label_text, color_button)
            self._controller_property_widgets_ordered.append(("_color_button", color_button, color_label_text))

        object_custom_props = map_object_data_ref.get("properties", {})
        if not isinstance(object_custom_props, dict): object_custom_props = {}; map_object_data_ref["properties"] = object_custom_props

        if game_type_id_str and game_type_id_str in ED_CONFIG.EDITABLE_ASSET_VARIABLES: # type: ignore
            prop_definitions = ED_CONFIG.EDITABLE_ASSET_VARIABLES[game_type_id_str] # type: ignore
            if prop_definitions:
                props_group = QGroupBox("Custom Properties"); props_group.setFlat(False) 
                props_layout_internal = QFormLayout(props_group) 
                props_layout_internal.setContentsMargins(6, 10, 6, 6); props_layout_internal.setSpacing(6)
                props_layout_internal.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
                props_layout_internal.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
                for var_name, definition in prop_definitions.items():
                    current_value = object_custom_props.get(var_name, definition["default"])
                    self._create_property_field(var_name, definition, current_value, props_layout_internal) 
                self.form_layout.addRow(props_group) 
        else:
            no_props_label = QLabel("No custom properties for this object type.")
            self.form_layout.addRow(no_props_label)
        
        self.scroll_widget.adjustSize() 
        if self._controller_has_focus: self._set_controller_focused_property(0) 

    @Slot(str)
    def display_asset_properties(self, asset_editor_key: Optional[str]):
        self._clear_dynamic_widgets_from_form()
        self.current_object_data_ref = None; self.current_asset_type_for_defaults = None
        if not asset_editor_key:
            if not self.current_object_data_ref: 
                self.no_selection_label.setText("Select an object or asset...")
                self.no_selection_container.setVisible(True); self.scroll_widget.adjustSize()
            return
        self.no_selection_container.setVisible(False); self.current_asset_type_for_defaults = asset_editor_key
        
        asset_data = self.editor_state.assets_palette.get(str(asset_editor_key));  _sp = None
        if not asset_data: self.scroll_widget.adjustSize(); return

        game_type_id = str(asset_data.get("game_type_id", "Unknown"))
        asset_name_display = asset_data.get('name_in_palette', game_type_id)
        if asset_name_display == game_type_id and "_" in asset_name_display:
            asset_name_display = asset_name_display.replace("_", " ").title()
            
        title_label = QLabel(f"Asset Type: {asset_name_display}")
        font_title = title_label.font(); font_title.setBold(True); font_title.setPointSize(ED_CONFIG.FONT_SIZE_MEDIUM); title_label.setFont(font_title) # type: ignore
        self.form_layout.addRow(title_label)

        if asset_data.get("colorable"):
            colorable_label_text = QLabel("Colorable:"); colorable_label_text.setWordWrap(True)
            colorable_info_label = QLabel("Yes (by tool or properties)")
            self.form_layout.addRow(colorable_label_text, colorable_info_label)
            default_color_val = asset_data.get("base_color_tuple")
            if not default_color_val: _sp = asset_data.get("surface_params")
            if _sp and isinstance(_sp, tuple) and len(_sp) == 3: default_color_val = _sp[2]
            if default_color_val:
                default_color_label_text = QLabel("Default Asset Color:"); default_color_label_text.setWordWrap(True)
                default_color_value_label = QLabel(str(default_color_val))
                self.form_layout.addRow(default_color_label_text, default_color_value_label)

        if game_type_id and game_type_id in ED_CONFIG.EDITABLE_ASSET_VARIABLES: # type: ignore
            props_group = QGroupBox("Default Editable Properties"); props_group.setFlat(False)
            props_layout_internal = QFormLayout(props_group) # type: ignore
            props_layout_internal.setContentsMargins(6,10,6,6); props_layout_internal.setSpacing(6)
            props_layout_internal.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            props_layout_internal.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
            prop_definitions = ED_CONFIG.EDITABLE_ASSET_VARIABLES[game_type_id] # type: ignore
            for var_name, definition in prop_definitions.items():
                prop_name_label = QLabel(definition.get('label', var_name.replace('_', ' ').title()) + ":")
                default_val_label = QLabel(str(definition["default"]))
                props_layout_internal.addRow(prop_name_label, default_val_label)
            self.form_layout.addRow(props_group)
        else:
            no_props_label = QLabel("No editable default properties for this asset type.")
            self.form_layout.addRow(no_props_label)
        
        self.scroll_widget.adjustSize() 

    def clear_display(self):
        self._clear_dynamic_widgets_from_form()
        self.current_object_data_ref = None; self.current_asset_type_for_defaults = None
        self.no_selection_label.setText("Select an object on the map or an asset type from the palette to see its properties.")
        self.no_selection_container.setVisible(True)
        self.scroll_widget.adjustSize()

    def _update_color_button_visuals(self, button: QPushButton, object_data_ref: Optional[Dict[str, Any]]):
        if not object_data_ref: return
        color_tuple = object_data_ref.get("override_color"); is_overridden = bool(color_tuple); _sp = None
        if not color_tuple: 
            asset_key = object_data_ref.get("asset_editor_key")
            asset_palette_data = self.editor_state.assets_palette.get(str(asset_key))
            if asset_palette_data:
                color_tuple = asset_palette_data.get("base_color_tuple")
                if not color_tuple: _sp = asset_palette_data.get("surface_params") 
                if _sp and isinstance(_sp, tuple) and len(_sp) == 3: color_tuple = _sp[2]
            if not color_tuple: color_tuple = (128,128,128)
        button_text = f"RGB: {color_tuple}"; button.setText(button_text + (" (Default)" if not is_overridden else ""))
        if color_tuple:
            q_color = QColor(*color_tuple); palette = button.palette()
            palette.setColor(QPalette.ColorRole.Button, q_color)
            luma = 0.299 * color_tuple[0] + 0.587 * color_tuple[1] + 0.114 * color_tuple[2]
            text_q_color = QColor(Qt.GlobalColor.black) if luma > 128 else QColor(Qt.GlobalColor.white)
            palette.setColor(QPalette.ColorRole.ButtonText, text_q_color)
            button.setPalette(palette); button.setAutoFillBackground(True)
            border_style = "1px solid black"
            if self._controller_has_focus and self._controller_focused_property_index >= 0 and \
               self._controller_focused_property_index < len(self._controller_property_widgets_ordered) and \
               self._controller_property_widgets_ordered[self._controller_focused_property_index][1] is button:
                border_style = ED_CONFIG.PROPERTIES_EDITOR_CONTROLLER_FOCUS_BORDER # type: ignore
            button.setStyleSheet(f"QPushButton {{ border: {border_style}; min-height: 20px; padding: 2px; }}"); button.update()


    def _create_property_field(self, var_name: str, definition: Dict[str, Any], current_value: Any, layout: QFormLayout):
        label_text_for_field = definition.get("label", var_name.replace("_", " ").title())
        property_name_label = QLabel(label_text_for_field + ":"); property_name_label.setWordWrap(True) 
        widget: Optional[QWidget] = None; prop_type = definition["type"]
        
        if prop_type == "int":
            spinner = QSpinBox(); widget = spinner
            spinner.setMinimum(definition.get("min", -2147483648)); spinner.setMaximum(definition.get("max", 2147483647))
            try: spinner.setValue(int(current_value))
            except: spinner.setValue(int(definition["default"]))
            spinner.valueChanged.connect(lambda val, vn=var_name: self._on_property_value_changed(vn, val))
        elif prop_type == "float":
            double_spinner = QDoubleSpinBox(); widget = double_spinner
            double_spinner.setMinimum(definition.get("min", -1.79e+308)); double_spinner.setMaximum(definition.get("max", 1.79e+308))
            try: double_spinner.setValue(float(current_value))
            except: double_spinner.setValue(float(definition["default"]))
            double_spinner.setDecimals(definition.get("decimals", 2))
            double_spinner.valueChanged.connect(lambda val, vn=var_name: self._on_property_value_changed(vn, val))
        elif prop_type == "str":
            if "options" in definition and isinstance(definition["options"], list):
                combo = QComboBox(); widget = combo; combo.addItems(definition["options"])
                try: combo.setCurrentIndex(definition["options"].index(str(current_value)))
                except ValueError: 
                    if str(definition["default"]) in definition["options"]: combo.setCurrentText(str(definition["default"]))
                    elif definition["options"]: combo.setCurrentIndex(0)
                combo.currentTextChanged.connect(lambda val, vn=var_name: self._on_property_value_changed(vn, val))
            else:
                line_edit = QLineEdit(str(current_value)); widget = line_edit 
                line_edit.editingFinished.connect(lambda le=line_edit, vn=var_name: self._on_line_edit_finished(vn, le.text()))
        elif prop_type == "bool":
            checkbox = QCheckBox(label_text_for_field); widget = checkbox 
            try: checkbox.setChecked(bool(current_value))
            except: checkbox.setChecked(bool(definition["default"]))
            checkbox.stateChanged.connect(lambda state_int, vn=var_name: self._on_property_value_changed(vn, state_int == Qt.CheckState.Checked.value))
        
        if widget:
            widget.setObjectName(f"prop_widget_{var_name}") 
            if not isinstance(widget, QCheckBox): 
                widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred) 
                layout.addRow(property_name_label, widget)
                self._controller_property_widgets_ordered.append((var_name, widget, property_name_label))
            else: 
                layout.addRow(widget) 
                self._controller_property_widgets_ordered.append((var_name, widget, None)) # Checkbox has its own label
            self.input_widgets[var_name] = widget
        else: layout.addRow(property_name_label, QLabel(f"Unsupported type: {prop_type}"))

    def _on_line_edit_finished(self, var_name: str, text_value: str): self._on_property_value_changed(var_name, text_value)
    def _on_property_value_changed(self, var_name: str, new_value: Any):
        if not self.current_object_data_ref: return
        if "properties" not in self.current_object_data_ref or not isinstance(self.current_object_data_ref.get("properties"), dict):
            self.current_object_data_ref["properties"] = {}
        game_type_id = str(self.current_object_data_ref.get("game_type_id"))
        definition = ED_CONFIG.EDITABLE_ASSET_VARIABLES.get(game_type_id, {}).get(var_name) # type: ignore
        if not definition: return
        prop_type = definition["type"]
        current_stored_value = self.current_object_data_ref["properties"].get(var_name, definition["default"])
        typed_new_value = new_value
        try:
            if prop_type == "int": typed_new_value = int(new_value)
            elif prop_type == "float": typed_new_value = float(new_value)
            elif prop_type == "bool": typed_new_value = bool(new_value)
            elif prop_type == "str": typed_new_value = str(new_value)
        except (ValueError, TypeError) as e:
            logger.warning(f"Casting error for '{var_name}': '{new_value}' to {prop_type}. Error: {e}")
            widget_to_revert = self.input_widgets.get(var_name)
            if widget_to_revert:
                if isinstance(widget_to_revert, QSpinBox): widget_to_revert.setValue(int(current_stored_value))
                elif isinstance(widget_to_revert, QDoubleSpinBox): widget_to_revert.setValue(float(current_stored_value))
                elif isinstance(widget_to_revert, QLineEdit): widget_to_revert.setText(str(current_stored_value))
                elif isinstance(widget_to_revert, QComboBox): widget_to_revert.setCurrentText(str(current_stored_value))
                elif isinstance(widget_to_revert, QCheckBox): widget_to_revert.setChecked(bool(current_stored_value))
            return
        if current_stored_value != typed_new_value:
            editor_history.push_undo_state(self.editor_state) # type: ignore
            self.current_object_data_ref["properties"][var_name] = typed_new_value
            self.properties_changed.emit(self.current_object_data_ref)
            logger.debug(f"Property '{var_name}' changed to '{typed_new_value}' for object.")

    def _change_object_color(self, map_object_data_ref: Optional[Dict[str, Any]]):
        if not map_object_data_ref: return
        current_color_tuple = map_object_data_ref.get("override_color"); _sp = None
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
                editor_history.push_undo_state(self.editor_state) # type: ignore
                map_object_data_ref["override_color"] = new_color_tuple
                self.properties_changed.emit(map_object_data_ref)
                logger.debug(f"Object color changed to {new_color_tuple}")
                color_button = self.input_widgets.get("_color_button")
                if isinstance(color_button, QPushButton): self._update_color_button_visuals(color_button, map_object_data_ref)
    
    def _update_focused_property_visuals(self):
        for var_name, widget, label_widget in self._controller_property_widgets_ordered:
            if widget is self.input_widgets.get("_color_button"):
                self._update_color_button_visuals(widget, self.current_object_data_ref) # type: ignore
            else:
                widget.setStyleSheet("") 
            if label_widget: label_widget.setStyleSheet("")

        if self._controller_has_focus and self._controller_focused_property_index >= 0 and \
           self._controller_focused_property_index < len(self._controller_property_widgets_ordered):
            
            var_name, widget, label_widget = self._controller_property_widgets_ordered[self._controller_focused_property_index]
            
            focus_style = f"border: {ED_CONFIG.PROPERTIES_EDITOR_CONTROLLER_FOCUS_BORDER};" # type: ignore
            if widget is not self.input_widgets.get("_color_button"): # Color button handles its own style
                widget.setStyleSheet(focus_style)
            
            if label_widget: 
                 label_widget.setStyleSheet("QLabel { color: " + ED_CONFIG.PROPERTIES_EDITOR_CONTROLLER_FOCUS_BORDER.split(' ')[-1] + "; font-weight: bold; }") # type: ignore
            
            widget.setFocus(Qt.FocusReason.OtherFocusReason) 
            self.scroll_area.ensureWidgetVisible(widget, 10, 10) # x, y margins

    def _set_controller_focused_property(self, index: int):
        if not self._controller_property_widgets_ordered:
            self._controller_focused_property_index = -1
            return
        
        new_index = max(0, min(index, len(self._controller_property_widgets_ordered) - 1))
        if self._controller_focused_property_index == new_index and self._controller_has_focus:
             return 
        
        self._controller_focused_property_index = new_index
        self._update_focused_property_visuals()
        logger.debug(f"PropertiesEditor: Controller focus on property index {new_index}")

    def on_controller_focus_gained(self):
        self._controller_has_focus = True
        if self._controller_property_widgets_ordered:
            self._set_controller_focused_property(0) 
        else:
            self._controller_focused_property_index = -1
        self._update_focused_property_visuals()
        logger.debug("PropertiesEditor: Controller focus gained.")

    def on_controller_focus_lost(self):
        self._controller_has_focus = False
        if self._controller_focused_property_index >= 0 and \
           self._controller_focused_property_index < len(self._controller_property_widgets_ordered):
            _, widget, label_widget = self._controller_property_widgets_ordered[self._controller_focused_property_index]
            if widget is not self.input_widgets.get("_color_button"):
                widget.setStyleSheet("")
            else: # Special handling for color button to reset its specific style correctly
                self._update_color_button_visuals(widget, self.current_object_data_ref) # type: ignore
            if label_widget: label_widget.setStyleSheet("")
        self._controller_focused_property_index = -1 
        logger.debug("PropertiesEditor: Controller focus lost.")

    def handle_controller_action(self, action: str, value: Any):
        if not self._controller_has_focus or not self._controller_property_widgets_ordered:
            if action == ACTION_UI_TAB_NEXT or action == ACTION_UI_TAB_PREV: # Allow tabbing out even if no props
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
            if isinstance(widget, QPushButton): widget.click() 
            elif isinstance(widget, QCheckBox): widget.toggle()
            elif isinstance(widget, QComboBox): widget.showPopup() 
        elif action == ACTION_UI_LEFT or action == ACTION_UI_RIGHT:
            step = 1 if action == ACTION_UI_RIGHT else -1
            if isinstance(widget, QSpinBox):
                new_val = widget.value() + step * widget.singleStep()
                if new_val >= widget.minimum() and new_val <= widget.maximum(): widget.setValue(new_val)
            elif isinstance(widget, QDoubleSpinBox):
                new_val = widget.value() + step * widget.singleStep()
                if new_val >= widget.minimum() and new_val <= widget.maximum(): widget.setValue(new_val)
            elif isinstance(widget, QComboBox):
                new_combo_idx = widget.currentIndex() + step
                if 0 <= new_combo_idx < widget.count(): widget.setCurrentIndex(new_combo_idx)
        elif action == ACTION_UI_TAB_NEXT or action == ACTION_UI_TAB_PREV:
            self.controller_focus_requested_elsewhere.emit()
            
#################### END OF FILE: editor\editor_ui_panels.py ####################