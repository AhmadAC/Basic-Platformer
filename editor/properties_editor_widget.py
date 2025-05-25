#################### START OF FILE: properties_editor_widget.py ####################

# editor/properties_editor_widget.py
# -*- coding: utf-8 -*-
"""
Properties Editor Widget for the Platformer Level Editor.
"""
import logging
import os
from typing import Optional, Dict, Any, List, Tuple

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QMessageBox,
    QLabel, QLineEdit, QCheckBox, QComboBox, QPushButton, QScrollArea,
    QFormLayout, QSpinBox, QDoubleSpinBox, QColorDialog,
    QGroupBox, QSizePolicy, QFileDialog, QSlider
)
from PySide6.QtGui import QIcon, QPalette, QColor, QPixmap, QPainter, QImage
from PySide6.QtCore import Qt, Signal, Slot, QSize

from . import editor_config as ED_CONFIG
from .editor_state import EditorState
from . import editor_history
from . import editor_map_utils 
from .editor_actions import (ACTION_UI_UP, ACTION_UI_DOWN, ACTION_UI_LEFT, ACTION_UI_RIGHT,
                             ACTION_UI_ACCEPT, ACTION_UI_TAB_NEXT, ACTION_UI_TAB_PREV)

logger = logging.getLogger(__name__)


class PropertiesEditorDockWidget(QWidget): # Renamed to match typical usage if it's the main widget in a dock
    properties_changed = Signal(dict) 
    controller_focus_requested_elsewhere = Signal()
    upload_image_for_trigger_requested = Signal(dict) 

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
        self.current_asset_type_for_defaults = None 
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
           (asset_editor_key in self.editor_state.assets_palette and not asset_editor_key.startswith("tool_")): 
            self._create_property_field("layer_order",
                                        {"type": "int", "default": 0, "label": "Layer Order", "min": -100, "max": 100},
                                        map_object_data_ref.get("layer_order", 0), self.form_layout)
            if is_custom_image_type or is_trigger_square_type : 
                self._create_dimension_fields(map_object_data_ref, self.form_layout)

            if is_custom_image_type:
                self._create_crop_fields(map_object_data_ref, self.form_layout)
            
            self._create_property_field("is_flipped_h",
                                        {"type": "bool", "default": False, "label": "Horizontally Flipped"},
                                        map_object_data_ref.get("is_flipped_h", False), self.form_layout)
            self._create_property_field("rotation",
                                        {"type": "int", "default": 0, "label": "Rotation (Degrees)", "min":0, "max":270, "step":90},
                                        map_object_data_ref.get("rotation", 0), self.form_layout)


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
        self._clear_dynamic_widgets_from_form()
        self.current_object_data_ref = None 
        self.current_asset_type_for_defaults = asset_key_or_custom_id

        if not asset_key_or_custom_id:
            if not self.current_object_data_ref: 
                self.no_selection_label.setText("Select an object or asset...")
                self.no_selection_container.setVisible(True)
            self.scroll_widget.adjustSize()
            return
        
        self.no_selection_container.setVisible(False)
        
        asset_data: Optional[Dict] = None 
        display_name_for_title = asset_key_or_custom_id
        game_type_id_for_props: Optional[str] = None

        if asset_key_or_custom_id.startswith(ED_CONFIG.CUSTOM_ASSET_PALETTE_PREFIX):
            filename = asset_key_or_custom_id.split(ED_CONFIG.CUSTOM_ASSET_PALETTE_PREFIX,1)[1]
            display_name_for_title = f"Custom Asset: {filename}"
            game_type_id_for_props = ED_CONFIG.CUSTOM_IMAGE_ASSET_KEY
        else:
            asset_data = self.editor_state.assets_palette.get(str(asset_key_or_custom_id))
            if not asset_data:
                self.scroll_widget.adjustSize()
                return 
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

    def display_custom_asset_palette_info(self, custom_asset_id: str): 
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
        
        if prop_type == "slider":
            slider_layout = QHBoxLayout()
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setMinimum(definition.get("min", 0))
            slider.setMaximum(definition.get("max", ED_CONFIG.TS // 2 if var_name == "corner_radius" else 100))
            
            spin_box = QSpinBox()
            spin_box.setMinimum(definition.get("min", 0))
            spin_box.setMaximum(definition.get("max", ED_CONFIG.TS // 2 if var_name == "corner_radius" else 100))
            
            try: 
                initial_val = int(current_value)
                slider.setValue(initial_val)
                spin_box.setValue(initial_val)
            except (ValueError, TypeError):
                default_val = int(definition["default"])
                slider.setValue(default_val)
                spin_box.setValue(default_val)

            slider.valueChanged.connect(lambda val, sb=spin_box: sb.setValue(val)) 
            slider.valueChanged.connect(lambda val, vn=var_name: self._on_property_value_changed(vn, val))
            spin_box.valueChanged.connect(lambda val, sl=slider: sl.setValue(val))
            spin_box.valueChanged.connect(lambda val, vn=var_name: self._on_property_value_changed(vn, val))

            slider_layout.addWidget(slider, 2) 
            slider_layout.addWidget(spin_box, 1)
            
            container_widget = QWidget()
            container_widget.setLayout(slider_layout)
            widget = container_widget
            self.input_widgets[var_name + "_slider_widget"] = slider
            self.input_widgets[var_name + "_spinbox_widget"] = spin_box
        
        elif prop_type == "int":
            spinner = QSpinBox()
            widget = spinner
            spinner.setMinimum(definition.get("min", -2147483648))
            spinner.setMaximum(definition.get("max", 2147483647))
            if "step" in definition: 
                spinner.setSingleStep(definition["step"])
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
            if var_name == "linked_map_name": # Specific handling for linked_map_name
                hbox = QHBoxLayout()
                line_edit = QLineEdit(str(current_value))
                line_edit.setPlaceholderText("None (or map folder name)")
                line_edit.editingFinished.connect(lambda le=line_edit, vn=var_name: self._on_property_value_changed(vn, le.text()))
                browse_button = QPushButton("...")
                browse_button.setToolTip("Browse for map folder")
                browse_button.clicked.connect(lambda _ch, vn=var_name, le=line_edit: self._browse_for_linked_map(vn, le))
                hbox.addWidget(line_edit, 1)
                hbox.addWidget(browse_button)
                container_widget = QWidget()
                container_widget.setLayout(hbox)
                widget = container_widget
                self.input_widgets[f"{var_name}_lineedit"] = line_edit # Store specifically if needed elsewhere
            elif "options" in definition and isinstance(definition["options"], list):
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
            checkbox = QCheckBox(label_text_for_field) 
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
            if not isinstance(widget, QCheckBox): 
                widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
                layout.addRow(property_name_label, widget)
                self._controller_property_widgets_ordered.append((var_name, widget, property_name_label))
            else: 
                layout.addRow(widget) 
                self._controller_property_widgets_ordered.append((var_name, widget, None)) 
            if var_name not in self.input_widgets or prop_type=="slider" or (prop_type=="str" and var_name=="linked_map_name"): 
                 self.input_widgets[var_name] = widget 
        else:
            layout.addRow(property_name_label, QLabel(f"Unsupported type: {prop_type}"))

    def _browse_for_linked_map(self, var_name: str, line_edit_ref: QLineEdit):
        if not self.current_object_data_ref:
            return
        
        maps_base_dir = editor_map_utils.get_maps_base_directory()
        if not os.path.exists(maps_base_dir):
            QMessageBox.warning(self, "Browse Error", f"Maps directory not found: {maps_base_dir}")
            return

        # Start browsing from the 'maps' directory itself
        selected_dir = QFileDialog.getExistingDirectory(
            self,
            "Select Linked Map Folder",
            maps_base_dir,
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks
        )

        if selected_dir:
            # We only want the name of the map folder relative to the maps_base_dir
            if os.path.normpath(selected_dir).startswith(os.path.normpath(maps_base_dir)):
                map_folder_name = os.path.basename(selected_dir)
                if editor_map_utils.sanitize_map_name(map_folder_name) == map_folder_name: # Check if it's a valid map name
                    line_edit_ref.setText(map_folder_name)
                    self._on_property_value_changed(var_name, map_folder_name)
                else:
                    QMessageBox.warning(self, "Invalid Map Name", f"The selected folder '{map_folder_name}' is not a valid map name.")
            else:
                QMessageBox.warning(self, "Invalid Directory", "Please select a map folder within the project's maps directory.")
        else: # User cancelled
            # If they cancel, we don't change the existing value.
            # If they want to clear it, they can manually delete text or use a clear button (if added)
            pass


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
        slider_widget = self.input_widgets.get(prop_name + "_slider_widget")
        spinbox_widget = self.input_widgets.get(prop_name + "_spinbox_widget")
        
        widget = self.input_widgets.get(widget_key_for_lineedit) or self.input_widgets.get(prop_name)


        if isinstance(slider_widget, QSlider) and isinstance(spinbox_widget, QSpinBox) and prop_name == "corner_radius":
            slider_widget.setValue(int(new_value))
            spinbox_widget.setValue(int(new_value))
        elif isinstance(widget, QLineEdit):
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
        is_sub_property = False 
        
        if var_name in ["layer_order", "current_width", "current_height", "is_flipped_h", "rotation"]:
            target_dict_for_prop = self.current_object_data_ref
            is_sub_property = False
        else: 
            if "properties" not in self.current_object_data_ref or \
               not isinstance(self.current_object_data_ref.get("properties"), dict):
                self.current_object_data_ref["properties"] = {}
            target_dict_for_prop = self.current_object_data_ref["properties"]
            is_sub_property = True
        
        game_type_id = str(self.current_object_data_ref.get("game_type_id"))
        definition: Optional[Dict] = None
        
        if var_name == "layer_order": definition = {"type": "int", "default": 0}
        elif var_name == "current_width": definition = {"type": "int", "default": ED_CONFIG.BASE_GRID_SIZE}
        elif var_name == "current_height": definition = {"type": "int", "default": ED_CONFIG.BASE_GRID_SIZE}
        elif var_name == "is_flipped_h": definition = {"type": "bool", "default": False}
        elif var_name == "rotation": definition = {"type": "int", "default": 0, "step":90} 
        else: 
            if game_type_id in ED_CONFIG.EDITABLE_ASSET_VARIABLES:
                definition = ED_CONFIG.EDITABLE_ASSET_VARIABLES[game_type_id].get(var_name)
        
        if not definition:
            if logger: logger.warning(f"No definition for prop '{var_name}' (GameID: '{game_type_id}'). Cannot process change.")
            return

        prop_type = definition["type"]
        current_stored_value = target_dict_for_prop.get(var_name, definition["default"])
        typed_new_value = new_value
        try:
            if prop_type == "int" or prop_type == "slider": typed_new_value = int(new_value)
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
            if prop_type == "slider": 
                slider_w = self.input_widgets.get(var_name + "_slider_widget")
                spinbox_w = self.input_widgets.get(var_name + "_spinbox_widget")
                if isinstance(slider_w, QSlider): slider_w.setValue(int(current_stored_value))
                if isinstance(spinbox_w, QSpinBox): spinbox_w.setValue(int(current_stored_value))
            elif isinstance(widget_to_revert, QSpinBox): widget_to_revert.setValue(int(current_stored_value))
            elif isinstance(widget_to_revert, QDoubleSpinBox): widget_to_revert.setValue(float(current_stored_value))
            elif isinstance(widget_to_revert, QLineEdit): widget_to_revert.setText(str(current_stored_value))
            elif isinstance(widget_to_revert, QCheckBox): widget_to_revert.setChecked(bool(current_stored_value))
            return
        
        if current_stored_value != typed_new_value:
            editor_history.push_undo_state(self.editor_state) 
            target_dict_for_prop[var_name] = typed_new_value

            if var_name == "corner_radius" and is_sub_property:
                props_dict = target_dict_for_prop 
                should_round_all = typed_new_value > 0
                corner_bool_props = ["round_top_left", "round_top_right", "round_bottom_left", "round_bottom_right"]
                for corner_prop_name in corner_bool_props:
                    if props_dict.get(corner_prop_name) != should_round_all:
                        props_dict[corner_prop_name] = should_round_all
                        checkbox_widget = self.input_widgets.get(corner_prop_name)
                        if isinstance(checkbox_widget, QCheckBox): 
                            checkbox_widget.blockSignals(True) 
                            checkbox_widget.setChecked(should_round_all)
                            checkbox_widget.blockSignals(False)
            
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
            if isinstance(widget, QWidget) and not isinstance(widget, QLabel):
                widget.setStyleSheet("") 
            if label_widget:
                label_widget.setStyleSheet("")

            if widget is self.input_widgets.get("_color_button"):
                self._update_color_button_visuals(widget, self.current_object_data_ref) 
            elif self.current_object_data_ref and self.current_object_data_ref.get("properties"):
                definition = ED_CONFIG.EDITABLE_ASSET_VARIABLES.get(self.current_object_data_ref.get("game_type_id", ""), {}).get(var_name)
                if definition and definition.get("type") == "tuple_color_rgba":
                     props = self.current_object_data_ref.get("properties",{})
                     self._update_rgba_color_button_style(widget, props.get(var_name, definition["default"])) 

        if self._controller_has_focus and self._controller_focused_property_index >= 0 and \
           self._controller_focused_property_index < len(self._controller_property_widgets_ordered):
            var_name, widget, label_widget = self._controller_property_widgets_ordered[self._controller_focused_property_index]
            focus_style_str = str(ED_CONFIG.PROPERTIES_EDITOR_CONTROLLER_FOCUS_BORDER) 
            
            is_color_btn = (widget is self.input_widgets.get("_color_button"))
            is_rgba_color_btn = False
            definition_type = ""
            if self.current_object_data_ref:
                game_type_id = self.current_object_data_ref.get("game_type_id", "")
                prop_def = ED_CONFIG.EDITABLE_ASSET_VARIABLES.get(game_type_id, {}).get(var_name)
                if prop_def: definition_type = prop_def.get("type", "")
                if definition_type == "tuple_color_rgba": is_rgba_color_btn = True
            
            if not is_color_btn and not is_rgba_color_btn and isinstance(widget, QWidget) and not isinstance(widget, (QLabel, QCheckBox)):
                widget.setStyleSheet(f"border: {focus_style_str};")
            elif isinstance(widget, QCheckBox): 
                 pass 
            
            if label_widget:
                 label_widget.setStyleSheet("QLabel { color: " + focus_style_str.split(' ')[-1] + "; font-weight: bold; }")
            
            if isinstance(widget, QWidget) and not isinstance(widget, QLabel): 
                target_focus_widget = widget
                if definition_type == "slider": 
                    slider_sub_widget = self.input_widgets.get(var_name + "_slider_widget")
                    if slider_sub_widget: target_focus_widget = slider_sub_widget
                
                target_focus_widget.setFocus(Qt.FocusReason.OtherFocusReason)
                self.scroll_area.ensureWidgetVisible(target_focus_widget, 10, 10)

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
            
            if isinstance(widget, QWidget) and not isinstance(widget, QLabel): 
                widget.setStyleSheet("") 
            if label_widget:
                label_widget.setStyleSheet("")

            if widget is self.input_widgets.get("_color_button"):
                self._update_color_button_visuals(widget, self.current_object_data_ref) 
            elif self.current_object_data_ref and self.current_object_data_ref.get("properties"):
                definition = ED_CONFIG.EDITABLE_ASSET_VARIABLES.get(self.current_object_data_ref.get("game_type_id", ""), {}).get(var_name)
                if definition and definition.get("type") == "tuple_color_rgba":
                     props = self.current_object_data_ref.get("properties",{})
                     self._update_rgba_color_button_style(widget, props.get(var_name, definition["default"]))
                     
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

        var_name, widget_container, _ = self._controller_property_widgets_ordered[current_idx]
        widget_to_act_on = widget_container 

        prop_def = None
        if self.current_object_data_ref:
            game_type_id = self.current_object_data_ref.get("game_type_id", "")
            if var_name not in ["layer_order", "current_width", "current_height", "is_flipped_h", "rotation"]:
                prop_def = ED_CONFIG.EDITABLE_ASSET_VARIABLES.get(game_type_id, {}).get(var_name)
            elif var_name == "corner_radius": 
                 prop_def = ED_CONFIG.EDITABLE_ASSET_VARIABLES.get(game_type_id, {}).get(var_name)

        if prop_def and prop_def.get("type") == "slider":
             slider_w = self.input_widgets.get(var_name + "_slider_widget")
             if isinstance(slider_w, QSlider):
                 widget_to_act_on = slider_w 

        if action == ACTION_UI_UP:
            self._set_controller_focused_property(current_idx - 1)
        elif action == ACTION_UI_DOWN:
            self._set_controller_focused_property(current_idx + 1)
        elif action == ACTION_UI_ACCEPT:
            if isinstance(widget_container, QPushButton):
                widget_container.click()
            elif isinstance(widget_container, QCheckBox):
                widget_container.toggle()
            elif isinstance(widget_container, QComboBox):
                widget_container.showPopup()
            elif isinstance(widget_container, QWidget) and widget_container.layout() is not None: 
                 # Check if it's the container for linked_map_name or image_path_custom
                 if var_name == "linked_map_name" or (prop_def and prop_def.get("type") == "image_path_custom"):
                     browse_button = widget_container.findChild(QPushButton, "Browse...") # Assuming browse button is default or only button
                     if browse_button: browse_button.click()
                 else:
                    children_buttons = widget_container.findChildren(QPushButton)
                    if children_buttons: 
                        children_buttons[0].click()
        elif action == ACTION_UI_LEFT or action == ACTION_UI_RIGHT:
            step = 1 if action == ACTION_UI_RIGHT else -1
            if isinstance(widget_to_act_on, QSpinBox):
                new_val = widget_to_act_on.value() + step * widget_to_act_on.singleStep()
                if new_val >= widget_to_act_on.minimum() and new_val <= widget_to_act_on.maximum():
                    widget_to_act_on.setValue(new_val)
            elif isinstance(widget_to_act_on, QDoubleSpinBox):
                new_val = widget_to_act_on.value() + step * widget_to_act_on.singleStep()
                if new_val >= widget_to_act_on.minimum() and new_val <= widget_to_act_on.maximum():
                    widget_to_act_on.setValue(new_val)
            elif isinstance(widget_to_act_on, QComboBox):
                new_combo_idx = widget_to_act_on.currentIndex() + step
                if 0 <= new_combo_idx < widget_to_act_on.count():
                    widget_to_act_on.setCurrentIndex(new_combo_idx)
            elif isinstance(widget_to_act_on, QSlider):
                widget_to_act_on.setValue(widget_to_act_on.value() + step * widget_to_act_on.singleStep())

        elif action == ACTION_UI_TAB_NEXT or action == ACTION_UI_TAB_PREV:
            self.controller_focus_requested_elsewhere.emit()
            
#################### END OF FILE: properties_editor_widget.py ####################