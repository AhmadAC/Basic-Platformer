#################### START OF FILE: editor_selection_pane.py ####################

# editor/editor_selection_pane.py
# -*- coding: utf-8 -*-
"""
Selection Pane Widget for the Platformer Level Editor.
Allows viewing and selecting map objects from a list.
Includes icons for hiding/locking objects.
"""
import logging
from typing import Optional, TYPE_CHECKING, List, Dict, Any

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QListWidget, QListWidgetItem, QPushButton, QHBoxLayout,
    QAbstractItemView, QLineEdit, QLabel, QSizePolicy
)
from PySide6.QtGui import QIcon, QPixmap, QPainter, QPen, QColor, QBrush, QCursor
from PySide6.QtCore import Qt, Signal, Slot, QSize, QRectF, QPointF


if TYPE_CHECKING:
    from .editor_state import EditorState
    # from .map_view_widget import StandardMapObjectItem, BaseResizableMapItem # Not directly used here

# Import ED_CONFIG correctly, handling standalone execution for testing
try:
    from . import editor_config as ED_CONFIG
except ImportError:
    # Fallback for standalone execution or if editor_config is not found in the package
    # This should ideally be a more robust mechanism or avoided if possible
    # by running the module as part of the package.
    class ED_CONFIG_FALLBACK:
        CUSTOM_ASSET_PALETTE_PREFIX = "custom:"
        TRIGGER_SQUARE_ASSET_KEY = "trigger_square"
        WALL_BASE_KEY = "platform_wall_gray" # For potential filtering if ever re-added
    ED_CONFIG = ED_CONFIG_FALLBACK()
    print("WARNING: editor_selection_pane.py using fallback ED_CONFIG.")


logger = logging.getLogger(__name__)

ICON_SIZE = 16

def _create_icon(icon_type: str, size: int = ICON_SIZE) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    
    pen_color = QColor(70, 70, 70) 
    painter.setPen(QPen(pen_color, 1.5)) 

    eye_center_y = size / 2
    eye_height = size * 0.45
    eye_width = size * 0.8
    eye_rect = QRectF((size - eye_width) / 2, eye_center_y - eye_height / 2, eye_width, eye_height)

    if icon_type == "visible":
        painter.drawArc(eye_rect, 0 * 16, 360 * 16) 
        pupil_radius = size / 6
        painter.setBrush(pen_color)
        painter.drawEllipse(QPointF(size / 2, eye_center_y), pupil_radius, pupil_radius)
    elif icon_type == "hidden":
        painter.drawArc(eye_rect, 0 * 16, 360 * 16) 
        pupil_radius = size / 6
        painter.setBrush(pen_color)
        painter.drawEllipse(QPointF(size / 2, eye_center_y), pupil_radius, pupil_radius)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(200, 50, 50), 1.8)) 
        painter.drawLine(QPointF(size * 0.15, size * 0.15), QPointF(size * 0.85, size * 0.85))
    elif icon_type == "unlocked":
        body_width = size * 0.55; body_height = size * 0.45
        body_x = (size - body_width) / 2; body_y = size * 0.5
        body_rect = QRectF(body_x, body_y, body_width, body_height)
        painter.setBrush(QColor(220,220,220)); painter.drawRect(body_rect)
        shackle_width = size * 0.35; shackle_height = size * 0.35
        shackle_x = (size - shackle_width) / 2; shackle_y = size * 0.15 
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawArc(QRectF(shackle_x, shackle_y, shackle_width, shackle_height), 0 * 16, 180 * 16)
        painter.drawLine(QPointF(shackle_x, shackle_y + shackle_height/2), QPointF(shackle_x, body_y)) 
        painter.drawLine(QPointF(shackle_x + shackle_width, shackle_y + shackle_height/2), QPointF(shackle_x + shackle_width + size*0.05, body_y - size*0.1))
    elif icon_type == "locked":
        body_width = size * 0.55; body_height = size * 0.45
        body_x = (size - body_width) / 2; body_y = size * 0.5
        body_rect = QRectF(body_x, body_y, body_width, body_height)
        painter.setBrush(QColor(180,180,180)); painter.drawRect(body_rect)
        shackle_width = size * 0.35; shackle_height = size * 0.35
        shackle_x = (size - shackle_width) / 2; shackle_y = size * 0.15 
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawArc(QRectF(shackle_x, shackle_y, shackle_width, shackle_height), 0 * 16, 180 * 16)
        painter.drawLine(QPointF(shackle_x, shackle_y + shackle_height/2), QPointF(shackle_x, body_y))
        painter.drawLine(QPointF(shackle_x + shackle_width, shackle_y + shackle_height/2), QPointF(shackle_x + shackle_width, body_y))

    painter.end()
    return QIcon(pixmap)


class ObjectListItemWidget(QWidget):
    visibility_button_clicked = Signal()
    lock_button_clicked = Signal()

    def __init__(self, text: str, is_hidden: bool, is_locked: bool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(3, 1, 3, 1) 
        layout.setSpacing(2)

        self.name_label = QLabel(text)
        self.name_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(self.name_label)

        self.hide_button = QPushButton()
        self.hide_button.setFlat(True)
        self.hide_button.setFixedSize(ICON_SIZE + 4, ICON_SIZE + 4) 
        self.hide_button.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        self.hide_button.setIcon(_create_icon("hidden" if is_hidden else "visible"))
        self.hide_button.setToolTip("Toggle Visibility")
        self.hide_button.clicked.connect(self.visibility_button_clicked) # Emits internal signal
        layout.addWidget(self.hide_button)

        self.lock_button = QPushButton()
        self.lock_button.setFlat(True)
        self.lock_button.setFixedSize(ICON_SIZE + 4, ICON_SIZE + 4)
        self.lock_button.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        self.lock_button.setIcon(_create_icon("locked" if is_locked else "unlocked"))
        self.lock_button.setToolTip("Toggle Lock")
        self.lock_button.clicked.connect(self.lock_button_clicked) # Emits internal signal
        layout.addWidget(self.lock_button)
        self.setLayout(layout)

    def update_icons(self, is_hidden: bool, is_locked: bool):
        self.hide_button.setIcon(_create_icon("hidden" if is_hidden else "visible"))
        self.lock_button.setIcon(_create_icon("locked" if is_locked else "unlocked"))

    def set_text(self, text: str):
        self.name_label.setText(text)


class SelectionPaneWidget(QWidget):
    select_map_object_via_pane_requested = Signal(object) 
    item_visibility_toggled_in_pane = Signal(object, bool) 
    item_lock_toggled_in_pane = Signal(object, bool)     
    
    rename_item_requested = Signal(object, str) 

    def __init__(self, editor_state: 'EditorState', parent_main_window: Optional[QWidget] = None):
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
        # self.item_list_widget.itemActivated.connect(self._on_list_item_activated) # Double click for rename?
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

            list_item = QListWidgetItem(self.item_list_widget)
            list_item.setData(Qt.ItemDataRole.UserRole, obj_data)

            is_hidden = obj_data.get("editor_hidden", False)
            is_locked = obj_data.get("editor_locked", False)

            item_widget = ObjectListItemWidget(display_name, is_hidden, is_locked)
            
            # Connect button signals directly to the pane's handlers
            item_widget.visibility_button_clicked.connect(
                lambda obj=obj_data, btn_widget=item_widget: self._on_item_widget_visibility_toggle(obj, btn_widget)
            )
            item_widget.lock_button_clicked.connect(
                lambda obj=obj_data, btn_widget=item_widget: self._on_item_widget_lock_toggle(obj, btn_widget)
            )
            
            list_item.setSizeHint(item_widget.sizeHint())
            self.item_list_widget.addItem(list_item)
            self.item_list_widget.setItemWidget(list_item, item_widget)

            if current_selected_obj_data_ref is obj_data:
                list_item.setSelected(True)

        self.item_list_widget.blockSignals(False)
        if self.item_list_widget.selectedItems(): 
            self.item_list_widget.scrollToItem(self.item_list_widget.selectedItems()[0], QAbstractItemView.ScrollHint.EnsureVisible)

    # NEW methods to handle clicks from item widgets
    def _on_item_widget_visibility_toggle(self, obj_data_ref: Dict[str, Any], item_widget_ref: ObjectListItemWidget):
        current_is_hidden_state = obj_data_ref.get("editor_hidden", False)
        new_intended_visible_state = not current_is_hidden_state # This means if it's hidden, we want it visible
        
        logger.debug(f"SelectionPane: Visibility button clicked for '{obj_data_ref.get('asset_editor_key')}'. Current hidden: {current_is_hidden_state}. Emitting new visible: {new_intended_visible_state}")
        self.item_visibility_toggled_in_pane.emit(obj_data_ref, new_intended_visible_state)
        # The main window will update the data and call populate_items, which will refresh the icon.

    def _on_item_widget_lock_toggle(self, obj_data_ref: Dict[str, Any], item_widget_ref: ObjectListItemWidget):
        current_is_locked_state = obj_data_ref.get("editor_locked", False)
        logger.debug(f"SelectionPane: Lock button clicked for '{obj_data_ref.get('asset_editor_key')}'. Current locked: {current_is_locked_state}. Emitting new lock: {not current_is_locked_state}")
        self.item_lock_toggled_in_pane.emit(obj_data_ref, not current_is_locked_state)


    @Slot(str)
    def filter_items(self, text: str):
        self.populate_items() 

    @Slot(QListWidgetItem)
    def _on_list_item_clicked(self, list_widget_item: QListWidgetItem):
        # This slot is for when the QListWidgetItem itself is clicked (e.g., its label area)
        # not the buttons within its custom widget.
        
        # Check if the click actually happened on one of the buttons inside the widget.
        # If so, the button's own clicked signal should have handled it.
        item_widget = self.item_list_widget.itemWidget(list_widget_item)
        if isinstance(item_widget, ObjectListItemWidget):
            mouse_pos_relative_to_item_widget = item_widget.mapFromGlobal(self.item_list_widget.viewport().mapToGlobal(self.item_list_widget.mapFromGlobal(QCursor.pos())))
            
            hide_button_rect = item_widget.hide_button.geometry()
            lock_button_rect = item_widget.lock_button.geometry()

            if hide_button_rect.contains(mouse_pos_relative_to_item_widget) or \
               lock_button_rect.contains(mouse_pos_relative_to_item_widget):
                logger.debug("SelectionPane: Click was on an action button, _on_list_item_clicked ignoring.")
                return # Let button's specific handler do its job

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
            from .editor_actions import ACTION_UI_UP, ACTION_UI_DOWN, ACTION_UI_ACCEPT, ACTION_UI_TAB_NEXT, ACTION_UI_TAB_PREV
        except ImportError: # Fallback for standalone testing if needed
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
                self._on_list_item_clicked(current_item) # Simulate a click on the item itself
        elif action == ACTION_UI_TAB_NEXT: 
            if self.item_list_widget.hasFocus():
                self.search_box.setFocus()
        elif action == ACTION_UI_TAB_PREV: 
            if self.item_list_widget.hasFocus():
                 self.search_box.setFocus()

#################### END OF FILE: editor_selection_pane.py ####################