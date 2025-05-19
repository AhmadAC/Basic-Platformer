# editor_ui_panels.py
# -*- coding: utf-8 -*-
"""
Custom Qt Widgets for UI Panels (Asset Palette, Properties Editor)
in the PySide6 Level Editor.
Version 2.0.7 (Paint Color button text static, background indicates color)
"""
import logging
from typing import Optional, Dict, Any, List, Tuple

from PySide6.QtWidgets import (
    QWidget, QListWidget, QListWidgetItem, QVBoxLayout, QHBoxLayout, 
    QLabel, QLineEdit, QCheckBox, QComboBox, QPushButton, QScrollArea,
    QFormLayout, QSpinBox, QDoubleSpinBox, QColorDialog,
    QGroupBox, QSizePolicy 
)
from PySide6.QtGui import QIcon, QPalette, QColor, QPixmap
from PySide6.QtCore import Qt, Signal, Slot, QSize

import editor_config as ED_CONFIG
from editor_state import EditorState
import editor_history

logger = logging.getLogger(__name__)

# --- AssetPaletteWidget ---
class AssetPaletteWidget(QWidget):
    asset_selected = Signal(str)
    tool_selected = Signal(str)
    paint_color_changed_for_status = Signal(str)


    def __init__(self, editor_state: EditorState, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.editor_state = editor_state
        self.parent_window = parent
        self.categories_populated_in_combo = False

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(2,2,2,2)
        self.main_layout.setSpacing(3) 

        filter_area_layout = QHBoxLayout()
        
        self.category_filter_combo = QComboBox(self)
        self.category_filter_combo.addItem("All") 
        self.category_filter_combo.currentIndexChanged.connect(self._on_category_filter_changed)
        filter_area_layout.addWidget(self.category_filter_combo, 1) 

        self.paint_color_button = QPushButton("Paint Color") # Static text
        self.paint_color_button.setToolTip("Set the color for the next placed colorable asset. Current color shown by button background.")
        self.paint_color_button.clicked.connect(self._on_select_paint_color)
        self._update_paint_color_button_visuals() 
        filter_area_layout.addWidget(self.paint_color_button, 0) 

        self.main_layout.addLayout(filter_area_layout)

        self.asset_list_widget = QListWidget(self)
        self.asset_list_widget.setIconSize(QSize(ED_CONFIG.ASSET_PALETTE_ICON_SIZE_W, ED_CONFIG.ASSET_PALETTE_ICON_SIZE_H))
        self.asset_list_widget.setViewMode(QListWidget.ViewMode.IconMode)
        self.asset_list_widget.setFlow(QListWidget.Flow.LeftToRight)
        self.asset_list_widget.setWrapping(True)
        self.asset_list_widget.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.asset_list_widget.setSpacing(5) 
        self.asset_list_widget.itemClicked.connect(self.on_item_clicked)
        self.asset_list_widget.setStyleSheet("""
            QListWidget::item { padding: 4px; border: 1px solid transparent; }
            QListWidget::item:hover { background-color: #e0e0e0; }
            QListWidget::item:selected { border: 1px solid #333; background-color: #c0d5eA; }
        """)
        self.main_layout.addWidget(self.asset_list_widget)

    def _update_paint_color_button_visuals(self):
        color_tuple = self.editor_state.current_selected_asset_paint_color
        # Keep button text static
        self.paint_color_button.setText("Paint Color") 

        if color_tuple:
            q_color = QColor(*color_tuple)
            palette = self.paint_color_button.palette()
            palette.setColor(QPalette.ColorRole.Button, q_color)
            
            # Determine text color for contrast
            luma = 0.299 * color_tuple[0] + 0.587 * color_tuple[1] + 0.114 * color_tuple[2]
            text_q_color = QColor(Qt.GlobalColor.black) if luma > 128 else QColor(Qt.GlobalColor.white)
            palette.setColor(QPalette.ColorRole.ButtonText, text_q_color)
            
            self.paint_color_button.setPalette(palette)
            self.paint_color_button.setAutoFillBackground(True)
            # Ensure border is visible if color is very light/dark like the default button bg
            self.paint_color_button.setStyleSheet("QPushButton { border: 1px solid #555; min-height: 20px; padding: 2px; }")
        else:
            # Revert to default appearance
            self.paint_color_button.setAutoFillBackground(False) 
            self.paint_color_button.setPalette(QWidget().palette()) # Get a default palette from a temporary default QWidget
            self.paint_color_button.setStyleSheet("") # Revert to default stylesheet
        
        self.paint_color_button.update()


    @Slot()
    def _on_select_paint_color(self):
        current_q_color = QColor(*self.editor_state.current_selected_asset_paint_color) if self.editor_state.current_selected_asset_paint_color else QColor(Qt.GlobalColor.white)
        new_q_color = QColorDialog.getColor(current_q_color, self, "Select Asset Paint Color")
        if new_q_color.isValid():
            self.editor_state.current_selected_asset_paint_color = new_q_color.getRgb()[:3]
            status_msg = f"Asset paint color set to: {self.editor_state.current_selected_asset_paint_color}"
        else:
            status_msg = "Asset paint color selection cancelled." # Or keep previous color
        
        self._update_paint_color_button_visuals()
        self.paint_color_changed_for_status.emit(status_msg)

    def _populate_category_combo_if_needed(self):
        if self.categories_populated_in_combo or not self.editor_state.assets_palette:
            return

        all_asset_categories = set()
        for data in self.editor_state.assets_palette.values():
            all_asset_categories.add(data.get("category", "unknown"))

        combo_items = ["All"]
        for cat_name_ordered in ED_CONFIG.EDITOR_PALETTE_ASSETS_CATEGORIES_ORDER:
            if cat_name_ordered in all_asset_categories:
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

    def populate_assets(self, filter_override: Optional[str] = None):
        self._populate_category_combo_if_needed()
        current_filter_text = filter_override if filter_override is not None else self.category_filter_combo.currentText()
        self.asset_list_widget.clear()
        if not self.editor_state.assets_palette: return
        
        logger.debug(f"Populating asset palette UI with filter: '{current_filter_text}'...")
        item_cell_width = 85 
        item_cell_height = ED_CONFIG.ASSET_PALETTE_ICON_SIZE_H + 20 
        self.asset_list_widget.setGridSize(QSize(item_cell_width, item_cell_height))
        self.asset_list_widget.setUniformItemSizes(True)

        assets_to_display: List[Tuple[str, Dict[str, Any]]] = []
        for key, data in self.editor_state.assets_palette.items():
            category = data.get("category", "unknown")
            if current_filter_text.lower() == "all" or \
               category.lower() == current_filter_text.lower() or \
               category.title().lower() == current_filter_text.lower():
                assets_to_display.append((key, data))
        assets_to_display.sort(key=lambda x: x[0])

        for key, data in assets_to_display:
            pixmap: Optional[QPixmap] = data.get("q_pixmap")
            if pixmap and not pixmap.isNull():
                item_text_for_tooltip = data.get("name_in_palette", key.replace("_", " ").title())
                list_item = QListWidgetItem(QIcon(pixmap), "") 
                list_item.setToolTip(item_text_for_tooltip) 
                list_item.setData(Qt.ItemDataRole.UserRole, key)
                self.asset_list_widget.addItem(list_item)
            else:
                logger.warning(f"Asset '{key}' missing valid QPixmap, not added to palette.")
        logger.debug(f"Asset palette UI populated with {self.asset_list_widget.count()} items for filter '{current_filter_text}'.")

    @Slot(int)
    def _on_category_filter_changed(self, index: int):
        self.populate_assets()

    @Slot(QListWidgetItem)
    def on_item_clicked(self, item: QListWidgetItem):
        if not (item.flags() & Qt.ItemFlag.ItemIsEnabled): return
        asset_key = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(asset_key, str):
            asset_data = self.editor_state.assets_palette.get(asset_key)
            if asset_data:
                current_name = asset_data.get("name_in_palette", asset_key)
                if asset_data.get("category") == "tool" or str(asset_data.get("game_type_id", "")).startswith("tool_"):
                    self.tool_selected.emit(asset_key)
                    if hasattr(self.parent_window, 'show_status_message'):
                        self.parent_window.show_status_message(f"Tool selected: {current_name}")
                else:
                    self.asset_selected.emit(asset_key)
                    if hasattr(self.parent_window, 'show_status_message'):
                         self.parent_window.show_status_message(f"Asset selected: {current_name}")

    def clear_selection(self):
        self.asset_list_widget.clearSelection()

# --- PropertiesEditorDockWidget ---
class PropertiesEditorDockWidget(QWidget):
    properties_changed = Signal(dict)

    def __init__(self, editor_state: EditorState, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.editor_state = editor_state
        self.parent_window = parent
        self.current_object_data_ref: Optional[Dict[str, Any]] = None
        self.current_asset_type_for_defaults: Optional[str] = None
        self.input_widgets: Dict[str, QWidget] = {}

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

    def _clear_dynamic_widgets_from_form(self):
        self.input_widgets.clear()
        for i in range(self.form_layout.rowCount() - 1, -1, -1):
            field_item = self.form_layout.itemAt(i, QFormLayout.ItemRole.FieldRole)
            label_item = self.form_layout.itemAt(i, QFormLayout.ItemRole.LabelRole)
            field_widget = field_item.widget() if field_item else None
            label_widget = label_item.widget() if label_item else None
            if field_widget is self.no_selection_container or label_widget is self.no_selection_container: continue
            if field_widget is self.no_selection_label or label_widget is self.no_selection_label: continue
            row_result = self.form_layout.takeRow(i)
            if row_result:
                if row_result.labelItem and row_result.labelItem.widget(): row_result.labelItem.widget().deleteLater()
                if row_result.fieldItem and row_result.fieldItem.widget(): row_result.fieldItem.widget().deleteLater()

    @Slot(object)
    def display_map_object_properties(self, map_object_data_ref: Optional[Dict[str, Any]]):
        self._clear_dynamic_widgets_from_form()
        self.current_object_data_ref = None; self.current_asset_type_for_defaults = None
        if not map_object_data_ref or not isinstance(map_object_data_ref, dict):
            self.no_selection_label.setText("Select an object on the map to edit its properties.")
            self.no_selection_container.setVisible(True); return
        self.no_selection_container.setVisible(False); self.current_object_data_ref = map_object_data_ref
        
        asset_editor_key = str(map_object_data_ref.get("asset_editor_key", "N/A"))
        game_type_id_str = str(map_object_data_ref.get("game_type_id", "Unknown"))
        display_name_for_title = game_type_id_str 
        asset_data_for_title = self.editor_state.assets_palette.get(asset_editor_key)
        if asset_data_for_title and asset_data_for_title.get("name_in_palette"):
            display_name_for_title = asset_data_for_title["name_in_palette"]
        elif "_" in display_name_for_title: display_name_for_title = display_name_for_title.replace("_", " ").title()
        
        title_label = QLabel(f"Object Properties: {display_name_for_title}")
        title_label.setWordWrap(True)
        title_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        font_title = title_label.font(); font_title.setBold(True); font_title.setPointSize(ED_CONFIG.FONT_SIZE_MEDIUM); title_label.setFont(font_title)
        self.form_layout.addRow(title_label)

        asset_key_label_text = QLabel("Asset Key:"); asset_key_label_text.setWordWrap(True)
        asset_key_value_label = QLabel(asset_editor_key); asset_key_value_label.setWordWrap(True)
        asset_key_value_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.form_layout.addRow(asset_key_label_text, asset_key_value_label)
        
        coords_label_text = QLabel("Coords (X,Y):"); coords_label_text.setWordWrap(True) 
        coords_value_label = QLabel(f"({map_object_data_ref.get('world_x')}, {map_object_data_ref.get('world_y')})")
        coords_value_label.setWordWrap(True); coords_value_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.form_layout.addRow(coords_label_text, coords_value_label)

        asset_palette_data = self.editor_state.assets_palette.get(asset_editor_key)
        if asset_palette_data and asset_palette_data.get("colorable"):
            color_label_text = QLabel("Color:"); color_label_text.setWordWrap(True)
            color_button = QPushButton()
            self.input_widgets["_color_button"] = color_button
            self._update_color_button_visuals(color_button, map_object_data_ref) 
            color_button.clicked.connect(lambda _checked=False, obj_ref=map_object_data_ref: self._change_object_color(obj_ref)) 
            self.form_layout.addRow(color_label_text, color_button)

        object_custom_props = map_object_data_ref.get("properties", {})
        if not isinstance(object_custom_props, dict): object_custom_props = {}; map_object_data_ref["properties"] = object_custom_props

        if game_type_id_str and game_type_id_str in ED_CONFIG.EDITABLE_ASSET_VARIABLES:
            prop_definitions = ED_CONFIG.EDITABLE_ASSET_VARIABLES[game_type_id_str]
            if prop_definitions:
                props_group = QGroupBox("Custom Properties"); props_group.setFlat(False) 
                props_layout = QFormLayout(props_group)
                props_layout.setContentsMargins(6, 10, 6, 6); props_layout.setSpacing(6)
                props_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
                props_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
                for var_name, definition in prop_definitions.items():
                    current_value = object_custom_props.get(var_name, definition["default"])
                    self._create_property_field(var_name, definition, current_value, props_layout)
                self.form_layout.addRow(props_group)
        else:
            no_props_label = QLabel("No custom properties for this object type.")
            no_props_label.setWordWrap(True); no_props_label.setStyleSheet("QLabel { font-style: italic; }")
            no_props_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            self.form_layout.addRow(no_props_label)

    @Slot(str)
    def display_asset_properties(self, asset_editor_key: Optional[str]):
        self._clear_dynamic_widgets_from_form()
        self.current_object_data_ref = None; self.current_asset_type_for_defaults = None
        if not asset_editor_key:
            if not self.current_object_data_ref: 
                self.no_selection_label.setText("Select an object or asset...")
                self.no_selection_container.setVisible(True)
            return
        self.no_selection_container.setVisible(False); self.current_asset_type_for_defaults = asset_editor_key
        
        asset_data = self.editor_state.assets_palette.get(str(asset_editor_key));  _sp = None
        if not asset_data: return

        game_type_id = str(asset_data.get("game_type_id", "Unknown"))
        asset_name_display = asset_data.get('name_in_palette', game_type_id)
        if asset_name_display == game_type_id and "_" in asset_name_display:
            asset_name_display = asset_name_display.replace("_", " ").title()
            
        title_label = QLabel(f"Asset Type: {asset_name_display}")
        title_label.setWordWrap(True)
        title_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        font_title = title_label.font(); font_title.setBold(True); font_title.setPointSize(ED_CONFIG.FONT_SIZE_MEDIUM); title_label.setFont(font_title)
        self.form_layout.addRow(title_label)

        if asset_data.get("colorable"):
            colorable_label_text = QLabel("Colorable:"); colorable_label_text.setWordWrap(True)
            colorable_info_label = QLabel("Yes (by tool or properties)")
            colorable_info_label.setWordWrap(True)
            colorable_info_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            self.form_layout.addRow(colorable_label_text, colorable_info_label)
             
            default_color_val = asset_data.get("base_color_tuple")
            if not default_color_val: _sp = asset_data.get("surface_params")
            if _sp and isinstance(_sp, tuple) and len(_sp) == 3: default_color_val = _sp[2]
            if default_color_val:
                default_color_label_text = QLabel("Default Asset Color:"); default_color_label_text.setWordWrap(True)
                default_color_value_label = QLabel(str(default_color_val))
                default_color_value_label.setWordWrap(True)
                default_color_value_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
                self.form_layout.addRow(default_color_label_text, default_color_value_label)

        if game_type_id and game_type_id in ED_CONFIG.EDITABLE_ASSET_VARIABLES:
            props_group = QGroupBox("Default Editable Properties"); props_group.setFlat(False)
            props_layout = QFormLayout(props_group)
            props_layout.setContentsMargins(6,10,6,6); props_layout.setSpacing(6)
            props_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            props_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
            prop_definitions = ED_CONFIG.EDITABLE_ASSET_VARIABLES[game_type_id]
            for var_name, definition in prop_definitions.items():
                prop_name_label = QLabel(definition.get('label', var_name.replace('_', ' ').title()) + ":")
                prop_name_label.setWordWrap(True)
                default_val_label = QLabel(str(definition["default"]))
                default_val_label.setWordWrap(True)
                default_val_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
                props_layout.addRow(prop_name_label, default_val_label)
            self.form_layout.addRow(props_group)
        else:
            no_props_label = QLabel("No editable default properties for this asset type.")
            no_props_label.setWordWrap(True); no_props_label.setStyleSheet("QLabel { font-style: italic; }")
            no_props_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            self.form_layout.addRow(no_props_label)

    def clear_display(self):
        self._clear_dynamic_widgets_from_form()
        self.current_object_data_ref = None; self.current_asset_type_for_defaults = None
        self.no_selection_label.setText("Select an object on the map or an asset type from the palette to see its properties.")
        self.no_selection_container.setVisible(True)

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
            button.setStyleSheet("QPushButton { border: 1px solid black; min-height: 20px; padding: 2px; }"); button.update()

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
            if not isinstance(widget, QCheckBox): 
                widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred) 
                layout.addRow(property_name_label, widget)
            else: layout.addRow(widget)
            self.input_widgets[var_name] = widget
        else: layout.addRow(property_name_label, QLabel(f"Unsupported type: {prop_type}"))

    def _on_line_edit_finished(self, var_name: str, text_value: str): self._on_property_value_changed(var_name, text_value)
    def _on_property_value_changed(self, var_name: str, new_value: Any):
        if not self.current_object_data_ref: return
        if "properties" not in self.current_object_data_ref or not isinstance(self.current_object_data_ref.get("properties"), dict):
            self.current_object_data_ref["properties"] = {}
        game_type_id = str(self.current_object_data_ref.get("game_type_id"))
        definition = ED_CONFIG.EDITABLE_ASSET_VARIABLES.get(game_type_id, {}).get(var_name)
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
            editor_history.push_undo_state(self.editor_state)
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
                editor_history.push_undo_state(self.editor_state)
                map_object_data_ref["override_color"] = new_color_tuple
                self.properties_changed.emit(map_object_data_ref)
                logger.debug(f"Object color changed to {new_color_tuple}")
                color_button = self.input_widgets.get("_color_button")
                if isinstance(color_button, QPushButton): self._update_color_button_visuals(color_button, map_object_data_ref)