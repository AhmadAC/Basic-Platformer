# editor_ui_panels.py
# -*- coding: utf-8 -*-
"""
Custom Qt Widgets for UI Panels (Asset Palette, Properties Editor)
in the PySide6 Level Editor.
"""
import logging
from typing import Optional, Dict, Any, List, Tuple # Tuple is used for color hints

from PySide6.QtWidgets import (
    QWidget, QListWidget, QListWidgetItem, QVBoxLayout,
    QLabel, QLineEdit, QCheckBox, QComboBox, QPushButton, QScrollArea,
    QFormLayout, QSpinBox, QDoubleSpinBox, QColorDialog,
    QGroupBox  # CORRECTED: Added QGroupBox
)
from PySide6.QtGui import QIcon, QPalette, QColor, QPixmap
from PySide6.QtCore import Qt, Signal, Slot, QSize

import editor_config as ED_CONFIG
from editor_state import EditorState
import editor_history # For undo stack on property changes

logger = logging.getLogger(__name__)

# --- AssetPaletteWidget ---
class AssetPaletteWidget(QWidget):
    asset_selected = Signal(str)
    tool_selected = Signal(str)

    def __init__(self, editor_state: EditorState, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.editor_state = editor_state
        self.parent_window = parent # Should be EditorMainWindow

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(2,2,2,2)

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

        self.layout.addWidget(self.asset_list_widget)
        # populate_assets is called from EditorMainWindow after assets are loaded into editor_state

    def populate_assets(self):
        self.asset_list_widget.clear()
        if not self.editor_state.assets_palette:
            logger.warning("Asset palette in state is empty. Cannot populate UI.")
            return
        logger.debug("Populating asset palette UI...")

        categorized_assets: Dict[str, List[Tuple[str, Dict[str, Any]]]] = {} # Explicit type hint for data
        for key, data in self.editor_state.assets_palette.items():
            category = data.get("category", "unknown")
            categorized_assets.setdefault(category, []).append((key, data))

        for category_name in ED_CONFIG.EDITOR_PALETTE_ASSETS_CATEGORIES_ORDER:
            if category_name in categorized_assets:
                header_item = QListWidgetItem(f"--- {category_name.title()} ---")
                font = header_item.font()
                font.setBold(ED_CONFIG.FONT_CATEGORY_TITLE_BOLD)
                font.setPointSize(ED_CONFIG.FONT_CATEGORY_TITLE_SIZE)
                header_item.setFont(font)
                header_item.setFlags(Qt.ItemFlag.NoItemFlags)
                self.asset_list_widget.addItem(header_item)

                for key, data in sorted(categorized_assets[category_name], key=lambda x: x[0]):
                    pixmap: Optional[QPixmap] = data.get("q_pixmap") # data value could be None
                    if pixmap and not pixmap.isNull():
                        item_text = data.get("name_in_palette", key.replace("_", " ").title())
                        
                        list_item = QListWidgetItem(QIcon(pixmap), item_text)
                        list_item.setData(Qt.ItemDataRole.UserRole, key)
                        fm = self.asset_list_widget.fontMetrics()
                        text_width = fm.horizontalAdvance(item_text)
                        item_width = max(ED_CONFIG.ASSET_PALETTE_ICON_SIZE_W + 10, text_width + 10)
                        item_height = ED_CONFIG.ASSET_PALETTE_ICON_SIZE_H + fm.height() + 15
                        list_item.setSizeHint(QSize(item_width, item_height))
                        self.asset_list_widget.addItem(list_item)
                    else:
                        logger.warning(f"Asset '{key}' missing valid QPixmap, not added to palette.")
        logger.debug(f"Asset palette UI populated with {self.asset_list_widget.count()} displayable items.")

    @Slot(QListWidgetItem)
    def on_item_clicked(self, item: QListWidgetItem):
        if not (item.flags() & Qt.ItemFlag.ItemIsEnabled): return

        asset_key = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(asset_key, str): # Ensure asset_key is a string
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
        self.current_object_data_ref: Optional[Dict[str, Any]] = None # Explicit type hint
        self.current_asset_type_for_defaults: Optional[str] = None
        self.input_widgets: Dict[str, QWidget] = {}

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(5,5,5,5)

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_widget = QWidget()
        self.form_layout = QFormLayout(self.scroll_widget)
        self.form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        self.form_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        self.scroll_area.setWidget(self.scroll_widget)

        self.main_layout.addWidget(self.scroll_area)
        
        # This label will be created and managed within clear_layout
        self.no_selection_label: Optional[QLabel] = None
        self.clear_layout()


    def clear_layout(self):
        self.current_object_data_ref = None
        self.current_asset_type_for_defaults = None
        self.input_widgets.clear()
        while self.form_layout.count():
            item = self.form_layout.takeAt(0)
            widget_to_delete = None
            layout_to_delete = None
            if item.widget(): widget_to_delete = item.widget()
            elif item.layout(): layout_to_delete = item.layout()
            
            if widget_to_delete: widget_to_delete.deleteLater()
            if layout_to_delete: # Clear layout and its widgets
                while layout_to_delete.count():
                    child = layout_to_delete.takeAt(0)
                    if child.widget(): child.widget().deleteLater()
                layout_to_delete.deleteLater()
        
        if not self.no_selection_label or not self.no_selection_label.parent(): # Create if doesn't exist or was deleted
            self.no_selection_label = QLabel("Select an object or asset to see properties.")
            self.no_selection_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.no_selection_label.setWordWrap(True)
             # Add it to a container for centering (if form_layout is multi-column this helps)
            no_sel_container = QWidget()
            no_sel_layout = QVBoxLayout(no_sel_container)
            no_sel_layout.addWidget(self.no_selection_label)
            no_sel_layout.addStretch()
            self.form_layout.addRow(no_sel_container) # Add the container
        
        self.no_selection_label.setText("Select an object or asset...")
        self.no_selection_label.setVisible(True)
        if self.no_selection_label.parentWidget(): # Ensure parent container is visible
            self.no_selection_label.parentWidget().setVisible(True)


    @Slot(object)
    def display_map_object_properties(self, map_object_data_ref: Optional[Dict[str, Any]]): # Explicit type hint
        self.clear_layout()
        if not map_object_data_ref or not isinstance(map_object_data_ref, dict):
            self.no_selection_label.setText("Select an object on the map to edit its properties.")
            self.no_selection_label.setVisible(True)
            if self.no_selection_label.parentWidget(): self.no_selection_label.parentWidget().setVisible(True)
            return

        self.current_object_data_ref = map_object_data_ref
        if self.no_selection_label and self.no_selection_label.parentWidget(): # Hide the placeholder container
            self.no_selection_label.parentWidget().setVisible(False)


        game_type_id = str(map_object_data_ref.get("game_type_id", "Unknown"))
        asset_editor_key = str(map_object_data_ref.get("asset_editor_key", "N/A"))
        
        title_label = QLabel(f"Object: {game_type_id}")
        font = title_label.font(); font.setBold(True); font.setPointSize(ED_CONFIG.FONT_SIZE_MEDIUM); title_label.setFont(font)
        self.form_layout.addRow(title_label)

        self.form_layout.addRow("Asset Key:", QLabel(asset_editor_key))
        self.form_layout.addRow("Coords (X,Y):", QLabel(f"({map_object_data_ref.get('world_x')}, {map_object_data_ref.get('world_y')})"))

        asset_palette_data = self.editor_state.assets_palette.get(asset_editor_key)
        if asset_palette_data and asset_palette_data.get("colorable"):
            color_button = QPushButton()
            self.input_widgets["_color_button"] = color_button
            self._update_color_button_visuals(color_button, map_object_data_ref) # Call helper
            color_button.clicked.connect(lambda _checked=False, obj_ref=map_object_data_ref: self._change_object_color(obj_ref)) # Use lambda for proper capture
            self.form_layout.addRow("Color:", color_button)

        object_custom_props = map_object_data_ref.get("properties")
        if not isinstance(object_custom_props, dict):
             object_custom_props = {}
             map_object_data_ref["properties"] = object_custom_props

        if game_type_id and game_type_id in ED_CONFIG.EDITABLE_ASSET_VARIABLES:
            prop_definitions = ED_CONFIG.EDITABLE_ASSET_VARIABLES[game_type_id]
            if prop_definitions:
                props_group = QGroupBox("Custom Properties")
                props_layout = QFormLayout(props_group)
                props_layout.setContentsMargins(2,5,2,5) # Smaller margins for groupbox formlayout
                for var_name, definition in prop_definitions.items():
                    current_value = object_custom_props.get(var_name, definition["default"])
                    self._create_property_field(var_name, definition, current_value, props_layout)
                self.form_layout.addRow(props_group)
        else:
            no_props_label = QLabel("No custom properties for this object type.")
            no_props_label.setStyleSheet("QLabel { font-style: italic; }")
            self.form_layout.addRow(no_props_label)


    @Slot(str)
    def display_asset_properties(self, asset_editor_key: Optional[str]):
        if not asset_editor_key:
            if not self.current_object_data_ref:
                self.clear_layout()
                self.no_selection_label.setText("Select an object or asset...")
                self.no_selection_label.setVisible(True)
                if self.no_selection_label.parentWidget(): self.no_selection_label.parentWidget().setVisible(True)
            return

        self.clear_layout()
        self.current_asset_type_for_defaults = asset_editor_key
        if self.no_selection_label and self.no_selection_label.parentWidget():
            self.no_selection_label.parentWidget().setVisible(False)


        asset_data = self.editor_state.assets_palette.get(str(asset_editor_key)) # Ensure key is str
        if not asset_data: return

        game_type_id = str(asset_data.get("game_type_id", "Unknown"))
        title_label = QLabel(f"Asset Type: {asset_data.get('name_in_palette', game_type_id)}")
        font = title_label.font(); font.setBold(True); font.setPointSize(ED_CONFIG.FONT_SIZE_MEDIUM); title_label.setFont(font)
        self.form_layout.addRow(title_label)

        if asset_data.get("colorable"):
             self.form_layout.addRow("Colorable:", QLabel("Yes (by tool or properties)"))
             default_color_val = asset_data.get("base_color_tuple")
             if not default_color_val and asset_data.get("surface_params_dims_color"):
                 default_color_val = asset_data.get("surface_params_dims_color")[2] # Get color from (w,h,color)
             if default_color_val:
                self.form_layout.addRow("Default Asset Color:", QLabel(str(default_color_val)))

        if game_type_id and game_type_id in ED_CONFIG.EDITABLE_ASSET_VARIABLES:
            props_group = QGroupBox("Default Editable Properties")
            props_layout = QFormLayout(props_group)
            props_layout.setContentsMargins(2,5,2,5)
            prop_definitions = ED_CONFIG.EDITABLE_ASSET_VARIABLES[game_type_id]
            for var_name, definition in prop_definitions.items():
                default_val_label = QLabel(str(definition["default"]))
                props_layout.addRow(f"{definition.get('label', var_name.replace('_', ' ').title())}:", default_val_label)
            self.form_layout.addRow(props_group)
        else:
            no_props_label = QLabel("No editable default properties for this asset type.")
            no_props_label.setStyleSheet("QLabel { font-style: italic; }")
            self.form_layout.addRow(no_props_label)

    def _update_color_button_visuals(self, button: QPushButton, object_data_ref: Optional[Dict[str, Any]]):
        if not object_data_ref: return

        color_tuple = object_data_ref.get("override_color")
        is_overridden = bool(color_tuple)

        if not color_tuple: # Determine default if no override
            asset_key = object_data_ref.get("asset_editor_key")
            asset_palette_data = self.editor_state.assets_palette.get(str(asset_key))
            if asset_palette_data:
                if asset_palette_data.get("base_color_tuple"):
                    color_tuple = asset_palette_data.get("base_color_tuple")
                elif asset_palette_data.get("surface_params_dims_color"):
                    color_tuple = asset_palette_data.get("surface_params_dims_color")[2] # Index 2 is color
            if not color_tuple: color_tuple = (128,128,128) # Fallback

        button_text = f"RGB: {color_tuple}"
        if not is_overridden: button_text += " (Default)"
        button.setText(button_text)
            
        if color_tuple:
            q_color = QColor(*color_tuple)
            palette = button.palette()
            palette.setColor(QPalette.ColorRole.Button, q_color)
            luma = 0.299 * color_tuple[0] + 0.587 * color_tuple[1] + 0.114 * color_tuple[2]
            text_q_color = QColor(Qt.GlobalColor.black) if luma > 128 else QColor(Qt.GlobalColor.white)
            palette.setColor(QPalette.ColorRole.ButtonText, text_q_color)
            button.setPalette(palette)
            button.setAutoFillBackground(True)
            button.setStyleSheet("QPushButton { border: 1px solid black; min-height: 20px; padding: 2px; }")
            button.update()


    def _create_property_field(self, var_name: str, definition: Dict[str, Any], current_value: Any, layout: QFormLayout):
        label_text = definition.get("label", var_name.replace("_", " ").title())
        widget: Optional[QWidget] = None

        prop_type = definition["type"]

        if prop_type == "int":
            spinner = QSpinBox(); widget = spinner
            spinner.setMinimum(definition.get("min", -2147483648))
            spinner.setMaximum(definition.get("max", 2147483647))
            try: spinner.setValue(int(current_value))
            except: spinner.setValue(int(definition["default"]))
            spinner.valueChanged.connect(lambda val, vn=var_name: self._on_property_value_changed(vn, val))
        elif prop_type == "float":
            double_spinner = QDoubleSpinBox(); widget = double_spinner
            double_spinner.setMinimum(definition.get("min", -1.79e+308))
            double_spinner.setMaximum(definition.get("max", 1.79e+308))
            try: double_spinner.setValue(float(current_value))
            except: double_spinner.setValue(float(definition["default"]))
            double_spinner.setDecimals(definition.get("decimals", 2))
            double_spinner.valueChanged.connect(lambda val, vn=var_name: self._on_property_value_changed(vn, val))
        elif prop_type == "str":
            if "options" in definition and isinstance(definition["options"], list):
                combo = QComboBox(); widget = combo
                combo.addItems(definition["options"])
                try:
                    idx = definition["options"].index(str(current_value))
                    combo.setCurrentIndex(idx)
                except ValueError: # If current_value not in options, try default
                    if str(definition["default"]) in definition["options"]:
                         combo.setCurrentText(str(definition["default"]))
                    elif definition["options"]: # Select first option if default also not there
                        combo.setCurrentIndex(0)

                combo.currentTextChanged.connect(lambda val, vn=var_name: self._on_property_value_changed(vn, val))
            else:
                line_edit = QLineEdit(str(current_value)); widget = line_edit
                # Connect to editingFinished for QLineEdit to avoid too many undo states during typing
                line_edit.editingFinished.connect(lambda le=line_edit, vn=var_name: self._on_line_edit_finished(vn, le.text()))
        elif prop_type == "bool":
            checkbox = QCheckBox(label_text); widget = checkbox # Label is part of checkbox
            try: checkbox.setChecked(bool(current_value))
            except: checkbox.setChecked(bool(definition["default"]))
            # stateChanged gives int, convert to bool
            checkbox.stateChanged.connect(lambda state_int, vn=var_name: self._on_property_value_changed(vn, state_int == Qt.CheckState.Checked.value))


        if widget:
            if isinstance(widget, QCheckBox): # QCheckBox includes its own label
                layout.addRow(widget) # Add checkbox directly, its text is the label
            else:
                layout.addRow(label_text + ":", widget)
            self.input_widgets[var_name] = widget
        else:
            layout.addRow(label_text + ":", QLabel(f"Unsupported type: {prop_type}"))

    def _on_line_edit_finished(self, var_name: str, text_value: str):
        self._on_property_value_changed(var_name, text_value)

    def _on_property_value_changed(self, var_name: str, new_value: Any):
        if self.current_object_data_ref:
            # Ensure 'properties' dict exists, create if not.
            if "properties" not in self.current_object_data_ref or not isinstance(self.current_object_data_ref.get("properties"), dict) :
                self.current_object_data_ref["properties"] = {}
            
            game_type_id = str(self.current_object_data_ref.get("game_type_id"))
            definition = ED_CONFIG.EDITABLE_ASSET_VARIABLES.get(game_type_id, {}).get(var_name)
            
            if definition:
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
                    # Revert widget value to current_stored_value
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


    def _change_object_color(self, map_object_data_ref: Optional[Dict[str, Any]]): # Explicit type hint
        if not map_object_data_ref: return
        
        current_color_tuple = map_object_data_ref.get("override_color")
        if not current_color_tuple:
            asset_key = map_object_data_ref.get("asset_editor_key")
            asset_palette_data = self.editor_state.assets_palette.get(str(asset_key))
            if asset_palette_data:
                current_color_tuple = asset_palette_data.get("base_color_tuple") or \
                                      (asset_palette_data.get("surface_params_dims_color")[2] if asset_palette_data.get("surface_params_dims_color") else None)
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
                if isinstance(color_button, QPushButton):
                    self._update_color_button_visuals(color_button, map_object_data_ref)


    def clear_display(self):
        self.clear_layout()
        # self.no_selection_label is recreated in clear_layout
        if self.no_selection_label:
            self.no_selection_label.setText("Select an object on the map or an asset type from the palette to see its properties.")
            self.no_selection_label.setVisible(True)
            if self.no_selection_label.parentWidget():
                self.no_selection_label.parentWidget().setVisible(True)