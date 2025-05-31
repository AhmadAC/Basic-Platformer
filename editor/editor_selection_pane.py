# editor/editor_selection_pane.py
# -*- coding: utf-8 -*-
"""
Selection Pane Widget for the Platformer Level Editor.
Allows viewing and selecting map objects from a list.
Includes icons for hiding/locking objects.
MODIFIED: Eyeball icon now toggles asset opacity (0% vs. last visible/100%).
MODIFIED: Boundary walls (is_boundary=True) are not shown in the list.
"""
import logging
import os
from typing import Optional, TYPE_CHECKING, List, Dict, Any

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QListWidget, QListWidgetItem, QPushButton, QHBoxLayout,
    QAbstractItemView, QLineEdit, QLabel, QSizePolicy
)
from PySide6.QtGui import QIcon, QPixmap, QPainter, QPen, QColor, QBrush, QCursor
from PySide6.QtCore import Qt, Signal, Slot, QSize, QRectF, QPointF


if TYPE_CHECKING:
    from editor.editor_state import EditorState
    from editor.editor_main_window import EditorMainWindow

# Import ED_CONFIG correctly, handling standalone execution for testing
try:
    from editor import editor_config as ED_CONFIG
    from editor import editor_history # For undo/redo
except ImportError:
    # Fallback for standalone execution or if editor_config is not found in the package
    class ED_CONFIG_FALLBACK: #type: ignore
        CUSTOM_ASSET_PALETTE_PREFIX = "custom:"
        TRIGGER_SQUARE_ASSET_KEY = "trigger_square"
        WALL_BASE_KEY = "platform_wall_gray" # For potential filtering if ever re-added
    class editor_history_FALLBACK: #type: ignore
        @staticmethod
        def push_undo_state(state): pass # type: ignore
    ED_CONFIG = ED_CONFIG_FALLBACK() #type: ignore
    editor_history = editor_history_FALLBACK() #type: ignore
    print("WARNING: editor_selection_pane.py using fallback ED_CONFIG and editor_history.")


logger = logging.getLogger(__name__)

ICON_SIZE = 16

def _create_icon(icon_type: str, size: int = ICON_SIZE) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    
    pen_color = QColor(70, 70, 70) 
    painter.setPen(QPen(pen_color, 1.5)) 

    eye_center_y = size / 2.0
    eye_height = size * 0.45
    eye_width = size * 0.8
    eye_rect = QRectF((size - eye_width) / 2.0, eye_center_y - eye_height / 2.0, eye_width, eye_height)

    if icon_type == "visible": # Normal eye (opacity > 0)
        painter.drawArc(eye_rect, 0 * 16, 360 * 16) 
        pupil_radius = size / 6.0
        painter.setBrush(pen_color)
        painter.drawEllipse(QPointF(size / 2.0, eye_center_y), pupil_radius, pupil_radius)
    elif icon_type == "hidden": # Crossed-out eye (opacity == 0)
        painter.drawArc(eye_rect, 0 * 16, 360 * 16)
        # Pupil still visible but dimmer or smaller if desired
        # pupil_radius = size / 7.0 
        # painter.setBrush(QColor(100,100,100)) # Dimmer pupil
        # painter.drawEllipse(QPointF(size / 2.0, eye_center_y), pupil_radius, pupil_radius)

        # Draw a thicker cross line
        cross_line_pen = QPen(QColor(200, 50, 50), 2.0) # Red cross
        cross_line_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(cross_line_pen)
        # Single diagonal line for "hidden" / "opacity 0"
        painter.drawLine(QPointF(size * 0.2, size * 0.8), QPointF(size * 0.8, size * 0.2))
    elif icon_type == "unlocked":
        body_width = size * 0.55; body_height = size * 0.45
        body_x = (size - body_width) / 2.0; body_y = size * 0.5
        body_rect = QRectF(body_x, body_y, body_width, body_height)
        painter.setBrush(QColor(220,220,220)); painter.drawRect(body_rect)
        shackle_width = size * 0.35; shackle_height = size * 0.35
        shackle_x = (size - shackle_width) / 2.0; shackle_y = size * 0.15 
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawArc(QRectF(shackle_x, shackle_y, shackle_width, shackle_height), 0 * 16, 180 * 16)
        painter.drawLine(QPointF(shackle_x, shackle_y + shackle_height/2.0), QPointF(shackle_x, body_y)) 
        painter.drawLine(QPointF(shackle_x + shackle_width, shackle_y + shackle_height/2.0), QPointF(shackle_x + shackle_width + size*0.05, body_y - size*0.1))
    elif icon_type == "locked":
        body_width = size * 0.55; body_height = size * 0.45
        body_x = (size - body_width) / 2.0; body_y = size * 0.5
        body_rect = QRectF(body_x, body_y, body_width, body_height)
        painter.setBrush(QColor(180,180,180)); painter.drawRect(body_rect)
        shackle_width = size * 0.35; shackle_height = size * 0.35
        shackle_x = (size - shackle_width) / 2.0; shackle_y = size * 0.15 
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawArc(QRectF(shackle_x, shackle_y, shackle_width, shackle_height), 0 * 16, 180 * 16)
        painter.drawLine(QPointF(shackle_x, shackle_y + shackle_height/2.0), QPointF(shackle_x, body_y))
        painter.drawLine(QPointF(shackle_x + shackle_width, shackle_y + shackle_height/2.0), QPointF(shackle_x + shackle_width, body_y))

    painter.end()
    return QIcon(pixmap)


class ObjectListItemWidget(QWidget):
    opacity_toggle_button_clicked = Signal()
    lock_button_clicked = Signal()

    def __init__(self, text: str, opacity: int, is_locked: bool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(3, 1, 3, 1) 
        layout.setSpacing(2)

        self.name_label = QLabel(text)
        self.name_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(self.name_label)

        self.opacity_button = QPushButton()
        self.opacity_button.setFlat(True)
        self.opacity_button.setFixedSize(ICON_SIZE + 4, ICON_SIZE + 4) 
        self.opacity_button.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        self.opacity_button.setIcon(_create_icon("hidden" if opacity == 0 else "visible"))
        self.opacity_button.setToolTip("Toggle Opacity (Visible/Hidden)")
        self.opacity_button.clicked.connect(self.opacity_toggle_button_clicked)
        layout.addWidget(self.opacity_button)

        self.lock_button = QPushButton()
        self.lock_button.setFlat(True)
        self.lock_button.setFixedSize(ICON_SIZE + 4, ICON_SIZE + 4)
        self.lock_button.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        self.lock_button.setIcon(_create_icon("locked" if is_locked else "unlocked"))
        self.lock_button.setToolTip("Toggle Lock")
        self.lock_button.clicked.connect(self.lock_button_clicked)
        layout.addWidget(self.lock_button)
        self.setLayout(layout)

    def update_icons(self, opacity: int, is_locked: bool):
        self.opacity_button.setIcon(_create_icon("hidden" if opacity == 0 else "visible"))
        self.lock_button.setIcon(_create_icon("locked" if is_locked else "unlocked"))

    def set_text(self, text: str):
        self.name_label.setText(text)


class SelectionPaneWidget(QWidget):
    select_map_object_via_pane_requested = Signal(object) 
    item_opacity_toggled_in_pane = Signal(object, int) # obj_data_ref, NEW_TARGET_OPACITY
    item_lock_toggled_in_pane = Signal(object, bool)     
    
    rename_item_requested = Signal(object, str) 

    def __init__(self, editor_state: 'EditorState', parent_main_window: Optional['EditorMainWindow'] = None):
        super().__init__(parent_main_window)
        self.editor_state = editor_state
        self.parent_main_window = parent_main_window 

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(2,2,2,2)
        self.main_layout.setSpacing(3)

        filter_layout = QHBoxLayout()
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search objects (name/type)...")
        self.search_box.textChanged.connect(self.filter_items)
        filter_layout.addWidget(self.search_box)
        self.main_layout.addLayout(filter_layout)

        self.item_list_widget = QListWidget()
        self.item_list_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.item_list_widget.itemClicked.connect(self._on_list_item_clicked)
        self.main_layout.addWidget(self.item_list_widget)
        
        self.setObjectName("SelectionPaneWidget")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)


    def _get_display_name(self, obj_data: Dict[str, Any], index: int) -> str:
        name = obj_data.get("editor_name") 
        if name:
            return name

        asset_key = obj_data.get("asset_editor_key", f"UnknownObj_{index}")
        game_type_id = obj_data.get("game_type_id")

        if asset_key.startswith(ED_CONFIG.CUSTOM_ASSET_PALETTE_PREFIX): 
            filename = asset_key.split(ED_CONFIG.CUSTOM_ASSET_PALETTE_PREFIX,1)[1] 
            return f"Custom: {filename[:20]}{'...' if len(filename)>20 else ''}"
        elif asset_key == ED_CONFIG.TRIGGER_SQUARE_ASSET_KEY: 
             linked_map = obj_data.get("properties", {}).get("linked_map_name", "")
             return f"Trigger Sq.{f' -> {linked_map}' if linked_map else ''}"

        palette_asset_info = self.editor_state.assets_palette.get(asset_key)
        if palette_asset_info and palette_asset_info.get("name_in_palette"):
            name = palette_asset_info["name_in_palette"]
        elif game_type_id and game_type_id != asset_key:
            name = str(game_type_id).replace("_", " ").title()
        else:
            name = asset_key.replace("_", " ").title()
        return name


    @Slot()
    def populate_items(self):
        logger.debug("SelectionPane: Populating items.")
        self.item_list_widget.blockSignals(True) 
        
        current_selected_obj_data_ref: Optional[Any] = None
        if self.parent_main_window and hasattr(self.parent_main_window, 'map_view_widget'):
            map_view = self.parent_main_window.map_view_widget 
            selected_scene_items = map_view.map_scene.selectedItems()
            if len(selected_scene_items) == 1 and hasattr(selected_scene_items[0], 'map_object_data_ref'):
                current_selected_obj_data_ref = selected_scene_items[0].map_object_data_ref

        self.item_list_widget.clear()
        search_text = self.search_box.text().lower()

        sorted_objects = sorted(
            self.editor_state.placed_objects, 
            key=lambda obj: (-obj.get("layer_order", 0), self._get_display_name(obj, self.editor_state.placed_objects.index(obj)).lower())
        )

        for i, obj_data in enumerate(sorted_objects):
            asset_key_filter = obj_data.get("asset_editor_key")
            display_name = self._get_display_name(obj_data, i)

            if search_text and search_text not in display_name.lower():
                game_type = obj_data.get("game_type_id", "").lower()
                asset_key_lower = asset_key_filter.lower() if asset_key_filter else ""
                if search_text not in asset_key_lower and search_text not in game_type:
                    continue
            
            # Filter out boundary walls from the selection pane
            if asset_key_filter == ED_CONFIG.WALL_BASE_KEY: # Typically "platform_wall_gray"
                obj_properties = obj_data.get("properties", {})
                if obj_properties.get("is_boundary", False) is True:
                    logger.debug(f"SelectionPane: Skipping boundary wall object '{display_name}' (asset_key: {asset_key_filter}) from list.")
                    continue # Skip this object, don't add to selection pane

            list_item = QListWidgetItem(self.item_list_widget)
            list_item.setData(Qt.ItemDataRole.UserRole, obj_data)

            item_opacity = obj_data.get("properties", {}).get("opacity", 100)
            is_locked = obj_data.get("editor_locked", False)

            item_widget = ObjectListItemWidget(display_name, item_opacity, is_locked)
            
            item_widget.opacity_toggle_button_clicked.connect(
                lambda checked=False, obj=obj_data, widget_ref=item_widget: self._on_item_widget_opacity_toggle(obj, widget_ref)
            )
            item_widget.lock_button_clicked.connect(
                lambda checked=False, obj=obj_data, widget_ref=item_widget: self._on_item_widget_lock_toggle(obj, widget_ref)
            )
            
            list_item.setSizeHint(item_widget.sizeHint())
            self.item_list_widget.addItem(list_item)
            self.item_list_widget.setItemWidget(list_item, item_widget)

            if current_selected_obj_data_ref is obj_data:
                list_item.setSelected(True)

        self.item_list_widget.blockSignals(False)
        if self.item_list_widget.selectedItems(): 
            self.item_list_widget.scrollToItem(self.item_list_widget.selectedItems()[0], QAbstractItemView.ScrollHint.EnsureVisible)

    def _on_item_widget_opacity_toggle(self, obj_data_ref: Dict[str, Any], item_widget_ref: ObjectListItemWidget):
        props = obj_data_ref.setdefault('properties', {})
        current_opacity = props.get('opacity', 100)
        
        new_target_opacity: int
        if current_opacity == 0:
            last_visible = props.get('last_visible_opacity', 100)
            new_target_opacity = 100 if last_visible == 0 else last_visible 
        else:
            new_target_opacity = 0
        
        logger.debug(f"SelectionPane: Opacity button clicked for '{obj_data_ref.get('asset_editor_key')}'. Current: {current_opacity}, New Target: {new_target_opacity}")
        self.item_opacity_toggled_in_pane.emit(obj_data_ref, new_target_opacity)
        # The MainEditorWindow will handle data change, undo, and then call populate_items which updates the icon.

    def _on_item_widget_lock_toggle(self, obj_data_ref: Dict[str, Any], item_widget_ref: ObjectListItemWidget):
        current_is_locked_state = obj_data_ref.get("editor_locked", False)
        new_lock_state = not current_is_locked_state
        
        logger.debug(f"SelectionPane: Lock button clicked for '{obj_data_ref.get('asset_editor_key')}'. New lock state: {new_lock_state}")
        self.item_lock_toggled_in_pane.emit(obj_data_ref, new_lock_state)
        # MainEditorWindow handles data change, undo, and then calls populate_items.


    @Slot(str)
    def filter_items(self, text: str):
        self.populate_items() 

    @Slot(QListWidgetItem)
    def _on_list_item_clicked(self, list_widget_item: QListWidgetItem):
        item_widget = self.item_list_widget.itemWidget(list_widget_item)
        if isinstance(item_widget, ObjectListItemWidget):
            mouse_pos_relative_to_item_widget = item_widget.mapFromGlobal(self.item_list_widget.viewport().mapToGlobal(self.item_list_widget.mapFromGlobal(QCursor.pos())))
            
            opacity_button_rect = item_widget.opacity_button.geometry()
            lock_button_rect = item_widget.lock_button.geometry()

            if opacity_button_rect.contains(mouse_pos_relative_to_item_widget) or \
               lock_button_rect.contains(mouse_pos_relative_to_item_widget):
                logger.debug("SelectionPane: Click was on an action button, _on_list_item_clicked ignoring.")
                return

        obj_data_ref = list_widget_item.data(Qt.ItemDataRole.UserRole)
        if obj_data_ref:
            self.select_map_object_via_pane_requested.emit(obj_data_ref)
            custom_widget = self.item_list_widget.itemWidget(list_widget_item)
            log_name = "object"
            if isinstance(custom_widget, ObjectListItemWidget):
                log_name = custom_widget.name_label.text()
            logger.debug(f"SelectionPane: Item area clicked (not buttons), requesting map selection of: {log_name}")


    @Slot()
    def sync_selection_from_map(self):
        logger.debug("SelectionPane: Syncing selection from map.")
        self.item_list_widget.blockSignals(True) 

        selected_map_obj_data_ref: Optional[Any] = None
        if self.parent_main_window and hasattr(self.parent_main_window, 'map_view_widget'):
            map_view = self.parent_main_window.map_view_widget 
            selected_scene_items = map_view.map_scene.selectedItems()
            if len(selected_scene_items) == 1 and hasattr(selected_scene_items[0], 'map_object_data_ref'):
                 selected_map_obj_data_ref = selected_scene_items[0].map_object_data_ref
        
        found_and_selected = False
        for i in range(self.item_list_widget.count()):
            list_item = self.item_list_widget.item(i)
            obj_data_in_list = list_item.data(Qt.ItemDataRole.UserRole)
            if obj_data_in_list is selected_map_obj_data_ref:
                if not list_item.isSelected():
                    self.item_list_widget.setCurrentItem(list_item) 
                self.item_list_widget.scrollToItem(list_item, QAbstractItemView.ScrollHint.EnsureVisible)
                found_and_selected = True
                break 
        
        if not found_and_selected:
            self.item_list_widget.clearSelection()

        self.item_list_widget.blockSignals(False)


    def on_controller_focus_gained(self):
        logger.debug("SelectionPane: Controller focus gained.")
        self.item_list_widget.setFocus()
        if self.item_list_widget.count() > 0 and not self.item_list_widget.currentItem():
            self.item_list_widget.setCurrentRow(0)

    def on_controller_focus_lost(self):
        logger.debug("SelectionPane: Controller focus lost.")

    def handle_controller_action(self, action: str, value: Any):
        if not self.hasFocus() and not self.item_list_widget.hasFocus() and not self.search_box.hasFocus():
             return

        try:
            from editor.editor_actions import ACTION_UI_UP, ACTION_UI_DOWN, ACTION_UI_ACCEPT, ACTION_UI_TAB_NEXT, ACTION_UI_TAB_PREV
        except ImportError: 
            ACTION_UI_UP, ACTION_UI_DOWN, ACTION_UI_ACCEPT, ACTION_UI_TAB_NEXT, ACTION_UI_TAB_PREV = "UI_UP", "UI_DOWN", "UI_ACCEPT", "UI_TAB_NEXT", "UI_TAB_PREV"


        if self.search_box.hasFocus():
            if action == ACTION_UI_DOWN: 
                self.item_list_widget.setFocus()
                if self.item_list_widget.count() > 0 and not self.item_list_widget.currentItem():
                    self.item_list_widget.setCurrentRow(0)
            return 

        current_row = self.item_list_widget.currentRow()
        if action == ACTION_UI_UP: 
            if current_row > 0:
                self.item_list_widget.setCurrentRow(current_row - 1)
        elif action == ACTION_UI_DOWN: 
            if current_row < self.item_list_widget.count() - 1:
                self.item_list_widget.setCurrentRow(current_row + 1)
        elif action == ACTION_UI_ACCEPT: 
            current_item = self.item_list_widget.currentItem()
            if current_item:
                self._on_list_item_clicked(current_item) 
        elif action == ACTION_UI_TAB_NEXT: 
            if self.item_list_widget.hasFocus():
                self.search_box.setFocus()
        elif action == ACTION_UI_TAB_PREV: 
            if self.item_list_widget.hasFocus():
                 self.search_box.setFocus()