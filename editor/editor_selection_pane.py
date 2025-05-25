#################### START OF FILE: editor_selection_pane.py ####################
# editor/editor_selection_pane.py
# -*- coding: utf-8 -*-
"""
Selection Pane Widget for the Platformer Level Editor.
Allows viewing and selecting map objects from a list.
"""
import logging
from typing import Optional, TYPE_CHECKING, List, Dict, Any

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QListWidget, QListWidgetItem, QPushButton, QHBoxLayout,
    QAbstractItemView, QLineEdit, QLabel
)
from PySide6.QtGui import QIcon # For potential future icons next to items
from PySide6.QtCore import Qt, Signal, Slot, QItemSelectionModel


if TYPE_CHECKING:
    from .editor_state import EditorState
    # from .map_view_widget import StandardMapObjectItem, BaseResizableMapItem # For type hinting if needed

logger = logging.getLogger(__name__)

class SelectionPaneWidget(QWidget):
    """
    Widget for the Selection Pane, allowing users to see a list of all objects
    on the map and select them.
    """
    # Emits the object_data_ref of the item that should be selected in the map view
    select_map_object_via_pane_requested = Signal(object) 
    # Emits (object_data_ref, new_visibility_state)
    item_visibility_toggled_in_pane = Signal(object, bool) 
    # Emits (object_data_ref, new_lock_state)
    item_lock_toggled_in_pane = Signal(object, bool) 
    
    rename_item_requested = Signal(object, str) # object_data_ref, new_name

    def __init__(self, editor_state: 'EditorState', parent_main_window: Optional[QWidget] = None):
        super().__init__(parent_main_window)
        self.editor_state = editor_state
        self.parent_main_window = parent_main_window # Reference to EditorMainWindow

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(2,2,2,2)
        self.main_layout.setSpacing(3)

        # --- Filter/Search Area ---
        filter_layout = QHBoxLayout()
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search objects (name/type)...")
        self.search_box.textChanged.connect(self.filter_items)
        filter_layout.addWidget(self.search_box)
        self.main_layout.addLayout(filter_layout)

        # --- Item List ---
        self.item_list_widget = QListWidget()
        self.item_list_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.item_list_widget.itemClicked.connect(self._on_list_item_clicked)
        # self.item_list_widget.itemDoubleClicked.connect(self._on_list_item_double_clicked) # For renaming
        self.main_layout.addWidget(self.item_list_widget)

        # --- Action Buttons (Optional, can be expanded) ---
        # action_button_layout = QHBoxLayout()
        # self.show_all_button = QPushButton("Show All") # Needs implementation for item visibility
        # self.hide_all_button = QPushButton("Hide All") # Needs implementation
        # action_button_layout.addWidget(self.show_all_button)
        # action_button_layout.addWidget(self.hide_all_button)
        # self.main_layout.addLayout(action_button_layout)
        
        self.setObjectName("SelectionPaneWidget")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)


    def _get_display_name(self, obj_data: Dict[str, Any], index: int) -> str:
        """Generates a display name for a map object."""
        name = obj_data.get("editor_name") # A potential new user-defined name field
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

        # Try to get a nice name from palette definition
        palette_asset_info = self.editor_state.assets_palette.get(asset_key)
        if palette_asset_info and palette_asset_info.get("name_in_palette"):
            name = palette_asset_info["name_in_palette"]
        elif game_type_id and game_type_id != asset_key:
            name = str(game_type_id).replace("_", " ").title()
        else:
            name = asset_key.replace("_", " ").title()
        
        # Add a unique identifier part if names are not unique enough
        # For now, simple index is okay, but later a real unique ID per object would be better.
        # name += f" [{index}]" 
        return name


    @Slot()
    def populate_items(self):
        """
        Populates the list widget with items from the current map state.
        Should be called when the map content changes or the map is loaded.
        """
        logger.debug("SelectionPane: Populating items.")
        self.item_list_widget.blockSignals(True) # Block signals during repopulation
        
        current_selected_obj_data_ref: Optional[Any] = None
        if self.parent_main_window and hasattr(self.parent_main_window, 'map_view_widget'):
            map_view = self.parent_main_window.map_view_widget # type: ignore
            selected_scene_items = map_view.map_scene.selectedItems()
            if len(selected_scene_items) == 1 and hasattr(selected_scene_items[0], 'map_object_data_ref'):
                current_selected_obj_data_ref = selected_scene_items[0].map_object_data_ref

        self.item_list_widget.clear()
        
        # Sort objects, e.g., by layer order then by creation order (original list order)
        # For simplicity, using original list order for now. Layer order could be complex if many layers.
        # sorted_objects = sorted(self.editor_state.placed_objects, key=lambda x: (x.get("layer_order", 0), self.editor_state.placed_objects.index(x)))
        
        search_text = self.search_box.text().lower()

        for i, obj_data in enumerate(self.editor_state.placed_objects):
            display_name = self._get_display_name(obj_data, i)

            if search_text and search_text not in display_name.lower():
                asset_key = obj_data.get("asset_editor_key", "").lower()
                game_type = obj_data.get("game_type_id", "").lower()
                if search_text not in asset_key and search_text not in game_type:
                    continue # Skip if search text doesn't match display name, asset key, or game type

            list_item = QListWidgetItem(display_name)
            list_item.setData(Qt.ItemDataRole.UserRole, obj_data) 
            # Potential: Add icons for visibility/lock state
            # list_item.setIcon(QIcon("path/to/visible_icon.png")) 
            self.item_list_widget.addItem(list_item)

            if current_selected_obj_data_ref is obj_data:
                list_item.setSelected(True)
                # self.item_list_widget.scrollToItem(list_item, QAbstractItemView.ScrollHint.EnsureVisible)

        self.item_list_widget.blockSignals(False)
        if self.item_list_widget.selectedItems(): # Ensure the selected item is visible after filtering
            self.item_list_widget.scrollToItem(self.item_list_widget.selectedItems()[0], QAbstractItemView.ScrollHint.EnsureVisible)


    @Slot(str)
    def filter_items(self, text: str):
        """Filters items in the list based on the search text."""
        self.populate_items() # Re-populating with filter is simplest for now

    @Slot(QListWidgetItem)
    def _on_list_item_clicked(self, list_widget_item: QListWidgetItem):
        obj_data_ref = list_widget_item.data(Qt.ItemDataRole.UserRole)
        if obj_data_ref:
            # Request the main editor/map view to select this object
            self.select_map_object_via_pane_requested.emit(obj_data_ref)
            logger.debug(f"SelectionPane: Clicked, requesting map selection of: {self._get_display_name(obj_data_ref, -1)}")

    # @Slot(QListWidgetItem)
    # def _on_list_item_double_clicked(self, list_widget_item: QListWidgetItem):
    #     """Handle double-click for renaming (example)."""
    #     obj_data_ref = list_widget_item.data(Qt.ItemDataRole.UserRole)
    #     if obj_data_ref:
    #         # Simple input dialog for renaming
    #         current_name = obj_data_ref.get("editor_name", self._get_display_name(obj_data_ref, 0))
    #         new_name, ok = QInputDialog.getText(self, "Rename Object", "Enter new name:", text=current_name)
    #         if ok and new_name:
    #             self.rename_item_requested.emit(obj_data_ref, new_name)


    @Slot()
    def sync_selection_from_map(self):
        """
        Updates the selection in this pane's list widget based on the current
        selection in the MapViewWidget.
        This slot should be connected to map_view_widget.map_scene.selectionChanged.
        """
        logger.debug("SelectionPane: Syncing selection from map.")
        self.item_list_widget.blockSignals(True) # Prevent feedback loop

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
                    # Use setCurrentItem for single selection mode to also clear previous
                    self.item_list_widget.setCurrentItem(list_item) 
                self.item_list_widget.scrollToItem(list_item, QAbstractItemView.ScrollHint.EnsureVisible)
                found_and_selected = True
                break 
        
        if not found_and_selected:
            self.item_list_widget.clearSelection()

        self.item_list_widget.blockSignals(False)


    # --- Controller Navigation (Optional Basic Implementation) ---
    def on_controller_focus_gained(self):
        logger.debug("SelectionPane: Controller focus gained.")
        self.item_list_widget.setFocus()
        if self.item_list_widget.count() > 0 and not self.item_list_widget.currentItem():
            self.item_list_widget.setCurrentRow(0)
        # Add visual indication of focus if needed

    def on_controller_focus_lost(self):
        logger.debug("SelectionPane: Controller focus lost.")
        # Remove visual indication of focus if needed

    def handle_controller_action(self, action: str, value: Any):
        if not self.hasFocus() and not self.item_list_widget.hasFocus() and not self.search_box.hasFocus():
             return

        if self.search_box.hasFocus():
            # Handle search box input if needed, or pass to list
            if action == ACTION_UI_DOWN: # type: ignore
                self.item_list_widget.setFocus()
                if self.item_list_widget.count() > 0 and not self.item_list_widget.currentItem():
                    self.item_list_widget.setCurrentRow(0)
            return # Let search box handle text input

        # List widget navigation
        current_row = self.item_list_widget.currentRow()
        if action == ACTION_UI_UP: # type: ignore
            if current_row > 0:
                self.item_list_widget.setCurrentRow(current_row - 1)
        elif action == ACTION_UI_DOWN: # type: ignore
            if current_row < self.item_list_widget.count() - 1:
                self.item_list_widget.setCurrentRow(current_row + 1)
        elif action == ACTION_UI_ACCEPT: # type: ignore
            current_item = self.item_list_widget.currentItem()
            if current_item:
                self._on_list_item_clicked(current_item)
        elif action == ACTION_UI_TAB_NEXT: # type: ignore
            # Cycle focus to search box or next panel
            if self.item_list_widget.hasFocus():
                self.search_box.setFocus()
            # else: # If search box had focus, emit to main window to change panel
            #     if hasattr(self.parent_main_window, "_cycle_panel_focus_next"):
            #         self.parent_main_window._cycle_panel_focus_next() # type: ignore
        elif action == ACTION_UI_TAB_PREV: # type: ignore
            if self.item_list_widget.hasFocus():
                 self.search_box.setFocus()
            # else:
            #     if hasattr(self.parent_main_window, "_cycle_panel_focus_prev"):
            #         self.parent_main_window._cycle_panel_focus_prev() # type: ignore


# Example usage placeholder for ED_CONFIG if this file is run standalone for testing (won't fully work)
if __name__ != "__main__":
    from . import editor_config as ED_CONFIG
else: # Basic fallback for standalone testing if needed
    class ED_CONFIG_FALLBACK: # type: ignore
        CUSTOM_ASSET_PALETTE_PREFIX = "custom:"
        TRIGGER_SQUARE_ASSET_KEY = "trigger_square"
    ED_CONFIG = ED_CONFIG_FALLBACK() # type: ignore


#################### END OF FILE: editor_selection_pane.py ####################