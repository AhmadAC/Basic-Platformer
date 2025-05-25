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
from PySide6.QtGui import QIcon, QPixmap, QPainter, QPen, QColor, QBrush, QAction 
from PySide6.QtCore import Qt, Signal, Slot, QSize, QRectF, QPointF


if TYPE_CHECKING:
    from .editor_state import EditorState
    from .map_view_widget import StandardMapObjectItem, BaseResizableMapItem 

logger = logging.getLogger(__name__)

ICON_SIZE = 16

def _create_icon(icon_type: str, size: int = ICON_SIZE) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    
    pen_color = QColor(70, 70, 70) # Slightly darker gray for better visibility
    painter.setPen(QPen(pen_color, 1.5)) # Thicker pen

    # Eye shape (common part for visible/hidden)
    eye_center_y = size / 2
    eye_height = size * 0.45
    eye_width = size * 0.8
    eye_rect = QRectF((size - eye_width) / 2, eye_center_y - eye_height / 2, eye_width, eye_height)

    if icon_type == "visible":
        painter.drawArc(eye_rect, 0 * 16, 360 * 16) # Full ellipse for open eye
        pupil_radius = size / 6
        painter.setBrush(pen_color)
        painter.drawEllipse(QPointF(size / 2, eye_center_y), pupil_radius, pupil_radius)
    elif icon_type == "hidden":
        painter.drawArc(eye_rect, 0 * 16, 360 * 16) # Full ellipse
        pupil_radius = size / 6
        painter.setBrush(pen_color)
        painter.drawEllipse(QPointF(size / 2, eye_center_y), pupil_radius, pupil_radius)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(200, 50, 50), 1.8)) # Red strike-through
        painter.drawLine(QPointF(size * 0.15, size * 0.15), QPointF(size * 0.85, size * 0.85))
    elif icon_type == "unlocked":
        body_width = size * 0.55
        body_height = size * 0.45
        body_x = (size - body_width) / 2
        body_y = size * 0.5
        body_rect = QRectF(body_x, body_y, body_width, body_height)
        painter.setBrush(QColor(220,220,220)) # Light gray body
        painter.drawRect(body_rect)

        shackle_width = size * 0.35
        shackle_height = size * 0.35 # Make shackle a bit taller relative to its width
        shackle_x = (size - shackle_width) / 2
        shackle_y = size * 0.15 # Move shackle up
        
        # Open shackle - one side detached
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawArc(QRectF(shackle_x, shackle_y, shackle_width, shackle_height), 0 * 16, 180 * 16)
        painter.drawLine(QPointF(shackle_x, shackle_y + shackle_height/2), QPointF(shackle_x, body_y)) # Left leg
        # Detached right leg
        painter.drawLine(QPointF(shackle_x + shackle_width, shackle_y + shackle_height/2), QPointF(shackle_x + shackle_width + size*0.05, body_y - size*0.1))


    elif icon_type == "locked":
        body_width = size * 0.55
        body_height = size * 0.45
        body_x = (size - body_width) / 2
        body_y = size * 0.5
        body_rect = QRectF(body_x, body_y, body_width, body_height)
        painter.setBrush(QColor(180,180,180)) # Darker gray body
        painter.drawRect(body_rect)

        shackle_width = size * 0.35
        shackle_height = size * 0.35
        shackle_x = (size - shackle_width) / 2
        shackle_y = size * 0.15 
        
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
        layout.setContentsMargins(3, 1, 3, 1) # Adjusted margins
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
        self.hide_button.clicked.connect(self.visibility_button_clicked)
        layout.addWidget(self.hide_button)

        self.lock_button = QPushButton()
        self.lock_button.setFlat(True)
        self.lock_button.setFixedSize(ICON_SIZE + 4, ICON_SIZE + 4)
        self.lock_button.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        self.lock_button.setIcon(_create_icon("locked" if is_locked else "unlocked"))
        self.lock_button.setToolTip("Toggle Lock")
        self.lock_button.clicked.connect(self.lock_button_clicked)
        layout.addWidget(self.lock_button)
        self.setLayout(layout)

    def update_icons(self, is_hidden: bool, is_locked: bool):
        self.hide_button.setIcon(_create_icon("hidden" if is_hidden else "visible"))
        self.lock_button.setIcon(_create_icon("locked" if is_locked else "unlocked"))

    def set_text(self, text: str):
        self.name_label.setText(text)


class SelectionPaneWidget(QWidget):
    select_map_object_via_pane_requested = Signal(object) 
    item_visibility_toggled_in_pane = Signal(object, bool) # obj_data_ref, new_visible_state
    item_lock_toggled_in_pane = Signal(object, bool)     # obj_data_ref, new_lock_state
    
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
        self.main_layout.addWidget(self.item_list_widget)
        
        self.setObjectName("SelectionPaneWidget")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)


    def _get_display_name(self, obj_data: Dict[str, Any], index: int) -> str:
        name = obj_data.get("editor_name") 
        if name:
            return name

        asset_key = obj_data.get("asset_editor_key", f"UnknownObj_{index}")
        game_type_id = obj_data.get("game_type_id")

        if asset_key.startswith(ED_CONFIG.CUSTOM_ASSET_PALETTE_PREFIX): # type: ignore
            filename = asset_key.split(ED_CONFIG.CUSTOM_ASSET_PALETTE_PREFIX,1)[1] # type: ignore
            return f"Custom: {filename[:20]}{'...' if len(filename)>20 else ''}"
        elif asset_key == ED_CONFIG.TRIGGER_SQUARE_ASSET_KEY: # type: ignore
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
            map_view = self.parent_main_window.map_view_widget # type: ignore
            selected_scene_items = map_view.map_scene.selectedItems()
            if len(selected_scene_items) == 1 and hasattr(selected_scene_items[0], 'map_object_data_ref'):
                current_selected_obj_data_ref = selected_scene_items[0].map_object_data_ref

        self.item_list_widget.clear()
        search_text = self.search_box.text().lower()

        # Sort objects by layer_order (descending so higher Z is at top), then by internal name or index
        sorted_objects = sorted(
            self.editor_state.placed_objects, 
            key=lambda obj: (-obj.get("layer_order", 0), self._get_display_name(obj, self.editor_state.placed_objects.index(obj)).lower())
        )


        for i, obj_data in enumerate(sorted_objects): # Use sorted_objects
            asset_key_filter = obj_data.get("asset_editor_key")
            
            # *** MODIFICATION START: Filter out WALL_BASE_KEY from Selection Pane ***
            if asset_key_filter == ED_CONFIG.WALL_BASE_KEY: # type: ignore
                continue 
            # *** MODIFICATION END ***

            display_name = self._get_display_name(obj_data, i) # i here is just for fallback unknown name

            if search_text and search_text not in display_name.lower():
                game_type = obj_data.get("game_type_id", "").lower()
                asset_key_lower = asset_key_filter.lower() if asset_key_filter else ""
                if search_text not in asset_key_lower and search_text not in game_type:
                    continue

            list_item = QListWidgetItem(self.item_list_widget) # Parent is the list widget
            list_item.setData(Qt.ItemDataRole.UserRole, obj_data)

            is_hidden = obj_data.get("editor_hidden", False)
            is_locked = obj_data.get("editor_locked", False)

            item_widget = ObjectListItemWidget(display_name, is_hidden, is_locked)
            # Use lambdas to capture the specific obj_data for each button
            item_widget.visibility_button_clicked.connect(
                lambda obj=obj_data, hidden=is_hidden: self._handle_item_visibility_toggle(obj, hidden)
            )
            item_widget.lock_button_clicked.connect(
                lambda obj=obj_data, locked=is_locked: self._handle_item_lock_toggle(obj, locked)
            )
            
            list_item.setSizeHint(item_widget.sizeHint()) # Important for custom widgets
            self.item_list_widget.addItem(list_item) # Add the QListWidgetItem
            self.item_list_widget.setItemWidget(list_item, item_widget) # Set the custom widget

            if current_selected_obj_data_ref is obj_data:
                list_item.setSelected(True)
                # self.item_list_widget.scrollToItem(list_item, QAbstractItemView.ScrollHint.EnsureVisible)

        self.item_list_widget.blockSignals(False)
        if self.item_list_widget.selectedItems(): 
            self.item_list_widget.scrollToItem(self.item_list_widget.selectedItems()[0], QAbstractItemView.ScrollHint.EnsureVisible)


    @Slot(object, bool)
    def _handle_item_visibility_toggle(self, obj_data_ref: Dict[str, Any], current_is_hidden_state: bool):
        # The signal should indicate the *new* intended visibility state
        self.item_visibility_toggled_in_pane.emit(obj_data_ref, not current_is_hidden_state)

    @Slot(object, bool)
    def _handle_item_lock_toggle(self, obj_data_ref: Dict[str, Any], current_is_locked_state: bool):
        self.item_lock_toggled_in_pane.emit(obj_data_ref, not current_is_locked_state)


    @Slot(str)
    def filter_items(self, text: str):
        self.populate_items() 

    @Slot(QListWidgetItem)
    def _on_list_item_clicked(self, list_widget_item: QListWidgetItem):
        obj_data_ref = list_widget_item.data(Qt.ItemDataRole.UserRole)
        if obj_data_ref:
            self.select_map_object_via_pane_requested.emit(obj_data_ref)
            custom_widget = self.item_list_widget.itemWidget(list_widget_item)
            log_name = "object"
            if isinstance(custom_widget, ObjectListItemWidget):
                log_name = custom_widget.name_label.text()
            logger.debug(f"SelectionPane: Clicked, requesting map selection of: {log_name}")


    @Slot()
    def sync_selection_from_map(self):
        logger.debug("SelectionPane: Syncing selection from map.")
        self.item_list_widget.blockSignals(True) 

        selected_map_obj_data_ref: Optional[Any] = None
        if self.parent_main_window and hasattr(self.parent_main_window, 'map_view_widget'):
            map_view = self.parent_main_window.map_view_widget # type: ignore
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

        # Import actions if not already imported (e.g. for standalone testing)
        try:
            from .editor_actions import ACTION_UI_UP, ACTION_UI_DOWN, ACTION_UI_ACCEPT, ACTION_UI_TAB_NEXT, ACTION_UI_TAB_PREV # type: ignore
        except ImportError:
            ACTION_UI_UP = "UI_UP" # Fallback
            ACTION_UI_DOWN = "UI_DOWN"
            ACTION_UI_ACCEPT = "UI_ACCEPT"
            ACTION_UI_TAB_NEXT = "UI_TAB_NEXT"
            ACTION_UI_TAB_PREV = "UI_TAB_PREV"


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


if __name__ != "__main__":
    from . import editor_config as ED_CONFIG
else: 
    class ED_CONFIG_FALLBACK: # type: ignore
        CUSTOM_ASSET_PALETTE_PREFIX = "custom:"
        TRIGGER_SQUARE_ASSET_KEY = "trigger_square"
        WALL_BASE_KEY = "platform_wall_gray" # Important for filtering
    ED_CONFIG = ED_CONFIG_FALLBACK() # type: ignore

#################### END OF FILE: editor_selection_pane.py ####################