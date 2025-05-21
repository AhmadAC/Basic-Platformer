# app_ui_creator.py
import os
import sys
import time
from typing import Dict, Optional, Any, List, TYPE_CHECKING

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QDialogButtonBox, QScrollArea, QSizePolicy,
    QListWidget, QListWidgetItem, QApplication, QMessageBox, QLineEdit, QDialog
)
from PySide6.QtGui import QFont, QColor, QPalette
from PySide6.QtCore import Qt, Slot, QTimer # QTimer might not be needed here directly

import pygame # For UI navigation with joystick

import constants as C
import config as game_config
from logger import info, debug, warning, error

# Forward declaration for MainWindow type hint for functions in THIS file
if TYPE_CHECKING:
    from app_core import MainWindow # This is correct for type hinting 'main_window' parameters
else:
    MainWindow = Any

# --- Function definitions start here ---

def _create_main_menu_widget(main_window: 'MainWindow') -> QWidget:
    main_window._main_menu_buttons_ref = []
    menu_widget = QWidget()
    layout = QVBoxLayout(menu_widget)
    layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.setSpacing(15)

    title_label = QLabel("Platformer Adventure LAN")
    title_label.setFont(main_window.fonts["large"])
    title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(title_label)

    buttons_data = [
        ("Couch Co-op", main_window.on_start_couch_play),
        ("Host Game", main_window.on_start_host_game),
        ("Join LAN Game", main_window.on_start_join_lan),
        ("Join by IP", main_window.on_start_join_ip),
        ("Level Editor", lambda: main_window.show_view("editor")),
        ("Settings/Controls", lambda: main_window.show_view("settings")),
        ("Quit", main_window.request_close_app)
    ]

    for text, slot_func in buttons_data:
        button = QPushButton(text)
        button.setFont(main_window.fonts["medium"])
        button.setMinimumHeight(40)
        button.setMinimumWidth(250)
        button.clicked.connect(slot_func)
        layout.addWidget(button)
        main_window._main_menu_buttons_ref.append(button)
    return menu_widget

def _create_map_select_widget(main_window: 'MainWindow') -> QWidget:
    page_widget = QWidget()
    main_layout = QVBoxLayout(page_widget)
    main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
    main_layout.setSpacing(10)

    main_window.map_select_title_label = QLabel("Select Map")
    main_window.map_select_title_label.setFont(main_window.fonts["large"])
    main_window.map_select_title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    main_layout.addWidget(main_window.map_select_title_label)

    main_window.map_select_scroll_area = QScrollArea()
    main_window.map_select_scroll_area.setWidgetResizable(True)
    main_window.map_select_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    main_window.map_select_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

    main_window.map_buttons_container = QWidget()
    main_window.map_buttons_layout = QGridLayout(main_window.map_buttons_container)
    main_window.map_buttons_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
    main_window.map_buttons_layout.setSpacing(10)

    main_window.map_select_scroll_area.setWidget(main_window.map_buttons_container)
    main_layout.addWidget(main_window.map_select_scroll_area, 1)

    back_button = QPushButton("Back to Main Menu")
    back_button.setFont(main_window.fonts["medium"])
    back_button.setMinimumHeight(40)
    back_button.setMinimumWidth(250)
    back_button.clicked.connect(lambda: main_window.show_view("menu"))

    button_layout_wrapper = QHBoxLayout()
    button_layout_wrapper.addStretch()
    button_layout_wrapper.addWidget(back_button)
    button_layout_wrapper.addStretch()
    main_layout.addLayout(button_layout_wrapper)

    return page_widget

def _populate_map_list_for_selection(main_window: 'MainWindow', purpose: str):
    if not isinstance(main_window.map_buttons_layout, QGridLayout):
        error("Map buttons layout is not QGridLayout in _populate_map_list_for_selection"); return
    while main_window.map_buttons_layout.count():
        child = main_window.map_buttons_layout.takeAt(0)
        if child.widget(): child.widget().deleteLater()
    main_window._map_selection_buttons_ref.clear()
    maps_dir = getattr(C, "MAPS_DIR", "maps")
    if not os.path.isabs(maps_dir): maps_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", maps_dir)


    available_maps = []
    if os.path.exists(maps_dir) and os.path.isdir(maps_dir):
        try:
            map_files = sorted([f[:-3] for f in os.listdir(maps_dir) if f.endswith(".py") and f != "__init__.py" and f[:-3] != "level_default"])
            prio = ["original", "lava", "cpu_extended", "noenemy", "bigmap1"]
            available_maps = [m for m in prio if m in map_files] + [m for m in map_files if m not in prio]
        except OSError as e: main_window.map_buttons_layout.addWidget(QLabel(f"Error: {e}"),0,0,1,main_window.NUM_MAP_COLUMNS); return
    else: main_window.map_buttons_layout.addWidget(QLabel(f"Maps dir not found: {maps_dir}"),0,0,1,main_window.NUM_MAP_COLUMNS); return
    if not available_maps: main_window.map_buttons_layout.addWidget(QLabel("No maps found."),0,0,1,main_window.NUM_MAP_COLUMNS); return

    for idx, map_name in enumerate(available_maps):
        button = QPushButton(map_name.replace("_", " ").title()); button.setFont(main_window.fonts["medium"]); button.setMinimumHeight(40); button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        if purpose == "couch_coop": button.clicked.connect(lambda checked=False, mn=map_name: main_window._on_map_selected_for_couch_coop(mn))
        elif purpose == "host_game": button.clicked.connect(lambda checked=False, mn=map_name: main_window._on_map_selected_for_host_game(mn))
        row, col = divmod(idx, main_window.NUM_MAP_COLUMNS)
        main_window.map_buttons_layout.addWidget(button, row, col); main_window._map_selection_buttons_ref.append(button)

def _create_view_page_with_back_button(main_window: 'MainWindow', title_text: str, content_widget_to_embed: QWidget, back_slot: Slot) -> QWidget:
    page_widget = QWidget(); page_layout = QVBoxLayout(page_widget); page_layout.setContentsMargins(10,10,10,10); page_layout.setSpacing(10)
    title_label = QLabel(title_text); title_label.setFont(main_window.fonts["large"]); title_label.setAlignment(Qt.AlignmentFlag.AlignCenter); page_layout.addWidget(title_label)
    page_layout.addWidget(content_widget_to_embed, 1)
    back_button = QPushButton("Back to Main Menu"); back_button.setFont(main_window.fonts["medium"]); back_button.setMinimumHeight(40); back_button.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed); back_button.clicked.connect(back_slot)
    button_layout_wrapper = QHBoxLayout(); button_layout_wrapper.addStretch(); button_layout_wrapper.addWidget(back_button); button_layout_wrapper.addStretch(); page_layout.addLayout(button_layout_wrapper)
    return page_widget

def _ensure_editor_instance(main_window: 'MainWindow'):
    from PySide6.QtWidgets import QMainWindow as EditorMainWindowType # Local import for type
    if main_window.actual_editor_module_instance and main_window.actual_editor_module_instance.parent() is main_window.editor_content_container: return
    
    # Clear previous content
    layout = main_window.editor_content_container.layout()
    if layout is not None:
        while layout.count(): 
            item = layout.takeAt(0)
            widget = item.widget()
            if widget: 
                widget.setParent(None) # Detach
                widget.deleteLater()
    else: # Ensure layout exists
        layout = QVBoxLayout(main_window.editor_content_container)
        main_window.editor_content_container.setLayout(layout)


    if main_window.actual_editor_module_instance is None:
        info("UI_VIEWS: Creating and embedding editor instance.")
        try:
            from editor.editor import editor_main
            instance = editor_main(parent_app_instance=QApplication.instance(), embed_mode=True)
            if not instance or not isinstance(instance, EditorMainWindowType):
                error("Failed to get QMainWindow editor instance."); _add_placeholder_to_content_area(main_window, main_window.editor_content_container, "Error: Editor load failed."); return
            main_window.actual_editor_module_instance = instance
        except Exception as e: error(f"Exception creating editor: {e}", exc_info=True); _add_placeholder_to_content_area(main_window, main_window.editor_content_container, f"Error loading editor: {e}"); main_window.actual_editor_module_instance = None; return
    
    if main_window.actual_editor_module_instance:
        if main_window.actual_editor_module_instance.parent() is not None: main_window.actual_editor_module_instance.setParent(None)
        main_window.editor_content_container.layout().addWidget(main_window.actual_editor_module_instance); info("UI_VIEWS: Editor instance embedded.")

def _ensure_controls_mapper_instance(main_window: 'MainWindow'):
    from controller_settings.controller_mapper_gui import MainWindow as ControlsMapperWindowType
    if main_window.actual_controls_module_instance and main_window.actual_controls_module_instance.parent() is main_window.controls_content_container: return

    # Clear previous content
    layout = main_window.controls_content_container.layout()
    if layout is not None:
        while layout.count(): 
            item = layout.takeAt(0)
            widget = item.widget()
            if widget: 
                widget.setParent(None) # Detach
                widget.deleteLater()
    else: # Ensure layout exists
        layout = QVBoxLayout(main_window.controls_content_container)
        main_window.controls_content_container.setLayout(layout)
                
    if main_window.actual_controls_module_instance is None:
        info("UI_VIEWS: Creating and embedding controls mapper instance.")
        try:
            from controller_settings.controller_mapper_gui import MainWindow as ControlsMapperWindow
            instance = ControlsMapperWindow()
            if not instance or not isinstance(instance, ControlsMapperWindowType): # Ensure correct type check
                error("Failed to get QWidget controls instance."); _add_placeholder_to_content_area(main_window, main_window.controls_content_container, "Error: Controls UI load failed (instance type)."); return
            main_window.actual_controls_module_instance = instance
        except ImportError as e_imp: error(f"ImportError creating controls mapper: {e_imp}", exc_info=True); _add_placeholder_to_content_area(main_window, main_window.controls_content_container, f"Error importing controls UI: {e_imp}"); main_window.actual_controls_module_instance = None; return
        except Exception as e: error(f"Exception creating controls mapper: {e}", exc_info=True); _add_placeholder_to_content_area(main_window, main_window.controls_content_container, f"Error loading controls UI: {e}"); main_window.actual_controls_module_instance = None; return
    
    if main_window.actual_controls_module_instance:
        if main_window.actual_controls_module_instance.parent() is not None: main_window.actual_controls_module_instance.setParent(None)
        main_window.controls_content_container.layout().addWidget(main_window.actual_controls_module_instance); info("UI_VIEWS: Controls mapper instance embedded/handled.")

def _add_placeholder_to_content_area(main_window: 'MainWindow', container: QWidget, msg: str):
    layout = container.layout();
    if layout is None: layout = QVBoxLayout(container); container.setLayout(layout)
    else:
        while layout.count(): 
            child = layout.takeAt(0);
            widget = child.widget()
            if widget: widget.deleteLater() # Use deleteLater for QObjects
    lbl = QLabel(msg); lbl.setAlignment(Qt.AlignmentFlag.AlignCenter); lbl.setFont(main_window.fonts["medium"]); layout.addWidget(lbl)

def _show_status_dialog(main_window: 'MainWindow', title: str, initial_message: str):
    from PySide6.QtWidgets import QProgressBar 
    if main_window.status_dialog is None:
        main_window.status_dialog = QDialog(main_window); main_window.status_dialog.setWindowTitle(title); layout = QVBoxLayout(main_window.status_dialog); main_window.status_label_in_dialog = QLabel(initial_message); main_window.status_label_in_dialog.setWordWrap(True); layout.addWidget(main_window.status_label_in_dialog)
        main_window.status_progress_bar_in_dialog = QProgressBar(); main_window.status_progress_bar_in_dialog.setRange(0,100); main_window.status_progress_bar_in_dialog.setTextVisible(True); layout.addWidget(main_window.status_progress_bar_in_dialog); main_window.status_dialog.setMinimumWidth(350)
    else: main_window.status_dialog.setWindowTitle(title)
    if main_window.status_label_in_dialog: main_window.status_label_in_dialog.setText(initial_message)
    if main_window.status_progress_bar_in_dialog: main_window.status_progress_bar_in_dialog.setValue(0); main_window.status_progress_bar_in_dialog.setVisible(False)
    main_window.status_dialog.show(); QApplication.processEvents()

def _update_status_dialog(main_window: 'MainWindow', message: str, progress: float = -1.0):
    if main_window.status_dialog and main_window.status_dialog.isVisible():
        if main_window.status_label_in_dialog: main_window.status_label_in_dialog.setText(message)
        if main_window.status_progress_bar_in_dialog:
            if 0 <= progress <= 100: main_window.status_progress_bar_in_dialog.setValue(int(progress)); main_window.status_progress_bar_in_dialog.setVisible(True)
            else: main_window.status_progress_bar_in_dialog.setVisible(False)
    QApplication.processEvents()

def _close_status_dialog(main_window: 'MainWindow'):
    if main_window.status_dialog: main_window.status_dialog.hide()

def _show_lan_search_dialog(main_window: 'MainWindow'):
    if main_window.lan_search_dialog is None:
        main_window.lan_search_dialog = QDialog(main_window); main_window.lan_search_dialog.setWindowTitle("Searching for LAN Games..."); layout = QVBoxLayout(main_window.lan_search_dialog); main_window.lan_search_status_label = QLabel("Initializing search...")
        layout.addWidget(main_window.lan_search_status_label); main_window.lan_servers_list_widget = QListWidget(); main_window.lan_servers_list_widget.itemDoubleClicked.connect(main_window._join_selected_lan_server_from_dialog); layout.addWidget(main_window.lan_servers_list_widget)
        main_window.lan_search_dialog.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Retry)
        main_window.lan_search_dialog.button_box.button(QDialogButtonBox.StandardButton.Ok).setText("Join Selected"); main_window.lan_search_dialog.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        main_window.lan_search_dialog.button_box.accepted.connect(main_window._join_selected_lan_server_from_dialog); main_window.lan_search_dialog.button_box.rejected.connect(main_window.lan_search_dialog.reject)
        main_window.lan_search_dialog.button_box.button(QDialogButtonBox.StandardButton.Retry).clicked.connect(main_window._start_lan_server_search_thread); layout.addWidget(main_window.lan_search_dialog.button_box)
        main_window.lan_search_dialog.rejected.connect(lambda: (main_window.show_view("menu"), setattr(main_window, 'current_modal_dialog', None))); main_window.lan_search_dialog.setMinimumSize(400, 300)
    main_window.lan_servers_list_widget.clear(); main_window.lan_search_status_label.setText("Searching for LAN games..."); main_window.lan_search_dialog.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
    main_window.current_modal_dialog = "lan_search"; main_window._lan_search_list_selected_idx = 0; _update_lan_search_list_focus(main_window)
    main_window.lan_search_dialog.show(); main_window._start_lan_server_search_thread()

def _update_lan_search_list_focus(main_window: 'MainWindow'):
    if not main_window.lan_search_dialog or not main_window.lan_servers_list_widget: return
    if main_window.lan_servers_list_widget.count() > 0:
        main_window.lan_servers_list_widget.setCurrentRow(main_window._lan_search_list_selected_idx)
        selected_item = main_window.lan_servers_list_widget.item(main_window._lan_search_list_selected_idx)
        if selected_item: main_window.lan_servers_list_widget.scrollToItem(selected_item, QListWidget.ScrollHint.EnsureVisible)
        if hasattr(main_window.lan_search_dialog, 'button_box'): main_window.lan_search_dialog.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)
    elif hasattr(main_window.lan_search_dialog, 'button_box'): main_window.lan_search_dialog.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)

def _update_ip_dialog_button_focus(main_window: 'MainWindow'):
    if not main_window.ip_input_dialog or not main_window._ip_dialog_buttons_ref: return
    for i, button in enumerate(main_window._ip_dialog_buttons_ref):
        is_selected = (i == main_window._ip_dialog_selected_button_idx)
        button.setStyleSheet("QPushButton { border: 2px solid yellow; background-color: #555; color: white; } QPushButton:focus { outline: none; }" if is_selected else "")
        if is_selected: button.setFocus(Qt.FocusReason.OtherFocusReason)

def _poll_pygame_joysticks_for_ui_navigation(main_window: 'MainWindow'):
    active_ui_element = main_window.current_modal_dialog if main_window.current_modal_dialog else main_window.current_view_name
    if active_ui_element not in ["menu", "map_select", "lan_search", "ip_input"] or not main_window._pygame_joysticks:
        _reset_all_prev_press_flags(main_window); return
    pygame.event.pump(); joy = main_window._pygame_joysticks[0]; joy_idx = 0
    JOY_NAV_AXIS_ID_Y = 1; JOY_NAV_AXIS_ID_X = 0; JOY_NAV_HAT_ID = 0
    current_time = time.monotonic()
    if current_time - main_window._last_pygame_joy_nav_time < 0.20: return
    confirm_mapping = game_config.LOADED_PYGAME_JOYSTICK_MAPPINGS.get("menu_confirm")
    cancel_mapping = game_config.LOADED_PYGAME_JOYSTICK_MAPPINGS.get("menu_cancel")
    
    if joy.get_numhats() > JOY_NAV_HAT_ID:
        hat_x, hat_y = joy.get_hat(JOY_NAV_HAT_ID); navigated_by_hat = False
        if hat_y > 0.5: 
            if active_ui_element in ["menu", "map_select", "lan_search"]: _navigate_current_menu_pygame_joy(main_window, 1); navigated_by_hat = True
        elif hat_y < -0.5:
            if active_ui_element in ["menu", "map_select", "lan_search"]: _navigate_current_menu_pygame_joy(main_window, -1); navigated_by_hat = True
        if hat_x > 0.5:
            if active_ui_element == "map_select" or (active_ui_element == "ip_input" and main_window._ip_dialog_buttons_ref): _navigate_current_menu_pygame_joy(main_window, 2); navigated_by_hat = True
        elif hat_x < -0.5:
            if active_ui_element == "map_select" or (active_ui_element == "ip_input" and main_window._ip_dialog_buttons_ref): _navigate_current_menu_pygame_joy(main_window, -2); navigated_by_hat = True
        if navigated_by_hat: main_window._last_pygame_joy_nav_time = current_time; _reset_all_prev_press_flags(main_window); return

    nav_threshold = 0.65; navigated_by_axis = False
    if joy.get_numaxes() > JOY_NAV_AXIS_ID_Y:
        axis_y_val = joy.get_axis(JOY_NAV_AXIS_ID_Y)
        if axis_y_val > nav_threshold:
            if not main_window._pygame_joy_axis_was_active_pos.get(joy_idx, False):
                if active_ui_element in ["menu", "map_select", "lan_search"]: _navigate_current_menu_pygame_joy(main_window, 1); navigated_by_axis = True
            main_window._pygame_joy_axis_was_active_pos[joy_idx] = True
        else: main_window._pygame_joy_axis_was_active_pos[joy_idx] = False
        if axis_y_val < -nav_threshold:
            if not main_window._pygame_joy_axis_was_active_neg.get(joy_idx, False):
                if active_ui_element in ["menu", "map_select", "lan_search"]: _navigate_current_menu_pygame_joy(main_window, -1); navigated_by_axis = True
            main_window._pygame_joy_axis_was_active_neg[joy_idx] = True
        else: main_window._pygame_joy_axis_was_active_neg[joy_idx] = False
    if joy.get_numaxes() > JOY_NAV_AXIS_ID_X:
         axis_x_val = joy.get_axis(JOY_NAV_AXIS_ID_X)
         if axis_x_val > nav_threshold:
            if not main_window._pygame_joy_axis_was_active_pos.get(f"{joy_idx}_x", False):
                if active_ui_element == "map_select" or (active_ui_element == "ip_input" and main_window._ip_dialog_buttons_ref): _navigate_current_menu_pygame_joy(main_window, 2); navigated_by_axis = True
            main_window._pygame_joy_axis_was_active_pos[f"{joy_idx}_x"] = True
         else: main_window._pygame_joy_axis_was_active_pos[f"{joy_idx}_x"] = False
         if axis_x_val < -nav_threshold:
            if not main_window._pygame_joy_axis_was_active_neg.get(f"{joy_idx}_x", False):
                if active_ui_element == "map_select" or (active_ui_element == "ip_input" and main_window._ip_dialog_buttons_ref): _navigate_current_menu_pygame_joy(main_window, -2); navigated_by_axis = True
            main_window._pygame_joy_axis_was_active_neg[f"{joy_idx}_x"] = True
         else: main_window._pygame_joy_axis_was_active_neg[f"{joy_idx}_x"] = False
    if navigated_by_axis: main_window._last_pygame_joy_nav_time = current_time; _reset_all_prev_press_flags(main_window); return

    current_joy_buttons = {i: joy.get_button(i) for i in range(joy.get_numbuttons())}; prev_joy_buttons = main_window._pygame_joy_button_prev_state[joy_idx]
    confirm_pressed = False
    if confirm_mapping and confirm_mapping.get("type") == "button": btn_id = confirm_mapping.get("id"); confirm_pressed = current_joy_buttons.get(btn_id, False) and not prev_joy_buttons.get(btn_id, False)
    if confirm_pressed:
        if active_ui_element in ["menu", "map_select"]: _activate_current_menu_selected_button_pygame_joy(main_window)
        elif active_ui_element == "lan_search": main_window._join_selected_lan_server_from_dialog()
        elif active_ui_element == "ip_input": _activate_ip_dialog_button(main_window)
        main_window._last_pygame_joy_nav_time = current_time; _reset_all_prev_press_flags(main_window); main_window._pygame_joy_button_prev_state[joy_idx] = current_joy_buttons.copy(); return
    cancel_pressed = False
    if cancel_mapping and cancel_mapping.get("type") == "button": btn_id = cancel_mapping.get("id"); cancel_pressed = current_joy_buttons.get(btn_id, False) and not prev_joy_buttons.get(btn_id, False)
    if cancel_pressed:
        if active_ui_element == "menu": main_window.request_close_app()
        elif active_ui_element == "map_select": main_window.show_view("menu")
        elif active_ui_element == "lan_search" and main_window.lan_search_dialog: main_window.lan_search_dialog.reject()
        elif active_ui_element == "ip_input" and main_window.ip_input_dialog: main_window.ip_input_dialog.reject()
        main_window._last_pygame_joy_nav_time = current_time; _reset_all_prev_press_flags(main_window); main_window._pygame_joy_button_prev_state[joy_idx] = current_joy_buttons.copy(); return
    if active_ui_element == "lan_search":
        retry_mapping = game_config.LOADED_PYGAME_JOYSTICK_MAPPINGS.get("reset"); retry_pressed = False
        if retry_mapping and retry_mapping.get("type") == "button": btn_id = retry_mapping.get("id"); retry_pressed = current_joy_buttons.get(btn_id, False) and not prev_joy_buttons.get(btn_id, False)
        if retry_pressed:
            if main_window.lan_search_dialog and hasattr(main_window.lan_search_dialog, 'button_box'): main_window.lan_search_dialog.button_box.button(QDialogButtonBox.StandardButton.Retry).click()
            main_window._last_pygame_joy_nav_time = current_time; _reset_all_prev_press_flags(main_window); main_window._pygame_joy_button_prev_state[joy_idx] = current_joy_buttons.copy(); return
    main_window._pygame_joy_button_prev_state[joy_idx] = current_joy_buttons.copy()

def _navigate_current_menu_pygame_joy(main_window: 'MainWindow', direction: int):
    buttons_to_nav = main_window._current_active_menu_buttons
    selected_idx_attr_name = main_window._current_active_menu_selected_idx_ref
    if not buttons_to_nav or not hasattr(main_window, selected_idx_attr_name): return
    num_buttons = len(buttons_to_nav)
    if num_buttons == 0: return
    current_idx = getattr(main_window, selected_idx_attr_name)
    new_idx = current_idx
    
    if main_window.current_view_name == "map_select":
        row, col = divmod(current_idx, main_window.NUM_MAP_COLUMNS)
        num_rows = (num_buttons + main_window.NUM_MAP_COLUMNS - 1) // main_window.NUM_MAP_COLUMNS
        if direction == -1 : row = max(0, row - 1)
        elif direction == 1: row = min(num_rows - 1, row + 1)
        elif direction == -2: col = max(0, col - 1)
        elif direction == 2:
            if row == num_rows - 1: # If in the last row
                items_in_last_row = num_buttons % main_window.NUM_MAP_COLUMNS
                if items_in_last_row == 0: items_in_last_row = main_window.NUM_MAP_COLUMNS # Full last row
                col = min(items_in_last_row - 1, col + 1)
            else: # Not in the last row
                col = min(main_window.NUM_MAP_COLUMNS - 1, col + 1)

        new_idx = row * main_window.NUM_MAP_COLUMNS + col; new_idx = min(num_buttons - 1, max(0, new_idx))
    elif main_window.current_modal_dialog == "lan_search":
        if direction == 1: main_window._lan_search_list_selected_idx = min(main_window.lan_servers_list_widget.count() - 1, main_window._lan_search_list_selected_idx + 1)
        elif direction == -1: main_window._lan_search_list_selected_idx = max(0, main_window._lan_search_list_selected_idx - 1)
        _update_lan_search_list_focus(main_window); return
    elif main_window.current_modal_dialog == "ip_input":
        if direction in [-2, 2]: main_window._ip_dialog_selected_button_idx = 1 - main_window._ip_dialog_selected_button_idx
        _update_ip_dialog_button_focus(main_window); return
    else: new_idx = (current_idx + direction + num_buttons) % num_buttons
        
    setattr(main_window, selected_idx_attr_name, new_idx)
    _update_current_menu_button_focus(main_window)
    info(f"Menu Joystick: Navigated to button index {new_idx} in UI '{main_window.current_modal_dialog or main_window.current_view_name}'")

def _activate_current_menu_selected_button_pygame_joy(main_window: 'MainWindow'):
    buttons_to_activate = main_window._current_active_menu_buttons
    selected_idx_attr_name = main_window._current_active_menu_selected_idx_ref
    if not buttons_to_activate or not hasattr(main_window, selected_idx_attr_name): return
    current_idx = getattr(main_window, selected_idx_attr_name)
    if not (0 <= current_idx < len(buttons_to_activate)): return
    selected_button = buttons_to_activate[current_idx]
    info(f"Menu Joystick: Activating button '{selected_button.text()}' in view '{main_window.current_view_name}'")
    selected_button.click()

def _reset_all_prev_press_flags(main_window: 'MainWindow'):
    main_window._prev_menu_confirm_pressed = False; main_window._prev_menu_cancel_pressed = False
    main_window._prev_lan_confirm_pressed = False; main_window._prev_lan_cancel_pressed = False; main_window._prev_lan_retry_pressed = False
    main_window._prev_ip_dialog_confirm_pressed = False; main_window._prev_ip_dialog_cancel_pressed = False

def _update_status_dialog(main_window: 'MainWindow', message: str, progress: float = -1.0, title: Optional[str] = None):
    if main_window.status_dialog and main_window.status_dialog.isVisible():
        if title: # If a new title is provided, update it
            main_window.status_dialog.setWindowTitle(title)
        if main_window.status_label_in_dialog: main_window.status_label_in_dialog.setText(message)
        if main_window.status_progress_bar_in_dialog:
            if 0 <= progress <= 100: main_window.status_progress_bar_in_dialog.setValue(int(progress)); main_window.status_progress_bar_in_dialog.setVisible(True)
            else: main_window.status_progress_bar_in_dialog.setVisible(False)
    QApplication.processEvents()

def _activate_ip_dialog_button(main_window: 'MainWindow'):
    if main_window.ip_input_dialog and main_window._ip_dialog_buttons_ref and 0 <= main_window._ip_dialog_selected_button_idx < len(main_window._ip_dialog_buttons_ref):
        main_window._ip_dialog_buttons_ref[main_window._ip_dialog_selected_button_idx].click()

def _update_current_menu_button_focus(main_window: 'MainWindow'):
    buttons_to_update = main_window._current_active_menu_buttons
    selected_idx_attr_name = main_window._current_active_menu_selected_idx_ref
    if not buttons_to_update or not hasattr(main_window, selected_idx_attr_name): return
    
    current_selected_idx = getattr(main_window, selected_idx_attr_name)
    selected_button_widget = None

    for i, button in enumerate(buttons_to_update):
        is_selected = (i == current_selected_idx)
        # Basic style, ensure you have a default style or this might look odd
        if is_selected:
            button.setStyleSheet("QPushButton { border: 2px solid yellow; background-color: #555; color: white; } QPushButton:focus { outline: none; }")
            button.setFocus(Qt.FocusReason.OtherFocusReason)
            selected_button_widget = button
        else:
            button.setStyleSheet("") # Reset to default stylesheet

    if selected_button_widget:
        if main_window.current_view_name == "map_select" and main_window.map_select_scroll_area:
            main_window.map_select_scroll_area.ensureWidgetVisible(selected_button_widget, 50, 50) # 50px margin
        # Note: LAN search list focus is handled by _update_lan_search_list_focus and QListWidget's own mechanisms.
        # IP dialog button focus is handled by _update_ip_dialog_button_focus.
        # This function primarily handles general menu button lists.