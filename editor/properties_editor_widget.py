# editor/properties_editor_widget.py
# -*- coding: utf-8 -*-
"""
Properties Editor Widget for the Platformer Level Editor.
Version 2.2.12 (Corrected indentation and new_combo_idx error, refined layout management)
"""
import logging
import os
from typing import Optional, Dict, Any, List, Tuple

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QCheckBox, QComboBox, QPushButton, QScrollArea,
    QFormLayout, QSpinBox, QDoubleSpinBox, QColorDialog, QMessageBox,
    QGroupBox, QSizePolicy, QFileDialog, QSlider
)
from PySide6.QtGui import QIcon, QPalette, QColor, QPixmap, QPainter, QImage
from PySide6.QtCore import Qt, Signal, Slot, QSize

# Corrected relative imports
from . import editor_config as ED_CONFIG
from .editor_state import EditorState
from . import editor_history
from . import editor_map_utils
from .editor_actions import (ACTION_UI_UP, ACTION_UI_DOWN, ACTION_UI_LEFT, ACTION_UI_RIGHT,
                             ACTION_UI_ACCEPT, ACTION_UI_TAB_NEXT, ACTION_UI_TAB_PREV)

logger = logging.getLogger(__name__)


class PropertiesEditorDockWidget(QWidget):
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

        # Placeholder widget - managed by main_layout
        self.no_selection_label = QLabel("Select an object or asset to see properties.")
        self.no_selection_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.no_selection_label.setWordWrap(True)
        self.no_selection_widget_container = QWidget()
        no_sel_layout = QVBoxLayout(self.no_selection_widget_container)
        no_sel_layout.addWidget(self.no_selection_label)
        no_sel_layout.addStretch()
        self.main_layout.addWidget(self.no_selection_widget_container)

        # ScrollArea for dynamic properties - managed by main_layout
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_widget_for_form = QWidget()
        self.form_layout = QFormLayout() # This is the layout FOR self.scroll_widget_for_form
        self.scroll_widget_for_form.setLayout(self.form_layout)
        
        self.form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.form_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        self.form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        
        self.scroll_area.setWidget(self.scroll_widget_for_form)
        self.main_layout.addWidget(self.scroll_area)
        
        self.clear_display() # Initial state: show "no selection" message
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def _clear_dynamic_widgets_from_form(self):
        self.input_widgets.clear()
        self._controller_property_widgets_ordered.clear()
        self._controller_focused_property_index = -1

        # Remove all rows from the form_layout that holds the dynamic properties
        while self.form_layout.rowCount() > 0:
            self.form_layout.removeRow(0) # This also deletes widgets in the row
        
        self._update_focused_property_visuals()

    @Slot(object)
    def display_map_object_properties(self, map_object_data_ref: Optional[Dict[str, Any]]):
        logger.debug(f"PropertiesEditor: display_map_object_properties called with type: {type(map_object_data_ref)}")
        self._clear_dynamic_widgets_from_form()
        self.current_object_data_ref = None
        self.current_asset_type_for_defaults = None

        if not map_object_data_ref or not isinstance(map_object_data_ref, dict):
            self.clear_display() # This will show the no_selection_widget_container
            self.no_selection_label.setText("Select an object on the map to edit its properties.")
            return
        
        self.no_selection_widget_container.setVisible(False)
        self.scroll_area.setVisible(True)
        self.current_object_data_ref = map_object_data_ref
        
        asset_editor_key = str(map_object_data_ref.get("asset_editor_key", "N/A"))
        game_type_id_str = str(map_object_data_ref.get("game_type_id", "Unknown"))
        display_name_for_title = game_type_id_str
        
        is_custom_image_type = (asset_editor_key == ED_CONFIG.CUSTOM_IMAGE_ASSET_KEY)
        is_trigger_square_type = (asset_editor_key == ED_CONFIG.TRIGGER_SQUARE_ASSET_KEY)

        if is_custom_image_type:
            display_name_for_title = "Custom Image"
            src_path = map_object_data_ref.get("source_file_path", "")
            if src_path: display_name_for_title += f" ({os.path.basename(src_path)})"
        elif is_trigger_square_type: display_name_for_title = "Trigger Square"
        else:
            asset_data_for_title = self.editor_state.assets_palette.get(asset_editor_key)
            if asset_data_for_title and asset_data_for_title.get("name_in_palette"):
                display_name_for_title = asset_data_for_title["name_in_palette"]
            elif "_" in display_name_for_title: display_name_for_title = display_name_for_title.replace("_", " ").title()
        
        title_label = QLabel(f"Object: {display_name_for_title}")
        font_title = title_label.font(); font_title.setBold(True); font_title.setPointSize(ED_CONFIG.FONT_SIZE_MEDIUM); title_label.setFont(font_title)
        self.form_layout.addRow(title_label) # Add to the dynamic form layout

        # Use a local counter for inserting rows into self.form_layout
        current_form_row = 1 

        if not is_custom_image_type and not is_trigger_square_type:
            asset_key_label_text = QLabel("Asset Key:"); asset_key_value_label = QLabel(asset_editor_key)
            self.form_layout.insertRow(current_form_row, asset_key_label_text, asset_key_value_label); current_form_row +=1
        
        coords_label_text = QLabel("Coords (X,Y):"); coords_value_label = QLabel(f"({map_object_data_ref.get('world_x')}, {map_object_data_ref.get('world_y')})")
        self.form_layout.insertRow(current_form_row, coords_label_text, coords_value_label); current_form_row +=1

        if is_custom_image_type or is_trigger_square_type or \
           (asset_editor_key in self.editor_state.assets_palette and not asset_editor_key.startswith("tool_")):
            current_form_row = self._create_property_field("layer_order", {"type": "int", "default": 0, "label": "Layer Order", "min": -100, "max": 100}, map_object_data_ref.get("layer_order", 0), self.form_layout, current_form_row)
            if is_custom_image_type or is_trigger_square_type :
                current_form_row = self._create_dimension_fields(map_object_data_ref, self.form_layout, current_form_row)
            if is_custom_image_type:
                current_form_row = self._create_crop_fields(map_object_data_ref, self.form_layout, current_form_row)
            current_form_row = self._create_property_field("is_flipped_h", {"type": "bool", "default": False, "label": "Horizontally Flipped"}, map_object_data_ref.get("is_flipped_h", False), self.form_layout, current_form_row)
            current_form_row = self._create_property_field("rotation", {"type": "int", "default": 0, "label": "Rotation (Degrees)", "min":0, "max":270, "step":90}, map_object_data_ref.get("rotation", 0), self.form_layout, current_form_row)

        asset_palette_data = self.editor_state.assets_palette.get(asset_editor_key)
        if asset_palette_data and asset_palette_data.get("colorable") and not is_custom_image_type and not is_trigger_square_type:
            color_label_text = QLabel("Color:"); color_button = QPushButton()
            self.input_widgets["_color_button"] = color_button
            self._update_color_button_visuals(color_button, map_object_data_ref)
            color_button.clicked.connect(lambda _checked=False, obj_ref=map_object_data_ref: self._change_object_color(obj_ref))
            self.form_layout.insertRow(current_form_row, color_label_text, color_button); current_form_row +=1
            self._controller_property_widgets_ordered.append(("_color_button", color_button, color_label_text))

        object_custom_props = map_object_data_ref.get("properties", {})
        if not isinstance(object_custom_props, dict): object_custom_props = {}; map_object_data_ref["properties"] = object_custom_props
        
        editable_vars_config_key = game_type_id_str
        if editable_vars_config_key and editable_vars_config_key in ED_CONFIG.EDITABLE_ASSET_VARIABLES:
            prop_definitions = ED_CONFIG.EDITABLE_ASSET_VARIABLES[editable_vars_config_key]
            if prop_definitions:
                props_group = QGroupBox("Object Properties"); props_group.setFlat(False)
                props_layout_internal = QFormLayout(props_group) # Inner layout for the group box
                props_layout_internal.setContentsMargins(6, 10, 6, 6); props_layout_internal.setSpacing(6)
                props_layout_internal.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
                props_layout_internal.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
                group_row_idx = 0
                for var_name, definition in prop_definitions.items():
                    current_value = object_custom_props.get(var_name, definition["default"])
                    group_row_idx = self._create_property_field(var_name, definition, current_value, props_layout_internal, group_row_idx) # Add to group's layout
                self.form_layout.insertRow(current_form_row, props_group); current_form_row +=1 # Add group box to main form
        elif not is_custom_image_type and not is_trigger_square_type:
            no_props_label = QLabel("No custom properties for this object type.")
            self.form_layout.insertRow(current_form_row, no_props_label); current_form_row +=1
        
        self.scroll_widget_for_form.adjustSize()
        if self._controller_has_focus: self._set_controller_focused_property(0)

    @Slot(str)
    def display_asset_properties(self, asset_key_or_custom_id: Optional[str]):
        logger.debug(f"PropertiesEditor: display_asset_properties called with {asset_key_or_custom_id}")
        self._clear_dynamic_widgets_from_form()
        self.current_object_data_ref = None
        self.current_asset_type_for_defaults = asset_key_or_custom_id

        if not asset_key_or_custom_id:
            self.clear_display()
            self.no_selection_label.setText("Select an object or asset...")
            return
        
        self.no_selection_widget_container.setVisible(False)
        self.scroll_area.setVisible(True)
        
        current_form_row = 0
        asset_data: Optional[Dict] = None; display_name_for_title = asset_key_or_custom_id
        game_type_id_for_props: Optional[str] = None

        if asset_key_or_custom_id.startswith(ED_CONFIG.CUSTOM_ASSET_PALETTE_PREFIX):
            filename = asset_key_or_custom_id.split(ED_CONFIG.CUSTOM_ASSET_PALETTE_PREFIX,1)[1]
            display_name_for_title = f"Custom Asset: {filename}"; game_type_id_for_props = ED_CONFIG.CUSTOM_IMAGE_ASSET_KEY
        else:
            asset_data = self.editor_state.assets_palette.get(str(asset_key_or_custom_id))
            if not asset_data: self.scroll_widget_for_form.adjustSize(); return
            game_type_id_for_props = str(asset_data.get("game_type_id", "Unknown"))
            display_name_for_title = asset_data.get('name_in_palette', game_type_id_for_props)
            if display_name_for_title == game_type_id_for_props and "_" in display_name_for_title:
                display_name_for_title = display_name_for_title.replace("_", " ").title()
            
        title_label = QLabel(f"Asset Type: {display_name_for_title}")
        font_title = title_label.font(); font_title.setBold(True); font_title.setPointSize(ED_CONFIG.FONT_SIZE_MEDIUM); title_label.setFont(font_title)
        self.form_layout.insertRow(current_form_row, title_label); current_form_row +=1

        if asset_data and asset_data.get("colorable"):
            colorable_label_text = QLabel("Colorable:"); colorable_info_label = QLabel("Yes (by tool or properties)")
            self.form_layout.insertRow(current_form_row, colorable_label_text, colorable_info_label); current_form_row +=1
            default_color_val = asset_data.get("base_color_tuple")
            if not default_color_val:
                _sp = asset_data.get("surface_params")
                if _sp and isinstance(_sp, tuple) and len(_sp) == 3: default_color_val = _sp[2] # type: ignore
            if default_color_val:
                default_color_label_text = QLabel("Default Asset Color:"); default_color_value_label = QLabel(str(default_color_val))
                self.form_layout.insertRow(current_form_row, default_color_label_text, default_color_value_label); current_form_row +=1

        if game_type_id_for_props and game_type_id_for_props in ED_CONFIG.EDITABLE_ASSET_VARIABLES:
            props_group = QGroupBox("Default Editable Properties"); props_group.setFlat(False)
            props_layout_internal = QFormLayout(props_group)
            props_layout_internal.setContentsMargins(6,10,6,6); props_layout_internal.setSpacing(6)
            props_layout_internal.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            props_layout_internal.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
            prop_definitions = ED_CONFIG.EDITABLE_ASSET_VARIABLES[game_type_id_for_props]
            group_row_idx_asset = 0
            for var_name, definition in prop_definitions.items():
                prop_name_label = QLabel(definition.get('label', var_name.replace('_', ' ').title()) + ":")
                default_val_label = QLabel(str(definition["default"]))
                props_layout_internal.insertRow(group_row_idx_asset, prop_name_label, default_val_label); group_row_idx_asset += 1
            self.form_layout.insertRow(current_form_row, props_group); current_form_row +=1
        else:
            no_props_label = QLabel("No editable default properties for this asset type.")
            self.form_layout.insertRow(current_form_row, no_props_label); current_form_row +=1
        
        self.scroll_widget_for_form.adjustSize()
        if self._controller_has_focus: self._set_controller_focused_property(0)

    def display_custom_asset_palette_info(self, custom_asset_id: str):
        self.display_asset_properties(custom_asset_id)

    def clear_display(self):
        self._clear_dynamic_widgets_from_form() # Empties self.form_layout
        self.current_object_data_ref = None
        self.current_asset_type_for_defaults = None
        
        self.no_selection_label.setText("Select an object on the map or an asset type from the palette to see its properties.")
        self.no_selection_widget_container.setVisible(True) # Show the placeholder
        self.scroll_area.setVisible(False) # Hide the (now empty) scroll area for properties
        
        self.adjustSize() # May help the parent dock widget adjust

    def _update_color_button_visuals(self, button: QPushButton, object_data_ref: Optional[Dict[str, Any]]):
        if not object_data_ref: return
        color_tuple = object_data_ref.get("override_color"); is_overridden = bool(color_tuple)
        _sp = None
        if not color_tuple:
            asset_key = object_data_ref.get("asset_editor_key"); asset_palette_data = self.editor_state.assets_palette.get(str(asset_key))
            if asset_palette_data:
                color_tuple = asset_palette_data.get("base_color_tuple")
                if not color_tuple: _sp = asset_palette_data.get("surface_params")
                if _sp and isinstance(_sp, tuple) and len(_sp) == 3: color_tuple = _sp[2] # type: ignore
            if not color_tuple: color_tuple = (128,128,128)
        button_text = f"RGB: {color_tuple}"; button.setText(button_text + (" (Default)" if not is_overridden else ""))
        if color_tuple:
            q_color = QColor(*color_tuple); palette = button.palette() # type: ignore
            palette.setColor(QPalette.ColorRole.Button, q_color)
            luma = 0.299 * color_tuple[0] + 0.587 * color_tuple[1] + 0.114 * color_tuple[2] # type: ignore
            text_q_color = QColor(Qt.GlobalColor.black) if luma > 128 else QColor(Qt.GlobalColor.white)
            palette.setColor(QPalette.ColorRole.ButtonText, text_q_color); button.setPalette(palette); button.setAutoFillBackground(True)
            border_style = "1px solid black"
            if self._controller_has_focus and self._controller_focused_property_index >= 0 and self._controller_focused_property_index < len(self._controller_property_widgets_ordered) and self._controller_property_widgets_ordered[self._controller_focused_property_index][1] is button:
                border_style = ED_CONFIG.PROPERTIES_EDITOR_CONTROLLER_FOCUS_BORDER
            button.setStyleSheet(f"QPushButton {{ border: {border_style}; min-height: 20px; padding: 2px; }}"); button.update()

    def _create_property_field(self, var_name: str, definition: Dict[str, Any], current_value: Any, layout: QFormLayout, insert_at_row: int = -1) -> int:
        label_text_for_field = definition.get("label", var_name.replace('_', ' ').title())
        property_name_label = QLabel(label_text_for_field + ":")
        property_name_label.setWordWrap(True)
        widget: Optional[QWidget] = None
        prop_type = definition["type"]
        
        if prop_type == "slider":
            slider_layout = QHBoxLayout(); slider = QSlider(Qt.Orientation.Horizontal); slider.setMinimum(definition.get("min", 0)); slider.setMaximum(definition.get("max", ED_CONFIG.TS // 2 if var_name == "corner_radius" else 100))
            spin_box = QSpinBox(); spin_box.setMinimum(definition.get("min", 0)); spin_box.setMaximum(definition.get("max", ED_CONFIG.TS // 2 if var_name == "corner_radius" else 100))
            try: initial_val = int(current_value); slider.setValue(initial_val); spin_box.setValue(initial_val)
            except (ValueError, TypeError): default_val = int(definition["default"]); slider.setValue(default_val); spin_box.setValue(default_val)
            slider.valueChanged.connect(lambda val, sb=spin_box: sb.setValue(val)); slider.valueChanged.connect(lambda val, vn=var_name: self._on_property_value_changed(vn, val))
            spin_box.valueChanged.connect(lambda val, sl=slider: sl.setValue(val)); spin_box.valueChanged.connect(lambda val, vn=var_name: self._on_property_value_changed(vn, val))
            slider_layout.addWidget(slider, 2); slider_layout.addWidget(spin_box, 1); container_widget = QWidget(); container_widget.setLayout(slider_layout); widget = container_widget
            self.input_widgets[var_name + "_slider_widget"] = slider; self.input_widgets[var_name + "_spinbox_widget"] = spin_box
        elif prop_type == "int":
            spinner = QSpinBox(); widget = spinner; spinner.setMinimum(definition.get("min", -2147483648)); spinner.setMaximum(definition.get("max", 2147483647))
            if "step" in definition: spinner.setSingleStep(definition["step"])
            try: spinner.setValue(int(current_value))
            except (ValueError, TypeError): spinner.setValue(int(definition["default"]))
            spinner.valueChanged.connect(lambda val, vn=var_name: self._on_property_value_changed(vn, val))
        elif prop_type == "float":
            double_spinner = QDoubleSpinBox(); widget = double_spinner; double_spinner.setMinimum(definition.get("min", -1.79e+308)); double_spinner.setMaximum(definition.get("max", 1.79e+308))
            try: double_spinner.setValue(float(current_value))
            except (ValueError, TypeError): double_spinner.setValue(float(definition["default"]))
            double_spinner.setDecimals(definition.get("decimals", 2)); double_spinner.valueChanged.connect(lambda val, vn=var_name: self._on_property_value_changed(vn, val))
        elif prop_type == "str":
            if var_name == "linked_map_name":
                hbox = QHBoxLayout(); line_edit = QLineEdit(str(current_value)); line_edit.setPlaceholderText("None (or map folder name)")
                line_edit.editingFinished.connect(lambda le=line_edit, vn=var_name: self._on_property_value_changed(vn, le.text()))
                browse_button = QPushButton("..."); browse_button.setToolTip("Browse for map folder"); browse_button.setFixedWidth(browse_button.fontMetrics().horizontalAdvance(" ... ") + 10)
                browse_button.clicked.connect(lambda _ch, vn=var_name, le=line_edit: self._browse_for_linked_map(vn, le))
                hbox.addWidget(line_edit, 1); hbox.addWidget(browse_button); container_widget = QWidget(); container_widget.setLayout(hbox); widget = container_widget
                self.input_widgets[f"{var_name}_lineedit"] = line_edit
            elif "options" in definition and isinstance(definition["options"], list):
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
            except (ValueError, TypeError): checkbox.setChecked(bool(definition["default"]))
            checkbox.stateChanged.connect(lambda state_int, vn=var_name: self._on_property_value_changed(vn, state_int == Qt.CheckState.Checked.value))
        elif prop_type == "tuple_color_rgba":
            color_val_prop = current_value if isinstance(current_value, (list,tuple)) and len(current_value) == 4 else definition["default"]
            color_button = QPushButton(str(color_val_prop)); self._update_rgba_color_button_style(color_button, color_val_prop)
            color_button.clicked.connect(lambda _ch, vn=var_name, btn=color_button: self._change_rgba_color_property(vn, btn)); widget = color_button
        elif prop_type == "image_path_custom":
            hbox = QHBoxLayout(); line_edit = QLineEdit(str(current_value)); line_edit.setReadOnly(True)
            browse_button = QPushButton("Browse..."); browse_button.clicked.connect(lambda _ch, vn=var_name: self._browse_for_trigger_image(vn))
            clear_button = QPushButton("Clear"); clear_button.clicked.connect(lambda _ch, vn=var_name: self._clear_trigger_image(vn))
            hbox.addWidget(line_edit, 1); hbox.addWidget(browse_button); hbox.addWidget(clear_button)
            container_widget = QWidget(); container_widget.setLayout(hbox); widget = container_widget
            self.input_widgets[f"{var_name}_lineedit"] = line_edit
        
        next_row_index = insert_at_row
        if widget:
            widget.setObjectName(f"prop_widget_{var_name}")
            if not isinstance(widget, QCheckBox):
                widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
                layout.insertRow(insert_at_row, property_name_label, widget)
            else:
                layout.insertRow(insert_at_row, widget) # QCheckBox includes its label
            
            self._controller_property_widgets_ordered.append((var_name, widget, property_name_label if not isinstance(widget, QCheckBox) else None))
            
            # Store references for external updates if needed
            if var_name not in self.input_widgets or \
               prop_type=="slider" or \
               (prop_type=="str" and var_name=="linked_map_name") or \
               (prop_type=="image_path_custom"):
                 if not ((prop_type=="str" and var_name=="linked_map_name") or \
                         (prop_type=="image_path_custom") or \
                         prop_type=="slider"): # Avoid double-storing container for these
                     self.input_widgets[var_name] = widget
            next_row_index = insert_at_row + 1
        else:
            layout.insertRow(insert_at_row, property_name_label, QLabel(f"Unsupported type: {prop_type}"))
            next_row_index = insert_at_row + 1
        return next_row_index


    def _create_dimension_fields(self, obj_data_ref: Dict[str, Any], layout: QFormLayout, start_row_index: int) -> int:
        current_row = start_row_index
        width_label = QLabel("Width:"); width_spinner = QSpinBox(); width_spinner.setMinimum(int(ED_CONFIG.BASE_GRID_SIZE / 4)); width_spinner.setMaximum(int(ED_CONFIG.BASE_GRID_SIZE * 100))
        width_spinner.setValue(int(obj_data_ref.get("current_width", ED_CONFIG.BASE_GRID_SIZE))); width_spinner.valueChanged.connect(lambda val: self._on_dimension_changed("current_width", val))
        layout.insertRow(current_row, width_label, width_spinner); self.input_widgets["current_width"] = width_spinner; self._controller_property_widgets_ordered.append(("current_width", width_spinner, width_label)); current_row += 1
        
        height_label = QLabel("Height:"); height_spinner = QSpinBox(); height_spinner.setMinimum(int(ED_CONFIG.BASE_GRID_SIZE / 4)); height_spinner.setMaximum(int(ED_CONFIG.BASE_GRID_SIZE * 100))
        height_spinner.setValue(int(obj_data_ref.get("current_height", ED_CONFIG.BASE_GRID_SIZE))); height_spinner.valueChanged.connect(lambda val: self._on_dimension_changed("current_height", val))
        layout.insertRow(current_row, height_label, height_spinner); self.input_widgets["current_height"] = height_spinner; self._controller_property_widgets_ordered.append(("current_height", height_spinner, height_label)); current_row += 1
        return current_row

    def _create_crop_fields(self, obj_data_ref: Dict[str, Any], parent_layout: QFormLayout, start_row_index: int) -> int:
        current_row = start_row_index
        crop_group = QGroupBox("Image Cropping"); crop_group.setFlat(False); crop_layout = QFormLayout(crop_group)
        crop_layout.setContentsMargins(6, 10, 6, 6); crop_layout.setSpacing(6)
        original_w = obj_data_ref.get("original_width", 0); original_h = obj_data_ref.get("original_height", 0)
        current_crop = obj_data_ref.get("crop_rect"); crop_x_val = 0; crop_y_val = 0; crop_w_val = original_w; crop_h_val = original_h
        if isinstance(current_crop, dict): crop_x_val = current_crop.get("x", 0); crop_y_val = current_crop.get("y", 0); crop_w_val = current_crop.get("width", original_w); crop_h_val = current_crop.get("height", original_h)
        
        group_row_idx_crop = 0
        crop_x_label = QLabel("Crop X:"); crop_x_spinner = QSpinBox(); crop_x_spinner.setMinimum(0); crop_x_spinner.setMaximum(max(0, original_w -1)); crop_x_spinner.setValue(crop_x_val); crop_x_spinner.valueChanged.connect(self._on_crop_value_changed)
        crop_layout.insertRow(group_row_idx_crop, crop_x_label, crop_x_spinner); self.input_widgets["crop_x"] = crop_x_spinner; self._controller_property_widgets_ordered.append(("crop_x", crop_x_spinner, crop_x_label)); group_row_idx_crop +=1
        
        crop_y_label = QLabel("Crop Y:"); crop_y_spinner = QSpinBox(); crop_y_spinner.setMinimum(0); crop_y_spinner.setMaximum(max(0, original_h - 1)); crop_y_spinner.setValue(crop_y_val); crop_y_spinner.valueChanged.connect(self._on_crop_value_changed)
        crop_layout.insertRow(group_row_idx_crop, crop_y_label, crop_y_spinner); self.input_widgets["crop_y"] = crop_y_spinner; self._controller_property_widgets_ordered.append(("crop_y", crop_y_spinner, crop_y_label)); group_row_idx_crop +=1
        
        crop_w_label = QLabel("Crop Width:"); crop_w_spinner = QSpinBox(); crop_w_spinner.setMinimum(1); crop_w_spinner.setMaximum(max(1, original_w)); crop_w_spinner.setValue(crop_w_val); crop_w_spinner.valueChanged.connect(self._on_crop_value_changed)
        crop_layout.insertRow(group_row_idx_crop, crop_w_label, crop_w_spinner); self.input_widgets["crop_width"] = crop_w_spinner; self._controller_property_widgets_ordered.append(("crop_width", crop_w_spinner, crop_w_label)); group_row_idx_crop +=1
        
        crop_h_label = QLabel("Crop Height:"); crop_h_spinner = QSpinBox(); crop_h_spinner.setMinimum(1); crop_h_spinner.setMaximum(max(1, original_h)); crop_h_spinner.setValue(crop_h_val); crop_h_spinner.valueChanged.connect(self._on_crop_value_changed)
        crop_layout.insertRow(group_row_idx_crop, crop_h_label, crop_h_spinner); self.input_widgets["crop_height"] = crop_h_spinner; self._controller_property_widgets_ordered.append(("crop_height", crop_h_spinner, crop_h_label)); group_row_idx_crop +=1
        
        reset_crop_button = QPushButton("Reset Crop to Full Image"); reset_crop_button.clicked.connect(self._on_reset_crop)
        crop_layout.insertRow(group_row_idx_crop, reset_crop_button); self.input_widgets["reset_crop"] = reset_crop_button; self._controller_property_widgets_ordered.append(("reset_crop", reset_crop_button, None)); group_row_idx_crop +=1
        
        parent_layout.insertRow(current_row, crop_group); current_row +=1
        return current_row

    # ... (the rest of the methods should be correctly indented and unchanged from the previous version)
    def _on_crop_value_changed(self):
        if not self.current_object_data_ref: return
        cx_spin = self.input_widgets.get("crop_x"); cy_spin = self.input_widgets.get("crop_y")
        cw_spin = self.input_widgets.get("crop_width"); ch_spin = self.input_widgets.get("crop_height")
        if not all(isinstance(s, QSpinBox) for s in [cx_spin, cy_spin, cw_spin, ch_spin]): logger.error("Crop spinners not found or not QSpinBox."); return
        new_crop_x = cx_spin.value(); new_crop_y = cy_spin.value(); new_crop_w = cw_spin.value(); new_crop_h = ch_spin.value()
        original_w = self.current_object_data_ref.get("original_width", 0); original_h = self.current_object_data_ref.get("original_height", 0)
        if new_crop_w < 1 or new_crop_h < 1 or new_crop_x < 0 or new_crop_y < 0 or new_crop_x + new_crop_w > original_w or new_crop_y + new_crop_h > original_h:
            logger.warning(f"Attempted to set invalid crop values: X={new_crop_x}, Y={new_crop_y}, W={new_crop_w}, H={new_crop_h} for original {original_w}x{original_h}")
        new_crop_rect = {"x": new_crop_x, "y": new_crop_y, "width": new_crop_w, "height": new_crop_h}
        current_rect = self.current_object_data_ref.get("crop_rect")
        if current_rect != new_crop_rect:
            editor_history.push_undo_state(self.editor_state); self.current_object_data_ref["crop_rect"] = new_crop_rect
            self.properties_changed.emit(self.current_object_data_ref); logger.debug(f"Crop rect changed to: {new_crop_rect}")

    def _on_reset_crop(self):
        if not self.current_object_data_ref: return
        if self.current_object_data_ref.get("crop_rect") is not None:
            editor_history.push_undo_state(self.editor_state); self.current_object_data_ref["crop_rect"] = None
            original_w = self.current_object_data_ref.get("original_width", 0); original_h = self.current_object_data_ref.get("original_height", 0)
            cx_spin = self.input_widgets.get("crop_x"); cy_spin = self.input_widgets.get("crop_y")
            cw_spin = self.input_widgets.get("crop_width"); ch_spin = self.input_widgets.get("crop_height")
            if isinstance(cx_spin, QSpinBox): cx_spin.setValue(0)
            if isinstance(cy_spin, QSpinBox): cy_spin.setValue(0)
            if isinstance(cw_spin, QSpinBox): cw_spin.setValue(original_w)
            if isinstance(ch_spin, QSpinBox): ch_spin.setValue(original_h)
            self.properties_changed.emit(self.current_object_data_ref); logger.debug("Crop rect reset to None (full image).")

    def _on_dimension_changed(self, dimension_key: str, new_value: int):
        if not self.current_object_data_ref: return
        if self.current_object_data_ref.get(dimension_key) != new_value:
            editor_history.push_undo_state(self.editor_state) 
            self.current_object_data_ref[dimension_key] = new_value
            self.properties_changed.emit(self.current_object_data_ref)

    def _update_rgba_color_button_style(self, button: QPushButton, color_tuple_rgba: Tuple[int,int,int,int]):
        if not color_tuple_rgba or len(color_tuple_rgba) != 4: button.setText("Invalid Color"); button.setIcon(QIcon()); return
        button.setText(f"RGBA: {color_tuple_rgba}"); q_color = QColor(*color_tuple_rgba)
        btn_width = max(60, button.width()); btn_height = max(20, button.height())
        pm = QPixmap(btn_width, btn_height); pm.fill(Qt.GlobalColor.transparent); checker_painter = QPainter(pm)
        checker_size = 8
        for y_coord in range(0, pm.height(), checker_size):
            for x_coord in range(0, pm.width(), checker_size):
                if (x_coord // checker_size + y_coord // checker_size) % 2 == 0: checker_painter.fillRect(x_coord, y_coord, checker_size, checker_size, QColor(200,200,200))
                else: checker_painter.fillRect(x_coord, y_coord, checker_size, checker_size, QColor(230,230,230))
        checker_painter.fillRect(pm.rect(), q_color); checker_painter.end()
        button.setIcon(QIcon(pm)); button.setIconSize(QSize(btn_width - 8, btn_height - 8 ))
        luma = 0.299 * color_tuple_rgba[0] + 0.587 * color_tuple_rgba[1] + 0.114 * color_tuple_rgba[2]
        alpha = color_tuple_rgba[3]; text_q_color = QColor(Qt.GlobalColor.black)
        if alpha > 128 and luma < 128 : text_q_color = QColor(Qt.GlobalColor.white)
        button.setStyleSheet(f"QPushButton {{ color: {text_q_color.name()}; text-align: left; padding-left: 5px; }}")


    def _change_rgba_color_property(self, var_name: str, button_ref: QPushButton):
        if not self.current_object_data_ref: return
        props = self.current_object_data_ref.get("properties", {}); current_color_val = props.get(var_name, (0,0,0,255))
        dialog = QColorDialog(self); dialog.setOption(QColorDialog.ColorDialogOption.ShowAlphaChannel, True); dialog.setCurrentColor(QColor(*current_color_val))
        if dialog.exec():
            new_q_color = dialog.selectedColor(); new_color_tuple_rgba = new_q_color.getRgb()
            if props.get(var_name) != new_color_tuple_rgba: 
                editor_history.push_undo_state(self.editor_state); props[var_name] = new_color_tuple_rgba 
                self._update_rgba_color_button_style(button_ref, new_color_tuple_rgba) 
                self.properties_changed.emit(self.current_object_data_ref)


    def _browse_for_trigger_image(self, var_name: str):
        if not self.current_object_data_ref: return
        self.upload_image_for_trigger_requested.emit(self.current_object_data_ref)

    def _clear_trigger_image(self, var_name: str):
        if not self.current_object_data_ref: return
        props = self.current_object_data_ref.get("properties", {})
        if props.get(var_name, "") != "":
            editor_history.push_undo_state(self.editor_state); props[var_name] = ""
            self.update_property_field_value(self.current_object_data_ref, var_name, "")
            self.properties_changed.emit(self.current_object_data_ref)

    def update_property_field_value(self, obj_data_ref: Dict[str, Any], prop_name: str, new_value: Any):
        if self.current_object_data_ref is not obj_data_ref: logger.warning(f"PropsEditor: update_prop_field_value for non-current object. Ignoring for '{prop_name}'."); return
        widget_key_for_lineedit = f"{prop_name}_lineedit"; slider_widget = self.input_widgets.get(prop_name + "_slider_widget"); spinbox_widget = self.input_widgets.get(prop_name + "_spinbox_widget")
        widget = self.input_widgets.get(prop_name) 
        if not widget: widget = self.input_widgets.get(widget_key_for_lineedit)
        if isinstance(slider_widget, QSlider) and isinstance(spinbox_widget, QSpinBox) and prop_name == "corner_radius":
            try: int_val = int(new_value); slider_widget.setValue(int_val); spinbox_widget.setValue(int_val)
            except (ValueError, TypeError): pass
        elif isinstance(widget, QLineEdit): widget.setText(str(new_value))
        elif isinstance(widget, QSpinBox): 
            try: widget.setValue(int(new_value)) 
            except (ValueError, TypeError): pass
        elif isinstance(widget, QDoubleSpinBox): 
            try: widget.setValue(float(new_value)) 
            except (ValueError, TypeError): pass
        elif isinstance(widget, QCheckBox): 
            try: widget.setChecked(bool(new_value)) 
            except (ValueError, TypeError): pass
        elif isinstance(widget, QComboBox): widget.setCurrentText(str(new_value))
        elif isinstance(widget, QPushButton) and prop_name.endswith("_color_rgba"):
             if isinstance(new_value, (tuple, list)) and len(new_value) == 4: self._update_rgba_color_button_style(widget, new_value) # type: ignore
        if logger: logger.debug(f"PropertiesEditor: Externally updated field '{prop_name}' to '{new_value}'")

    def _on_line_edit_finished(self, var_name: str, text_value: str):
        self._on_property_value_changed(var_name, text_value)

    def _on_property_value_changed(self, var_name: str, new_value: Any):
        if not self.current_object_data_ref: return
        target_dict_for_prop = self.current_object_data_ref; is_sub_property = False 
        if var_name in ["layer_order", "current_width", "current_height", "is_flipped_h", "rotation"]: target_dict_for_prop = self.current_object_data_ref; is_sub_property = False
        else: 
            if "properties" not in self.current_object_data_ref or not isinstance(self.current_object_data_ref.get("properties"), dict): self.current_object_data_ref["properties"] = {}
            target_dict_for_prop = self.current_object_data_ref["properties"]; is_sub_property = True
        game_type_id = str(self.current_object_data_ref.get("game_type_id")); definition: Optional[Dict] = None
        if var_name == "layer_order": definition = {"type": "int", "default": 0}
        elif var_name == "current_width": definition = {"type": "int", "default": ED_CONFIG.BASE_GRID_SIZE}
        elif var_name == "current_height": definition = {"type": "int", "default": ED_CONFIG.BASE_GRID_SIZE}
        elif var_name == "is_flipped_h": definition = {"type": "bool", "default": False}
        elif var_name == "rotation": definition = {"type": "int", "default": 0, "step":90} 
        else: 
            if game_type_id in ED_CONFIG.EDITABLE_ASSET_VARIABLES: definition = ED_CONFIG.EDITABLE_ASSET_VARIABLES[game_type_id].get(var_name)
        if not definition:
            if logger: logger.warning(f"No definition for prop '{var_name}' (GameID: '{game_type_id}'). Cannot process change.")
            return
        prop_type = definition["type"]; current_stored_value = target_dict_for_prop.get(var_name, definition["default"]); typed_new_value = new_value
        try:
            if prop_type == "int" or prop_type == "slider": typed_new_value = int(new_value)
            elif prop_type == "float": typed_new_value = float(new_value)
            elif prop_type == "bool": typed_new_value = bool(new_value)
            elif prop_type == "str": typed_new_value = str(new_value)
            elif prop_type == "tuple_color_rgba":
                if not (isinstance(new_value, (list, tuple)) and len(new_value) == 4): raise ValueError("Invalid RGBA tuple")
            elif prop_type == "image_path_custom": typed_new_value = str(new_value)
        except (ValueError, TypeError) as e:
            if logger: logger.warning(f"Casting error for '{var_name}': '{new_value}' to {prop_type}. Error: {e}")
            widget_to_revert = self.input_widgets.get(var_name)
            if prop_type == "slider": 
                slider_w = self.input_widgets.get(var_name + "_slider_widget"); spinbox_w = self.input_widgets.get(var_name + "_spinbox_widget")
                if isinstance(slider_w, QSlider): slider_w.setValue(int(current_stored_value))
                if isinstance(spinbox_w, QSpinBox): spinbox_w.setValue(int(current_stored_value))
            elif isinstance(widget_to_revert, QSpinBox): widget_to_revert.setValue(int(current_stored_value))
            elif isinstance(widget_to_revert, QDoubleSpinBox): widget_to_revert.setValue(float(current_stored_value))
            elif isinstance(widget_to_revert, QLineEdit): widget_to_revert.setText(str(current_stored_value))
            elif isinstance(widget_to_revert, QCheckBox): widget_to_revert.setChecked(bool(current_stored_value))
            return
        if current_stored_value != typed_new_value:
            editor_history.push_undo_state(self.editor_state); target_dict_for_prop[var_name] = typed_new_value
            if var_name == "corner_radius" and is_sub_property:
                props_dict = target_dict_for_prop; should_round_all = typed_new_value > 0 # type: ignore
                corner_bool_props = ["round_top_left", "round_top_right", "round_bottom_left", "round_bottom_right"]
                for corner_prop_name in corner_bool_props:
                    if props_dict.get(corner_prop_name) != should_round_all:
                        props_dict[corner_prop_name] = should_round_all; checkbox_widget = self.input_widgets.get(corner_prop_name)
                        if isinstance(checkbox_widget, QCheckBox): checkbox_widget.blockSignals(True); checkbox_widget.setChecked(should_round_all); checkbox_widget.blockSignals(False)
            self.properties_changed.emit(self.current_object_data_ref)
            if logger: logger.debug(f"Property '{var_name}' changed to '{typed_new_value}'.")

    def _change_object_color(self, map_object_data_ref: Optional[Dict[str, Any]]):
        if not map_object_data_ref: return
        current_color_tuple = map_object_data_ref.get("override_color"); _sp = None
        if not current_color_tuple:
            asset_key = map_object_data_ref.get("asset_editor_key"); asset_palette_data = self.editor_state.assets_palette.get(str(asset_key))
            if asset_palette_data:
                current_color_tuple = asset_palette_data.get("base_color_tuple")
                if not current_color_tuple: _sp = asset_palette_data.get("surface_params")
                if _sp and isinstance(_sp, tuple) and len(_sp) == 3: current_color_tuple = _sp[2] # type: ignore
            if not current_color_tuple: current_color_tuple = (128,128,128)
        q_current_color = QColor(*current_color_tuple) # type: ignore
        new_q_color = QColorDialog.getColor(q_current_color, self, "Select Object Color")
        if new_q_color.isValid():
            new_color_tuple = new_q_color.getRgb()[:3]
            if map_object_data_ref.get("override_color") != new_color_tuple:
                editor_history.push_undo_state(self.editor_state); map_object_data_ref["override_color"] = new_color_tuple
                self.properties_changed.emit(map_object_data_ref); color_button = self.input_widgets.get("_color_button")
                if isinstance(color_button, QPushButton): self._update_color_button_visuals(color_button, map_object_data_ref)
    
    # --- Controller Navigation Methods ---
    def _update_focused_property_visuals(self):
        for var_name, widget_container, label_widget in self._controller_property_widgets_ordered:
            widget_to_style = widget_container
            if isinstance(widget_container, QWidget) and widget_container.layout() is not None:
                le = widget_container.findChild(QLineEdit); cb = widget_container.findChild(QComboBox); sb = widget_container.findChild(QSpinBox); dsb = widget_container.findChild(QDoubleSpinBox); sl = widget_container.findChild(QSlider)
                if le: widget_to_style = le; 
                elif cb: widget_to_style = cb; 
                elif sb: widget_to_style = sb; 
                elif dsb: widget_to_style = dsb; 
                elif sl: widget_to_style = sl
            if isinstance(widget_to_style, QWidget) and not isinstance(widget_to_style, QLabel): widget_to_style.setStyleSheet("")
            if label_widget: label_widget.setStyleSheet("")
            if widget_container is self.input_widgets.get("_color_button"): self._update_color_button_visuals(widget_container, self.current_object_data_ref)
            elif self.current_object_data_ref and self.current_object_data_ref.get("properties"):
                definition = ED_CONFIG.EDITABLE_ASSET_VARIABLES.get(str(self.current_object_data_ref.get("game_type_id")), {}).get(var_name)
                if definition and definition.get("type") == "tuple_color_rgba":
                     props = self.current_object_data_ref.get("properties",{}); self._update_rgba_color_button_style(widget_container, props.get(var_name, definition["default"]))
        if self._controller_has_focus and self._controller_focused_property_index >= 0 and self._controller_focused_property_index < len(self._controller_property_widgets_ordered):
            var_name_focused, widget_container_focused, label_widget_focused = self._controller_property_widgets_ordered[self._controller_focused_property_index]
            focus_style_str = str(ED_CONFIG.PROPERTIES_EDITOR_CONTROLLER_FOCUS_BORDER)
            widget_to_style_focused = widget_container_focused
            if isinstance(widget_container_focused, QWidget) and widget_container_focused.layout() is not None:
                le = widget_container_focused.findChild(QLineEdit); cb = widget_container_focused.findChild(QComboBox); sb = widget_container_focused.findChild(QSpinBox); dsb = widget_container_focused.findChild(QDoubleSpinBox); sl = widget_container_focused.findChild(QSlider)
                if le: widget_to_style_focused = le; 
                elif cb: widget_to_style_focused = cb; 
                elif sb: widget_to_style_focused = sb; 
                elif dsb: widget_to_style_focused = dsb; 
                elif sl: widget_to_style_focused = sl
            is_color_btn_focused = (widget_container_focused is self.input_widgets.get("_color_button")); is_rgba_color_btn_focused = False; definition_type_focused = ""
            if self.current_object_data_ref:
                game_type_id_focused = self.current_object_data_ref.get("game_type_id", "")
                prop_def_focused = ED_CONFIG.EDITABLE_ASSET_VARIABLES.get(game_type_id_focused, {}).get(var_name_focused)
                if prop_def_focused: definition_type_focused = prop_def_focused.get("type", "")
                if definition_type_focused == "tuple_color_rgba": is_rgba_color_btn_focused = True
            if not is_color_btn_focused and not is_rgba_color_btn_focused and isinstance(widget_to_style_focused, QWidget) and not isinstance(widget_to_style_focused, (QLabel, QCheckBox)): widget_to_style_focused.setStyleSheet(f"border: {focus_style_str};")
            if label_widget_focused: label_widget_focused.setStyleSheet("QLabel { color: " + focus_style_str.split(' ')[-1] + "; font-weight: bold; }")
            if isinstance(widget_to_style_focused, QWidget) and not isinstance(widget_to_style_focused, QLabel):
                target_focus_widget = widget_to_style_focused
                if definition_type_focused == "slider":
                    slider_sub_widget = self.input_widgets.get(var_name_focused + "_slider_widget")
                    if slider_sub_widget: target_focus_widget = slider_sub_widget
                target_focus_widget.setFocus(Qt.FocusReason.OtherFocusReason); self.scroll_area.ensureWidgetVisible(target_focus_widget, 10, 10)

    def _set_controller_focused_property(self, index: int):
        if not self._controller_property_widgets_ordered: self._controller_focused_property_index = -1; return
        new_index = max(0, min(index, len(self._controller_property_widgets_ordered) - 1))
        if self._controller_focused_property_index == new_index and self._controller_has_focus: return
        self._controller_focused_property_index = new_index; self._update_focused_property_visuals()
        if logger: logger.debug(f"PropertiesEditor: Controller focus on property index {new_index}")

    def on_controller_focus_gained(self):
        self._controller_has_focus = True
        if self._controller_property_widgets_ordered: self._set_controller_focused_property(0)
        else: self._controller_focused_property_index = -1
        self._update_focused_property_visuals()
        if logger: logger.debug("PropertiesEditor: Controller focus gained.")

    def on_controller_focus_lost(self):
        self._controller_has_focus = False
        if self._controller_focused_property_index >= 0 and self._controller_focused_property_index < len(self._controller_property_widgets_ordered):
            var_name, widget_container, label_widget = self._controller_property_widgets_ordered[self._controller_focused_property_index]
            widget_to_style = widget_container
            if isinstance(widget_container, QWidget) and widget_container.layout() is not None:
                le = widget_container.findChild(QLineEdit); cb = widget_container.findChild(QComboBox); sb = widget_container.findChild(QSpinBox); dsb = widget_container.findChild(QDoubleSpinBox); sl = widget_container.findChild(QSlider)
                if le: widget_to_style = le; 
                elif cb: widget_to_style = cb; 
                elif sb: widget_to_style = sb; 
                elif dsb: widget_to_style = dsb; 
                elif sl: widget_to_style = sl
            if isinstance(widget_to_style, QWidget) and not isinstance(widget_to_style, QLabel): widget_to_style.setStyleSheet("")
            if label_widget: label_widget.setStyleSheet("")
            if widget_container is self.input_widgets.get("_color_button"): self._update_color_button_visuals(widget_container, self.current_object_data_ref)
            elif self.current_object_data_ref and self.current_object_data_ref.get("properties"):
                definition = ED_CONFIG.EDITABLE_ASSET_VARIABLES.get(str(self.current_object_data_ref.get("game_type_id")), {}).get(var_name)
                if definition and definition.get("type") == "tuple_color_rgba":
                     props = self.current_object_data_ref.get("properties",{}); self._update_rgba_color_button_style(widget_container, props.get(var_name, definition["default"]))
        self._controller_focused_property_index = -1
        if logger: logger.debug("PropertiesEditor: Controller focus lost.")

    def handle_controller_action(self, action: str, value: Any):
        if not self._controller_has_focus or not self._controller_property_widgets_ordered:
            if action == ACTION_UI_TAB_NEXT or action == ACTION_UI_TAB_PREV: self.controller_focus_requested_elsewhere.emit()
            return
        current_idx = self._controller_focused_property_index
        if not (0 <= current_idx < len(self._controller_property_widgets_ordered)):
            if self._controller_property_widgets_ordered: self._set_controller_focused_property(0)
            return
        var_name, widget_container, _ = self._controller_property_widgets_ordered[current_idx]; widget_to_act_on = widget_container
        prop_def = None
        if self.current_object_data_ref:
            game_type_id = self.current_object_data_ref.get("game_type_id", "")
            if var_name not in ["layer_order", "current_width", "current_height", "is_flipped_h", "rotation"]:
                prop_def = ED_CONFIG.EDITABLE_ASSET_VARIABLES.get(game_type_id, {}).get(var_name)
            elif var_name == "corner_radius": prop_def = ED_CONFIG.EDITABLE_ASSET_VARIABLES.get(game_type_id, {}).get(var_name)
        if prop_def and prop_def.get("type") == "slider":
             slider_w = self.input_widgets.get(var_name + "_slider_widget")
             if isinstance(slider_w, QSlider): widget_to_act_on = slider_w
        elif isinstance(widget_container, QWidget) and widget_container.layout() is not None:
             le = widget_container.findChild(QLineEdit); cb = widget_container.findChild(QComboBox)
             if le: widget_to_act_on = le; 
             elif cb: widget_to_act_on = cb
        
        new_combo_idx: int # Define new_combo_idx here for broader scope if needed

        if action == ACTION_UI_UP: self._set_controller_focused_property(current_idx - 1)
        elif action == ACTION_UI_DOWN: self._set_controller_focused_property(current_idx + 1)
        elif action == ACTION_UI_ACCEPT:
            if isinstance(widget_to_act_on, QPushButton): widget_to_act_on.click()
            elif isinstance(widget_to_act_on, QCheckBox): widget_to_act_on.toggle()
            elif isinstance(widget_to_act_on, QComboBox): widget_to_act_on.showPopup()
            elif isinstance(widget_to_act_on, QWidget) and widget_to_act_on.layout() is not None:
                 if var_name == "linked_map_name" or (prop_def and prop_def.get("type") == "image_path_custom"):
                     browse_button = None
                     for child_widget in widget_to_act_on.findChildren(QPushButton):
                         if child_widget.text() == "..." or child_widget.text() == "Browse...": browse_button = child_widget; break
                     if browse_button: browse_button.click()
                 else: children_buttons = widget_to_act_on.findChildren(QPushButton);
                 if children_buttons: children_buttons[0].click()
        elif action == ACTION_UI_LEFT or action == ACTION_UI_RIGHT:
            step = 1 if action == ACTION_UI_RIGHT else -1
            if isinstance(widget_to_act_on, QSpinBox):
                new_val = widget_to_act_on.value() + step * widget_to_act_on.singleStep()
                if new_val >= widget_to_act_on.minimum() and new_val <= widget_to_act_on.maximum(): widget_to_act_on.setValue(new_val)
            elif isinstance(widget_to_act_on, QDoubleSpinBox):
                new_val = widget_to_act_on.value() + step * widget_to_act_on.singleStep()
                if new_val >= widget_to_act_on.minimum() and new_val <= widget_to_act_on.maximum(): widget_to_act_on.setValue(new_val)
            elif isinstance(widget_to_act_on, QComboBox):
                new_combo_idx = widget_to_act_on.currentIndex() + step # now defined before use
                if 0 <= new_combo_idx < widget_to_act_on.count(): widget_to_act_on.setCurrentIndex(new_combo_idx)
            elif isinstance(widget_to_act_on, QSlider): widget_to_act_on.setValue(widget_to_act_on.value() + step * widget_to_act_on.singleStep())
        elif action == ACTION_UI_TAB_NEXT or action == ACTION_UI_TAB_PREV: self.controller_focus_requested_elsewhere.emit()