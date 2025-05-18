# editor_ui_panels.py
# -*- coding: utf-8 -*-
"""
Custom Qt Widgets for UI Panels (Asset Palette, Properties Editor)
in the PySide6 Level Editor.
"""
import logging
from typing import Optional, Dict, Any, List, Tuple

from PySide6.QtWidgets import (
    QWidget, QListWidget, QListWidgetItem, QVBoxLayout,
    QLabel, QLineEdit, QCheckBox, QComboBox, QPushButton, QScrollArea,
    QFormLayout, QSpinBox, QDoubleSpinBox, QColorDialog, QGroupBox
)
from PySide6.QtGui import QIcon, QPalette, QColor, QPixmap # Added QPixmap
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
            # Optionally add a placeholder item:
            # placeholder = QListWidgetItem("No assets loaded or defined.")
            # placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            # self.asset_list_widget.addItem(placeholder)
            return
        logger.debug("Populating asset palette UI...")

        categorized_assets: Dict[str, List[Tuple[str, Dict]]] = {}
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
                    pixmap: Optional[QPixmap] = data.get("q_pixmap")
                    if pixmap and not pixmap.isNull():
                        item_text = data.get("name_in_palette", key.replace("_", " ").title())
                        
                        list_item = QListWidgetItem(QIcon(pixmap), item_text)
                        list_item.setData(Qt.ItemDataRole.UserRole, key)
                        fm = self.asset_list_widget.fontMetrics()
                        text_width = fm.horizontalAdvance(item_text)
                        # Ensure icon size is considered for width, and text height for overall item height
                        item_width = max(ED_CONFIG.ASSET_PALETTE_ICON_SIZE_W + 10, text_width + 10)
                        item_height = ED_CONFIG.ASSET_PALETTE_ICON_SIZE_H + fm.height() + 15 # Added more padding
                        list_item.setSizeHint(QSize(item_width, item_height))
                        self.asset_list_widget.addItem(list_item)
                    else:
                        logger.warning(f"Asset '{key}' missing valid QPixmap, not added to palette.")
        logger.debug(f"Asset palette UI populated with {self.asset_list_widget.count()} displayable items.")

    @Slot(QListWidgetItem)
    def on_item_clicked(self, item: QListWidgetItem):
        if not (item.flags() & Qt.ItemFlag.ItemIsEnabled): return

        asset_key = item.data(Qt.ItemDataRole.UserRole)
        if asset_key:
            asset_data = self.editor_state.assets_palette.get(str(asset_key)) # Ensure key is str
            if asset_data:
                current_name = asset_data.get("name_in_palette", str(asset_key))
                if asset_data.get("category") == "tool" or str(asset_data.get("game_type_id", "")).startswith("tool_"):
                    self.tool_selected.emit(str(asset_key))
                    if hasattr(self.parent_window, 'show_status_message'):
                        self.parent_window.show_status_message(f"Tool selected: {current_name}")
                else:
                    self.asset_selected.emit(str(asset_key))
                    if hasattr(self.parent_window, 'show_status_message'):
                         self.parent_window.show_status_message(f"Asset selected: {current_name}")
            # Do not clearSelection here if you want to see which item is active in the palette
            # self.asset_list_widget.setCurrentItem(item) # This makes it visually selected

    def clear_selection(self):
        self.asset_list_widget.clearSelection()


# --- PropertiesEditorDockWidget ---
class PropertiesEditorDockWidget(QWidget):
    properties_changed = Signal(dict)

    def __init__(self, editor_state: EditorState, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.editor_state = editor_state
        self.parent_window = parent # Should be EditorMainWindow instance
        self.current_object_data_ref: Optional[Dict] = None
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
        self.clear_layout() # Initialize with the "no selection" message

    def clear_layout(self):
        self.current_object_data_ref = None
        self.current_asset_type_for_defaults = None
        self.input_widgets.clear()
        while self.form_layout.count():
            item = self.form_layout.takeAt(0)
            widget_to_delete = None
            if item.widget(): widget_to_delete = item.widget()
            elif item.layout(): # Clear layout and its widgets
                layout_to_clear = item.layout()
                while layout_to_clear.count():
                    child = layout_to_clear.takeAt(0)
                    if child.widget(): child.widget().deleteLater()
                layout_to_clear.deleteLater() # Delete the layout itself
            if widget_to_delete: widget_to_delete.deleteLater()
        
        # Re-add the placeholder label
        self.no_selection_label = QLabel("Select an object or asset to see properties.")
        self.no_selection_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.no_selection_label.setWordWrap(True)
        self.form_layout.addRow(self.no_selection_label)
        self.no_selection_label.setVisible(True)


    @Slot(object) # dict or None
    def display_map_object_properties(self, map_object_data_ref: Optional[Dict]):
        self.clear_layout()
        if not map_object_data_ref or not isinstance(map_object_data_ref, dict):
            self.no_selection_label.setText("Select an object on the map to edit its properties.")
            self.no_selection_label.setVisible(True)
            return

        self.current_object_data_ref = map_object_data_ref
        self.no_selection_label.setVisible(False)

        game_type_id = str(map_object_data_ref.get("game_type_id", "Unknown"))
        asset_editor_key = str(map_object_data_ref.get("asset_editor_key", "N/A"))
        
        title_label = QLabel(f"Object Properties: {game_type_id}")
        font = title_label.font(); font.setBold(True); font.setPointSize(ED_CONFIG.FONT_SIZE_MEDIUM); title_label.setFont(font)
        self.form_layout.addRow(title_label)

        self.form_layout.addRow("Asset Key:", QLabel(asset_editor_key))
        self.form_layout.addRow("Coords (X,Y):", QLabel(f"({map_object_data_ref.get('world_x')}, {map_object_data_ref.get('world_y')})"))

        asset_palette_data = self.editor_state.assets_palette.get(asset_editor_key)
        if asset_palette_data and asset_palette_data.get("colorable"):
            color_button = QPushButton() # Text will be set by _update_color_button_text
            self.input_widgets["_color_button"] = color_button
            self._update_color_button_visuals(color_button, map_object_data_ref)
            color_button.clicked.connect(lambda: self._change_object_color(map_object_data_ref))
            self.form_layout.addRow("Color:", color_button)


        object_custom_props = map_object_data_ref.get("properties")
        if not isinstance(object_custom_props, dict): # Ensure it's a dict
             object_custom_props = {}
             map_object_data_ref["properties"] = object_custom_props # Initialize if missing

        if game_type_id and game_type_id in ED_CONFIG.EDITABLE_ASSET_VARIABLES:
            prop_definitions = ED_CONFIG.EDITABLE_ASSET_VARIABLES[game_type_id]
            if prop_definitions:
                props_group = QGroupBox("Custom Properties")
                props_layout = QFormLayout(props_group)
                for var_name, definition in prop_definitions.items():
                    current_value = object_custom_props.get(var_name, definition["default"])
                    self._create_property_field(var_name, definition, current_value, props_layout)
                self.form_layout.addRow(props_group)
        else:
            self.form_layout.addRow(QLabel("No custom properties for this object type."))


    @Slot(str)
    def display_asset_properties(self, asset_editor_key: Optional[str]):
        if not asset_editor_key:
            if not self.current_object_data_ref:
                self.clear_layout()
                self.no_selection_label.setText("Select an object or asset...")
                self.no_selection_label.setVisible(True)
            return

        self.clear_layout()
        self.current_asset_type_for_defaults = asset_editor_key
        self.no_selection_label.setVisible(False)

        asset_data = self.editor_state.assets_palette.get(str(asset_editor_key))
        if not asset_data: return

        game_type_id = str(asset_data.get("game_type_id", "Unknown"))
        title_label = QLabel(f"Asset Type: {asset_data.get('name_in_palette', game_type_id)}")
        font = title_label.font(); font.setBold(True); font.setPointSize(ED_CONFIG.FONT_SIZE_MEDIUM); title_label.setFont(font)
        self.form_layout.addRow(title_label)

        if asset_data.get("colorable"):
             self.form_layout.addRow("Colorable:", QLabel("Yes"))
             default_color = asset_data.get("base_color_tuple") or \
                             (asset_data.get("surface_params_dims_color")[2] if asset_data.get("surface_params_dims_color") else None)
             if default_color:
                self.form_layout.addRow("Default Asset Color:", QLabel(str(default_color)))

        if game_type_id and game_type_id in ED_CONFIG.EDITABLE_ASSET_VARIABLES:
            props_group = QGroupBox("Default Editable Properties")
            props_layout = QFormLayout(props_group)
            prop_definitions = ED_CONFIG.EDITABLE_ASSET_VARIABLES[game_type_id]
            for var_name, definition in prop_definitions.items():
                default_val_label = QLabel(str(definition["default"]))
                props_layout.addRow(f"{var_name.replace('_', ' ').title()}:", default_val_label)
            self.form_layout.addRow(props_group)
        else:
            self.form_layout.addRow(QLabel("No editable default properties for this asset type."))

    def _update_color_button_visuals(self, button: QPushButton, object_data_ref: Dict):
        color_tuple = object_data_ref.get("override_color")
        asset_key = object_data_ref.get("asset_editor_key")
        asset_palette_data = self.editor_state.assets_palette.get(str(asset_key))
        
        is_overridden = bool(color_tuple)
        if not color_tuple and asset_palette_data: # Determine a default if no override
            if asset_palette_data.get("base_color_tuple"):
                color_tuple = asset_palette_data.get("base_color_tuple")
            elif asset_palette_data.get("surface_params_dims_color"):
                color_tuple = asset_palette_data.get("surface_params_dims_color")[2]
            else:
                color_tuple = (128,128,128) # Fallback display color

        button_text = f"RGB: {color_tuple}"
        if not is_overridden:
            button_text += " (Default)"
        button.setText(button_text)
            
        if color_tuple:
            palette = button.palette()
            palette.setColor(QPalette.ColorRole.Button, QColor(*color_tuple))
            # Set text color based on background brightness
            luma = 0.299 * color_tuple[0] + 0.587 * color_tuple[1] + 0.114 * color_tuple[2]
            text_q_color = QColor(Qt.GlobalColor.black) if luma > 128 else QColor(Qt.GlobalColor.white)
            palette.setColor(QPalette.ColorRole.ButtonText, text_q_color)
            button.setPalette(palette)
            button.setAutoFillBackground(True)
            button.setStyleSheet("QPushButton { border: 1px solid black; min-height: 20px; }")
            button.update()


    def _create_property_field(self, var_name: str, definition: Dict, current_value: Any, layout: QFormLayout):
        label_text = definition.get("label", var_name.replace("_", " ").title()) # Use custom label if provided
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
                except ValueError:
                    if str(definition["default"]) in definition["options"]:
                         combo.setCurrentText(str(definition["default"]))
                combo.currentTextChanged.connect(lambda val, vn=var_name: self._on_property_value_changed(vn, val))
            else:
                line_edit = QLineEdit(str(current_value)); widget = line_edit
                line_edit.editingFinished.connect(lambda le=line_edit, vn=var_name: self._on_line_edit_finished(vn, le.text()))
        elif prop_type == "bool":
            checkbox = QCheckBox(); widget = checkbox # Checkbox has no separate text label in QFormLayout by default
            try: checkbox.setChecked(bool(current_value))
            except: checkbox.setChecked(bool(definition["default"]))
            checkbox.stateChanged.connect(lambda state_int, vn=var_name: self._on_property_value_changed(vn, state_int == Qt.CheckState.Checked.value))

        if widget:
            layout.addRow(label_text + ":", widget)
            self.input_widgets[var_name] = widget
        else:
            layout.addRow(label_text + ":", QLabel(f"Unsupported type: {prop_type}"))

    def _on_line_edit_finished(self, var_name: str, text_value: str):
        self._on_property_value_changed(var_name, text_value)

    def _on_property_value_changed(self, var_name: str, new_value: Any):
        if self.current_object_data_ref:
            if "properties" not in self.current_object_data_ref: self.current_object_data_ref["properties"] = {}
            game_type_id = str(self.current_object_data_ref.get("game_type_id"))
            definition = ED_CONFIG.EDITABLE_ASSET_VARIABLES.get(game_type_id, {}).get(var_name)
            if definition:
                prop_type = definition["type"]
                current_stored_value = self.current_object_data_ref["properties"].get(var_name, definition["default"])
                typed_new_value = new_value
                try:
                    if prop_type == "int": typed_new_value = int(new_value)
                    elif prop_type == "float": typed_new_value = float(new_value)
                    elif prop_type == "bool": typed_new_value = bool(new_value) # new_value from checkbox is already bool
                except (ValueError, TypeError) as e:
                    logger.warning(f"Casting error for '{var_name}': {new_value} to {prop_type}. Error: {e}")
                    # Revert widget if cast fails (optional)
                    widget = self.input_widgets.get(var_name)
                    if widget:
                        if isinstance(widget, QSpinBox): widget.setValue(int(current_stored_value))
                        elif isinstance(widget, QDoubleSpinBox): widget.setValue(float(current_stored_value))
                        elif isinstance(widget, QLineEdit): widget.setText(str(current_stored_value))
                        elif isinstance(widget, QCheckBox): widget.setChecked(bool(current_stored_value))
                        elif isinstance(widget, QComboBox): widget.setCurrentText(str(current_stored_value))
                    return

                if current_stored_value != typed_new_value:
                    editor_history.push_undo_state(self.editor_state)
                    self.current_object_data_ref["properties"][var_name] = typed_new_value
                    self.properties_changed.emit(self.current_object_data_ref)
                    logger.debug(f"Property '{var_name}' changed to '{typed_new_value}' for object.")

    def _change_object_color(self, map_object_data_ref: Optional[Dict]):
        if not map_object_data_ref: return
        
        current_color_tuple = map_object_data_ref.get("override_color")
        if not current_color_tuple: # Determine a sensible default if no override
            asset_key = map_object_data_ref.get("asset_editor_key")
            asset_palette_data = self.editor_state.assets_palette.get(str(asset_key))
            if asset_palette_data:
                current_color_tuple = asset_palette_data.get("base_color_tuple") or \
                                      (asset_palette_data.get("surface_params_dims_color")[2] if asset_palette_data.get("surface_params_dims_color") else None)
            if not current_color_tuple: current_color_tuple = (128,128,128) # Absolute fallback

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
        self.clear_layout() # This now re-adds the no_selection_label
        self.no_selection_label.setText("Select an object on the map or an asset type from the palette to see its properties.")
        self.no_selection_label.setVisible(True)