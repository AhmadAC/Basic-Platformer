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
from PySide6.QtGui import QFont, QColor
from PySide6.QtCore import Qt, Slot, QTimer

import pygame # For UI navigation with joystick

import constants as C
import config as game_config # For joystick mappings for UI nav and joystick count
from logger import info, debug, warning, error

if TYPE_CHECKING:
    from app_core import MainWindow
else:
    MainWindow = Any

# --- UI Element Creation Functions ---

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
        ("Settings & Controls", lambda: main_window.show_view("settings")),
        ("Quit", main_window.request_close_app)
    ]
    for text, slot_func in buttons_data:
        button = QPushButton(text)
        button.setFont(main_window.fonts["medium"]); button.setMinimumHeight(40)
        button.setMinimumWidth(250); button.clicked.connect(slot_func)
        layout.addWidget(button); main_window._main_menu_buttons_ref.append(button)
    return menu_widget

def _create_map_select_widget(main_window: 'MainWindow') -> QWidget:
    page_widget = QWidget(); main_layout = QVBoxLayout(page_widget)
    main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter); main_layout.setSpacing(10)
    main_window.map_select_title_label = QLabel("Select Map"); main_window.map_select_title_label.setFont(main_window.fonts["large"])
    main_window.map_select_title_label.setAlignment(Qt.AlignmentFlag.AlignCenter); main_layout.addWidget(main_window.map_select_title_label)
    main_window.map_select_scroll_area = QScrollArea(); main_window.map_select_scroll_area.setWidgetResizable(True)
    main_window.map_select_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    main_window.map_select_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    main_window.map_buttons_container = QWidget()
    main_window.map_buttons_layout = QGridLayout(main_window.map_buttons_container)
    main_window.map_buttons_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter); main_window.map_buttons_layout.setSpacing(10)
    main_window.map_select_scroll_area.setWidget(main_window.map_buttons_container); main_layout.addWidget(main_window.map_select_scroll_area, 1)
    back_button = QPushButton("Back to Main Menu"); back_button.setFont(main_window.fonts["medium"])
    back_button.setMinimumHeight(40); back_button.setMinimumWidth(250); back_button.clicked.connect(lambda: main_window.show_view("menu"))
    button_layout_wrapper = QHBoxLayout(); button_layout_wrapper.addStretch(); button_layout_wrapper.addWidget(back_button)
    button_layout_wrapper.addStretch(); main_layout.addLayout(button_layout_wrapper)
    return page_widget

def _populate_map_list_for_selection(main_window: 'MainWindow', purpose: str):
    if not isinstance(main_window.map_buttons_layout, QGridLayout):
        error("Map buttons layout is not QGridLayout in _populate_map_list_for_selection"); return
    while main_window.map_buttons_layout.count():
        child = main_window.map_buttons_layout.takeAt(0)
        if child.widget(): child.widget().deleteLater()
    main_window._map_selection_buttons_ref.clear()
    maps_dir = str(getattr(C, "MAPS_DIR", "maps"))
    if not os.path.isabs(maps_dir): maps_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), maps_dir)
    available_maps = [];
    if os.path.exists(maps_dir) and os.path.isdir(maps_dir):
        try:
            map_files = sorted([f[:-3] for f in os.listdir(maps_dir) if f.endswith(".py") and f != "__init__.py" and f[:-3] != "level_default"])
            prio = ["original", "lava", "cpu_extended", "noenemy", "bigmap1", "one"]; available_maps = [m for m in prio if m in map_files] + [m for m in map_files if m not in prio]
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
    from PySide6.QtWidgets import QMainWindow as EditorMainWindowType
    if main_window.actual_editor_module_instance and main_window.actual_editor_module_instance.parent() is main_window.editor_content_container: return
    layout = main_window.editor_content_container.layout()
    if layout is not None:
        while layout.count(): 
            item = layout.takeAt(0); widget = item.widget()
            if widget: widget.setParent(None); widget.deleteLater()
    else: layout = QVBoxLayout(main_window.editor_content_container); main_window.editor_content_container.setLayout(layout)
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

def _ensure_controls_settings_instance(main_window: 'MainWindow'):
    from controller_settings.controller_mapper_gui import ControllerSettingsWindow
    if main_window.actual_controls_settings_instance and \
       main_window.actual_controls_settings_instance.parent() is main_window.settings_content_container:
        if hasattr(main_window.actual_controls_settings_instance, 'load_settings_into_ui'):
             main_window.actual_controls_settings_instance.load_settings_into_ui()
        return
    layout = main_window.settings_content_container.layout()
    if layout is not None:
        while layout.count():
            item = layout.takeAt(0); widget = item.widget()
            if widget: widget.setParent(None); widget.deleteLater()
    else: layout = QVBoxLayout(main_window.settings_content_container); main_window.settings_content_container.setLayout(layout)
    if main_window.actual_controls_settings_instance is None or \
       not isinstance(main_window.actual_controls_settings_instance, ControllerSettingsWindow) :
        info("UI_VIEWS: Creating and embedding ControllerSettingsWindow instance.")
        try:
            game_config.load_config() # Ensure latest config before creating UI that reads it
            instance = ControllerSettingsWindow(parent=main_window.settings_content_container)
            main_window.actual_controls_settings_instance = instance
        except ImportError as e_imp: error(f"ImportError creating ControllerSettingsWindow: {e_imp}", exc_info=True); _add_placeholder_to_content_area(main_window, main_window.settings_content_container, f"Error importing controls UI: {e_imp}"); main_window.actual_controls_settings_instance = None; return
        except Exception as e: error(f"Exception creating ControllerSettingsWindow: {e}", exc_info=True); _add_placeholder_to_content_area(main_window, main_window.settings_content_container, f"Error loading controls UI: {e}"); main_window.actual_controls_settings_instance = None; return
    if main_window.actual_controls_settings_instance:
        if main_window.actual_controls_settings_instance.parent() is not main_window.settings_content_container: main_window.actual_controls_settings_instance.setParent(main_window.settings_content_container)
        main_window.settings_content_container.layout().addWidget(main_window.actual_controls_settings_instance)
        if hasattr(main_window.actual_controls_settings_instance, 'load_settings_into_ui'): main_window.actual_controls_settings_instance.load_settings_into_ui()
        info("UI_VIEWS: ControllerSettingsWindow instance embedded/handled.")

def _add_placeholder_to_content_area(main_window: 'MainWindow', container: QWidget, msg: str):
    layout = container.layout();
    if layout is None: layout = QVBoxLayout(container); container.setLayout(layout)
    else:
        while layout.count(): 
            child = layout.takeAt(0); widget = child.widget()
            if widget: widget.deleteLater()
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

def _update_status_dialog(main_window: 'MainWindow', message: str, progress: float = -1.0, title: Optional[str] = None):
    if main_window.status_dialog and main_window.status_dialog.isVisible():
        if title: main_window.status_dialog.setWindowTitle(title)
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
    if main_window.lan_servers_list_widget: main_window.lan_servers_list_widget.clear()
    if main_window.lan_search_status_label: main_window.lan_search_status_label.setText("Searching for LAN games...")
    if main_window.lan_search_dialog and hasattr(main_window.lan_search_dialog, 'button_box'): main_window.lan_search_dialog.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
    main_window.current_modal_dialog = "lan_search"; main_window._lan_search_list_selected_idx = -1; _update_lan_search_list_focus(main_window)
    main_window.lan_search_dialog.show(); main_window._start_lan_server_search_thread()

def _update_lan_search_list_focus(main_window: 'MainWindow'):
    if not main_window.lan_search_dialog or not main_window.lan_servers_list_widget: return
    if main_window.lan_servers_list_widget.count() > 0:
        if not (0 <= main_window._lan_search_list_selected_idx < main_window.lan_servers_list_widget.count()):
            main_window._lan_search_list_selected_idx = 0
        main_window.lan_servers_list_widget.setCurrentRow(main_window._lan_search_list_selected_idx)
        selected_item = main_window.lan_servers_list_widget.item(main_window._lan_search_list_selected_idx)
        if selected_item: main_window.lan_servers_list_widget.scrollToItem(selected_item, QListWidget.ScrollHint.EnsureVisible)
        if hasattr(main_window.lan_search_dialog, 'button_box'): main_window.lan_search_dialog.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)
    elif hasattr(main_window.lan_search_dialog, 'button_box'): main_window.lan_search_dialog.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)

def _update_ip_dialog_button_focus(main_window: 'MainWindow'):
    if not main_window.ip_input_dialog or not main_window._ip_dialog_buttons_ref: return
    # Determine focus color based on which controller is active, or default
    focus_color_str = main_window._p1_ui_focus_color_str # Default (keyboard or joy0)
    if main_window._ui_nav_focus_controller_index == 1: # Joy1
        focus_color_str = main_window._p2_ui_focus_color_str
    elif not main_window._pygame_joysticks: # No joysticks, no special highlight
        focus_color_str = "" 

    for i, button in enumerate(main_window._ip_dialog_buttons_ref):
        is_selected = (i == main_window._ip_dialog_selected_button_idx)
        if focus_color_str:
            button.setStyleSheet(f"QPushButton {{ border: 2px solid {focus_color_str}; background-color: #555; color: white; }} QPushButton:focus {{ outline: none; }}" if is_selected else "")
        else:
            button.setStyleSheet("") # No special highlight if no joysticks
        if is_selected: button.setFocus(Qt.FocusReason.OtherFocusReason)

def _poll_pygame_joysticks_for_ui_navigation(main_window: 'MainWindow'):
    active_ui_element = main_window.current_modal_dialog if main_window.current_modal_dialog else main_window.current_view_name
    if active_ui_element not in ["menu", "map_select", "lan_search", "ip_input"]:
        _reset_all_prev_press_flags(main_window); return

    # Crucial: Check if Pygame Joystick system is initialized
    if not game_config._joystick_initialized_globally:
        if main_window.render_print_limiter.can_print("joy_sys_not_init_poll_ui"):
            warning("UI Poll: Pygame joystick system not initialized. Skipping UI nav poll.")
        main_window._ui_nav_focus_controller_index = None
        _reset_all_prev_press_flags(main_window)
        return

    if not main_window._pygame_joysticks: # No joysticks detected by AppCore
        main_window._ui_nav_focus_controller_index = None
        _reset_all_prev_press_flags(main_window); return

    pygame.event.pump() # Keep Pygame event queue flowing
    current_time = time.monotonic()
    if current_time - main_window._last_pygame_joy_nav_time < 0.20: return

    navigated_this_poll = False
    action_joystick_index = -1 # Which joystick (0 or 1) performed the action

    for joy_idx, joy in enumerate(main_window._pygame_joysticks):
        if joy_idx > 1: break # Only first two joysticks for UI nav
        if not joy.get_init(): # Ensure this specific joystick object is initialized
            try: joy.init()
            except pygame.error: continue # Skip if it can't be initialized
        if not joy.get_init(): continue

        # Hat Navigation
        JOY_NAV_HAT_ID = 0
        if joy.get_numhats() > JOY_NAV_HAT_ID:
            hat_x, hat_y = joy.get_hat(JOY_NAV_HAT_ID)
            nav_dir_hat = 0
            if hat_y > 0.5: nav_dir_hat = 1; debug(f"Joy {joy_idx} Hat Down")
            elif hat_y < -0.5: nav_dir_hat = -1; debug(f"Joy {joy_idx} Hat Up")
            elif hat_x > 0.5: nav_dir_hat = 2; debug(f"Joy {joy_idx} Hat Right")
            elif hat_x < -0.5: nav_dir_hat = -2; debug(f"Joy {joy_idx} Hat Left")
            if nav_dir_hat != 0:
                grid_nav_val = nav_dir_hat
                if active_ui_element == "map_select":
                    if nav_dir_hat == 2: grid_nav_val = main_window.NUM_MAP_COLUMNS      # Map Right
                    elif nav_dir_hat == -2: grid_nav_val = -main_window.NUM_MAP_COLUMNS # Map Left
                _navigate_current_menu_pygame_joy(main_window, grid_nav_val); navigated_this_poll = True; action_joystick_index = joy_idx; break
        if navigated_this_poll: break

        # Axis Navigation
        JOY_NAV_AXIS_ID_Y = 1; JOY_NAV_AXIS_ID_X = 0; nav_threshold = 0.65
        axis_nav_dir = 0
        # ... (Axis logic from previous response, ensure it uses joy_idx correctly for _pygame_joy_axis_was_active flags)
        if joy.get_numaxes() > JOY_NAV_AXIS_ID_Y: # Vertical Axis
            axis_y_val = joy.get_axis(JOY_NAV_AXIS_ID_Y)
            if axis_y_val > nav_threshold and not main_window._pygame_joy_axis_was_active_pos.get(f"{joy_idx}_y", False): axis_nav_dir = 1
            elif axis_y_val < -nav_threshold and not main_window._pygame_joy_axis_was_active_neg.get(f"{joy_idx}_y", False): axis_nav_dir = -1
            main_window._pygame_joy_axis_was_active_pos[f"{joy_idx}_y"] = axis_y_val > nav_threshold
            main_window._pygame_joy_axis_was_active_neg[f"{joy_idx}_y"] = axis_y_val < -nav_threshold
        if joy.get_numaxes() > JOY_NAV_AXIS_ID_X and axis_nav_dir == 0: # Horizontal Axis
            axis_x_val = joy.get_axis(JOY_NAV_AXIS_ID_X)
            if axis_x_val > nav_threshold and not main_window._pygame_joy_axis_was_active_pos.get(f"{joy_idx}_x", False): axis_nav_dir = 2
            elif axis_x_val < -nav_threshold and not main_window._pygame_joy_axis_was_active_neg.get(f"{joy_idx}_x", False): axis_nav_dir = -2
            main_window._pygame_joy_axis_was_active_pos[f"{joy_idx}_x"] = axis_x_val > nav_threshold
            main_window._pygame_joy_axis_was_active_neg[f"{joy_idx}_x"] = axis_x_val < -nav_threshold
        if axis_nav_dir != 0:
            grid_nav_val_axis = axis_nav_dir
            if active_ui_element == "map_select":
                if axis_nav_dir == 2: grid_nav_val_axis = main_window.NUM_MAP_COLUMNS
                elif axis_nav_dir == -2: grid_nav_val_axis = -main_window.NUM_MAP_COLUMNS
            _navigate_current_menu_pygame_joy(main_window, grid_nav_val_axis); navigated_this_poll = True; action_joystick_index = joy_idx; break
        if navigated_this_poll: break

        # Button Actions
        current_joy_buttons = {i: joy.get_button(i) for i in range(joy.get_numbuttons())}
        prev_joy_buttons = main_window._pygame_joy_button_prev_state[joy_idx]
        joy_mappings_to_use = game_config.get_translated_pygame_joystick_mappings() # Use translated for runtime
        if not joy_mappings_to_use: joy_mappings_to_use = game_config.DEFAULT_PYGAME_JOYSTICK_MAPPINGS

        confirm_mapping = joy_mappings_to_use.get("menu_confirm")
        cancel_mapping = joy_mappings_to_use.get("menu_cancel")
        retry_mapping = joy_mappings_to_use.get("reset") # Assuming 'reset' is for LAN retry

        if confirm_mapping and confirm_mapping.get("type") == "button" and \
           current_joy_buttons.get(confirm_mapping["id"], False) and not prev_joy_buttons.get(confirm_mapping["id"], False):
            if active_ui_element in ["menu", "map_select"]: _activate_current_menu_selected_button_pygame_joy(main_window)
            elif active_ui_element == "lan_search": main_window._join_selected_lan_server_from_dialog()
            elif active_ui_element == "ip_input": _activate_ip_dialog_button(main_window)
            navigated_this_poll = True; action_joystick_index = joy_idx; break
        if cancel_mapping and cancel_mapping.get("type") == "button" and \
           current_joy_buttons.get(cancel_mapping["id"], False) and not prev_joy_buttons.get(cancel_mapping["id"], False):
            if active_ui_element == "menu": main_window.request_close_app()
            elif active_ui_element == "map_select": main_window.show_view("menu")
            elif active_ui_element == "lan_search" and main_window.lan_search_dialog: main_window.lan_search_dialog.reject()
            elif active_ui_element == "ip_input" and main_window.ip_input_dialog: main_window.ip_input_dialog.reject()
            navigated_this_poll = True; action_joystick_index = joy_idx; break
        if active_ui_element == "lan_search" and retry_mapping and retry_mapping.get("type") == "button" and \
           current_joy_buttons.get(retry_mapping["id"], False) and not prev_joy_buttons.get(retry_mapping["id"], False) and \
           main_window.lan_search_dialog and hasattr(main_window.lan_search_dialog, 'button_box'):
            main_window.lan_search_dialog.button_box.button(QDialogButtonBox.StandardButton.Retry).click()
            navigated_this_poll = True; action_joystick_index = joy_idx; break
        if navigated_this_poll: break

    if navigated_this_poll:
        main_window._ui_nav_focus_controller_index = action_joystick_index
        main_window._last_pygame_joy_nav_time = current_time
        _reset_all_prev_press_flags(main_window)
        if 0 <= action_joystick_index < len(main_window._pygame_joysticks):
            joy_acted = main_window._pygame_joysticks[action_joystick_index]
            if joy_acted.get_init(): # Check before getting buttons
                main_window._pygame_joy_button_prev_state[action_joystick_index] = \
                    {i: joy_acted.get_button(i) for i in range(joy_acted.get_numbuttons())}
        _update_current_menu_button_focus(main_window)
        return

    for joy_idx_update, joy_update in enumerate(main_window._pygame_joysticks):
         if joy_idx_update < len(main_window._pygame_joy_button_prev_state) and joy_update.get_init():
             main_window._pygame_joy_button_prev_state[joy_idx_update] = \
                 {i: joy_update.get_button(i) for i in range(joy_update.get_numbuttons())}

def _navigate_current_menu_pygame_joy(main_window: 'MainWindow', direction: int):
    # ... (navigation logic as before, it seemed mostly correct) ...
    buttons_to_nav = main_window._current_active_menu_buttons
    selected_idx_attr_name = main_window._current_active_menu_selected_idx_ref
    if not buttons_to_nav or not hasattr(main_window, selected_idx_attr_name): return
    num_buttons = len(buttons_to_nav); 
    if num_buttons == 0: return
    current_idx = getattr(main_window, selected_idx_attr_name); new_idx = current_idx
    if main_window.current_view_name == "map_select":
        row, col = divmod(current_idx, main_window.NUM_MAP_COLUMNS)
        num_rows = (num_buttons + main_window.NUM_MAP_COLUMNS - 1) // main_window.NUM_MAP_COLUMNS
        if direction == -1 : row = max(0, row - 1) # Up (Vertical list style)
        elif direction == 1: row = min(num_rows - 1, row + 1) # Down (Vertical list style)
        # Horizontal navigation in map select using special direction values
        elif direction == -main_window.NUM_MAP_COLUMNS : row = max(0, row - 1) # Grid Up
        elif direction == main_window.NUM_MAP_COLUMNS : row = min(num_rows-1, row +1) # Grid Down
        elif direction == -2: col = max(0, col - 1) # Left (Horizontal in row)
        elif direction == 2: # Right (Horizontal in row)
            # Calculate max columns for the current row, especially important for the last row
            items_in_this_row = main_window.NUM_MAP_COLUMNS
            if row == num_rows -1: # If it's the last row
                items_in_this_row = num_buttons - (row * main_window.NUM_MAP_COLUMNS)
            col = min(items_in_this_row - 1, col + 1)
        new_idx = row * main_window.NUM_MAP_COLUMNS + col; new_idx = min(num_buttons - 1, max(0, new_idx))
    elif main_window.current_modal_dialog == "lan_search":
        if main_window.lan_servers_list_widget:
            if direction == 1: main_window._lan_search_list_selected_idx = min(main_window.lan_servers_list_widget.count() - 1, main_window._lan_search_list_selected_idx + 1)
            elif direction == -1: main_window._lan_search_list_selected_idx = max(0, main_window._lan_search_list_selected_idx - 1)
            _update_lan_search_list_focus(main_window); return
    elif main_window.current_modal_dialog == "ip_input":
        if direction in [-2, 2]: main_window._ip_dialog_selected_button_idx = 1 - main_window._ip_dialog_selected_button_idx
        _update_ip_dialog_button_focus(main_window); return
    else: new_idx = (current_idx + direction + num_buttons) % num_buttons
    setattr(main_window, selected_idx_attr_name, new_idx)
    _update_current_menu_button_focus(main_window)
    info(f"Menu Nav: Index {new_idx} in UI '{main_window.current_modal_dialog or main_window.current_view_name}' (Dir: {direction})")

def _activate_current_menu_selected_button_pygame_joy(main_window: 'MainWindow'):
    buttons_to_activate = main_window._current_active_menu_buttons
    selected_idx_attr_name = main_window._current_active_menu_selected_idx_ref
    if not buttons_to_activate or not hasattr(main_window, selected_idx_attr_name): return
    current_idx = getattr(main_window, selected_idx_attr_name)
    if not (0 <= current_idx < len(buttons_to_activate)): return
    selected_button = buttons_to_activate[current_idx]
    info(f"Menu Activate: Button '{selected_button.text()}' in view '{main_window.current_view_name}'")
    selected_button.click()

def _reset_all_prev_press_flags(main_window: 'MainWindow'):
    main_window._pygame_joy_axis_was_active_neg.clear()
    main_window._pygame_joy_axis_was_active_pos.clear()
    # _pygame_joy_button_prev_state is handled per joystick in the poll loop

def _activate_ip_dialog_button(main_window: 'MainWindow'):
    if main_window.ip_input_dialog and main_window._ip_dialog_buttons_ref and \
       0 <= main_window._ip_dialog_selected_button_idx < len(main_window._ip_dialog_buttons_ref):
        main_window._ip_dialog_buttons_ref[main_window._ip_dialog_selected_button_idx].click()

def _update_current_menu_button_focus(main_window: 'MainWindow'):
    buttons_to_update = main_window._current_active_menu_buttons
    selected_idx_attr_name = main_window._current_active_menu_selected_idx_ref
    if not buttons_to_update or not hasattr(main_window, selected_idx_attr_name): return
    current_selected_idx = getattr(main_window, selected_idx_attr_name)
    selected_button_widget = None

    # If Pygame joystick system isn't even initialized, or no joysticks attached to AppCore, no custom highlights.
    if not game_config._joystick_initialized_globally or not main_window._pygame_joysticks:
        for i, button in enumerate(buttons_to_update):
            button.setStyleSheet("") # Reset any custom style
            if i == current_selected_idx:
                button.setFocus(Qt.FocusReason.OtherFocusReason)
                selected_button_widget = button
    else:
        focus_color_hex = main_window._p1_ui_focus_color_str
        if main_window._ui_nav_focus_controller_index == 1:
            focus_color_hex = main_window._p2_ui_focus_color_str
        for i, button in enumerate(buttons_to_update):
            is_selected = (i == current_selected_idx)
            if is_selected:
                button.setStyleSheet(f"QPushButton {{ border: 2px solid {focus_color_hex}; background-color: #555; color: white; }} QPushButton:focus {{ outline: none; }}")
                button.setFocus(Qt.FocusReason.OtherFocusReason); selected_button_widget = button
            else: button.setStyleSheet("")

    if selected_button_widget and main_window.current_view_name == "map_select" and main_window.map_select_scroll_area:
        main_window.map_select_scroll_area.ensureWidgetVisible(selected_button_widget, 50, 50)