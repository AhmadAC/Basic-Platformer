# app_ui_creator.py
import os
import sys
import time
from typing import Dict, Optional, Any, List, TYPE_CHECKING

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QDialogButtonBox, QScrollArea, QSizePolicy,
    QListWidget, QListWidgetItem, QApplication, QMessageBox, QLineEdit, QDialog, QLayout
)
from PySide6.QtGui import QFont, QColor # QColor not actively used but kept from original
from PySide6.QtCore import Qt, Slot, QTimer

import pygame # For UI navigation with joystick

import constants as C
import config as game_config
from logger import info, debug, warning, error

if TYPE_CHECKING:
    from app_core import MainWindow
else:
    MainWindow = Any

# --- Helper functions for new UI state ---

def _get_selected_idx_for_source(main_window: 'MainWindow', input_source: str) -> int:
    """Gets the selected button index based on the input source."""
    print(f"MERGE_DEBUG_UI: Getting index for source '{input_source}'")
    if input_source == "keyboard":
        return main_window._keyboard_selected_button_idx
    elif input_source == "controller_0":
        return main_window._controller0_selected_button_idx
    elif input_source == "controller_1":
        return main_window._controller1_selected_button_idx
    elif input_source == "controller_2":
        return main_window._controller2_selected_button_idx
    elif input_source == "controller_3":
        return main_window._controller3_selected_button_idx
    
    active_ui = main_window.current_modal_dialog if main_window.current_modal_dialog else main_window.current_view_name
    if active_ui == "map_select": # map_select has its own primary index
        return main_window._map_selection_selected_button_idx
    
    # Fallback for unhandled sources or contexts for generic menus
    # warning(f"MERGE_DEBUG_UI: _get_selected_idx_for_source: Unknown input_source '{input_source}' in context '{active_ui}', falling back to keyboard index.")
    return main_window._keyboard_selected_button_idx


def _set_selected_idx_for_source(main_window: 'MainWindow', new_idx: int, input_source: str):
    """Sets the selected button index for the given input source and updates global state."""
    print(f"MERGE_DEBUG_UI: Setting index for source '{input_source}' to {new_idx}")
    if input_source == "keyboard":
        main_window._keyboard_selected_button_idx = new_idx
    elif input_source == "controller_0":
        main_window._controller0_selected_button_idx = new_idx
    elif input_source == "controller_1":
        main_window._controller1_selected_button_idx = new_idx
    elif input_source == "controller_2":
        main_window._controller2_selected_button_idx = new_idx
    elif input_source == "controller_3":
        main_window._controller3_selected_button_idx = new_idx
    else:
        # warning(f"MERGE_DEBUG_UI: _set_selected_idx_for_source: Unknown input_source '{input_source}', attempting to set keyboard index.")
        main_window._keyboard_selected_button_idx = new_idx 

    main_window._last_active_input_source = input_source
    if input_source == "keyboard":
        main_window._ui_nav_focus_controller_index = -1
    elif input_source.startswith("controller_"):
        try:
            controller_ui_idx = int(input_source.split("_")[1])
            main_window._ui_nav_focus_controller_index = controller_ui_idx
        except (IndexError, ValueError):
            warning(f"MERGE_DEBUG_UI: Could not parse controller index from {input_source}. Setting UI focus to keyboard.")
            main_window._ui_nav_focus_controller_index = -1 
    else: 
        main_window._ui_nav_focus_controller_index = -1 


# --- UI Element Creation Functions (mostly unchanged) ---
def _create_main_menu_widget(main_window: 'MainWindow') -> QWidget:
    main_window._main_menu_buttons_ref = []
    menu_widget = QWidget(); layout = QVBoxLayout(menu_widget)
    layout.setAlignment(Qt.AlignmentFlag.AlignCenter); layout.setSpacing(15)
    title_label = QLabel("Platformer Adventure LAN"); title_label.setFont(main_window.fonts["large"])
    title_label.setAlignment(Qt.AlignmentFlag.AlignCenter); layout.addWidget(title_label)
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
        button = QPushButton(text); button.setFont(main_window.fonts["medium"]); button.setMinimumHeight(40)
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
    if not isinstance(main_window.map_buttons_layout, QGridLayout): error("Map buttons layout is not QGridLayout"); return
    _clear_layout(main_window.map_buttons_layout) 
    
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

def _clear_layout(layout: Optional[QLayout]):
    if layout is not None:
        while layout.count():
            item = layout.takeAt(0)
            if item:
                widget = item.widget()
                if widget:
                    widget.setParent(None) 
                    widget.deleteLater()
                else:
                    sub_layout = item.layout()
                    if sub_layout:
                        _clear_layout(sub_layout)

def _ensure_editor_instance(main_window: 'MainWindow'):
    from PySide6.QtWidgets import QMainWindow as EditorMainWindowType
    if main_window.actual_editor_module_instance and \
       main_window.actual_editor_module_instance.parent() is main_window.editor_content_container:
        return 

    _clear_layout(main_window.editor_content_container.layout()) 

    if main_window.actual_editor_module_instance is None or \
       not isinstance(main_window.actual_editor_module_instance, EditorMainWindowType):
        info("UI_VIEWS: Creating and embedding editor instance.")
        try:
            from editor.editor import editor_main
            instance = editor_main(parent_app_instance=QApplication.instance(), embed_mode=True)
            if not instance or not isinstance(instance, EditorMainWindowType):
                error("Failed to get QMainWindow editor instance."); _add_placeholder_to_content_area(main_window, main_window.editor_content_container, "Error: Editor load failed."); return
            main_window.actual_editor_module_instance = instance
        except Exception as e: error(f"Exception creating editor: {e}", exc_info=True); _add_placeholder_to_content_area(main_window, main_window.editor_content_container, f"Error: {e}"); main_window.actual_editor_module_instance = None; return
    
    if main_window.actual_editor_module_instance:
        if main_window.actual_editor_module_instance.parent() is not None:
            main_window.actual_editor_module_instance.setParent(None) 
        main_window.editor_content_container.layout().addWidget(main_window.actual_editor_module_instance)
        main_window.actual_editor_module_instance.setParent(main_window.editor_content_container) 
        info("UI_VIEWS: Editor instance embedded.")


def _ensure_controls_settings_instance(main_window: 'MainWindow'):
    from controller_settings.controller_mapper_gui import ControllerSettingsWindow
    if main_window.actual_controls_settings_instance and \
       main_window.actual_controls_settings_instance.parent() is main_window.settings_content_container:
        if hasattr(main_window.actual_controls_settings_instance, 'load_settings_into_ui'):
             main_window.actual_controls_settings_instance.load_settings_into_ui()
        return

    _clear_layout(main_window.settings_content_container.layout()) 

    if main_window.actual_controls_settings_instance is None or \
       not isinstance(main_window.actual_controls_settings_instance, ControllerSettingsWindow) :
        info("UI_VIEWS: Creating ControllerSettingsWindow instance.")
        try:
            game_config.load_config()
            instance = ControllerSettingsWindow(parent=main_window.settings_content_container)
            main_window.actual_controls_settings_instance = instance
        except ImportError as e_imp: error(f"ImportError ControllerSettingsWindow: {e_imp}", exc_info=True); _add_placeholder_to_content_area(main_window, main_window.settings_content_container, f"Error: {e_imp}"); main_window.actual_controls_settings_instance = None; return
        except Exception as e: error(f"Exception ControllerSettingsWindow: {e}", exc_info=True); _add_placeholder_to_content_area(main_window, main_window.settings_content_container, f"Error: {e}"); main_window.actual_controls_settings_instance = None; return
    
    if main_window.actual_controls_settings_instance:
        if main_window.actual_controls_settings_instance.parent() is not None :
             main_window.actual_controls_settings_instance.setParent(None)
        main_window.settings_content_container.layout().addWidget(main_window.actual_controls_settings_instance)
        main_window.actual_controls_settings_instance.setParent(main_window.settings_content_container) 
        if hasattr(main_window.actual_controls_settings_instance, 'load_settings_into_ui'): main_window.actual_controls_settings_instance.load_settings_into_ui()
        info("UI_VIEWS: ControllerSettingsWindow embedded.")


def _add_placeholder_to_content_area(main_window: 'MainWindow', container: QWidget, msg: str):
    _clear_layout(container.layout()) 
    lbl = QLabel(msg); lbl.setAlignment(Qt.AlignmentFlag.AlignCenter); lbl.setFont(main_window.fonts["medium"])
    if container.layout(): container.layout().addWidget(lbl)
    else: 
        temp_layout = QVBoxLayout(container); temp_layout.addWidget(lbl); container.setLayout(temp_layout)


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
    
    focus_color_str = main_window._keyboard_ui_focus_color_str 
    active_source = main_window._last_active_input_source

    if active_source == "keyboard":
        focus_color_str = main_window._keyboard_ui_focus_color_str
    elif active_source == "controller_0":
        focus_color_str = main_window._p1_ui_focus_color_str
    elif active_source == "controller_1":
        focus_color_str = main_window._p2_ui_focus_color_str
    elif active_source == "controller_2": # New for P3
        focus_color_str = main_window._p3_ui_focus_color_str
    elif active_source == "controller_3": # New for P4
        focus_color_str = main_window._p4_ui_focus_color_str
    
    for i, button in enumerate(main_window._ip_dialog_buttons_ref):
        is_selected = (i == main_window._ip_dialog_selected_button_idx)
        button.setStyleSheet(f"QPushButton {{ border: 2px solid {focus_color_str}; background-color: #555; color: white; }} QPushButton:focus {{ outline: none; }}" if is_selected else "")
        if is_selected: button.setFocus(Qt.FocusReason.OtherFocusReason)

# --- UI Navigation Functions (Updated) ---

def _poll_pygame_joysticks_for_ui_navigation(main_window: 'MainWindow'):
    active_ui_element = main_window.current_modal_dialog if main_window.current_modal_dialog else main_window.current_view_name
    if active_ui_element not in ["menu", "map_select", "lan_search", "ip_input"]:
        _reset_all_prev_press_flags(main_window); return

    if not game_config._joystick_initialized_globally:
        if main_window.render_print_limiter.can_print("joy_sys_not_init_poll_ui_creator"):
            warning("UI Poll Creator: Pygame joystick system not globally initialized. Skipping UI nav poll.")
        if main_window._last_active_input_source != "keyboard": 
             main_window._last_active_input_source = "keyboard"
             main_window._ui_nav_focus_controller_index = -1
             _update_current_menu_button_focus(main_window)
        _reset_all_prev_press_flags(main_window); return
    
    if not main_window._pygame_joysticks: 
        if main_window._last_active_input_source != "keyboard":
            main_window._last_active_input_source = "keyboard"
            main_window._ui_nav_focus_controller_index = -1
            _update_current_menu_button_focus(main_window)
        _reset_all_prev_press_flags(main_window); return

    try: pygame.event.pump()
    except pygame.error as e_pump: warning(f"UI Poll Creator: Pygame event pump error: {e_pump}"); return

    current_time = time.monotonic()
    if current_time - main_window._last_pygame_joy_nav_time < 0.20: return 

    navigated_this_poll = False
    action_input_source: Optional[str] = None 

    for ui_controller_idx, joy in enumerate(main_window._pygame_joysticks):
        # Your original code had: if ui_controller_idx > 1: break 
        # This is retained for now. If you want all 4 UI joysticks to navigate, remove this line.
        if ui_controller_idx > 1: 
            # print(f"MERGE_DEBUG_UI: Poll skipping UI joystick index {ui_controller_idx} due to >1 limit.")
            break
        
        if not joy.get_init():
            try: joy.init()
            except pygame.error: continue
        if not joy.get_init(): continue 

        joy_instance_id = joy.get_instance_id() 

        JOY_NAV_HAT_ID = 0; nav_dir_hat = 0
        if joy.get_numhats() > JOY_NAV_HAT_ID:
            hat_x, hat_y = joy.get_hat(JOY_NAV_HAT_ID)
            if hat_y > 0.5: nav_dir_hat = 1    
            elif hat_y < -0.5: nav_dir_hat = -1 
            elif hat_x > 0.5: nav_dir_hat = 2   
            elif hat_x < -0.5: nav_dir_hat = -2 
            
            if nav_dir_hat != 0:
                grid_nav_val = nav_dir_hat
                if active_ui_element == "map_select": # Map select uses specific interpretation
                    if nav_dir_hat == 2: grid_nav_val = 1 # Map to simple column right
                    elif nav_dir_hat == -2: grid_nav_val = -1 # Map to simple column left
                    # For Up/Down (-1, 1), they are fine for row changes.
                elif active_ui_element == "ip_input" and nav_dir_hat not in [-2, 2]: 
                    continue 
                
                action_input_source = f"controller_{ui_controller_idx}"
                _navigate_current_menu_pygame_joy(main_window, grid_nav_val, action_input_source)
                navigated_this_poll = True
                break 
        if navigated_this_poll: break

        JOY_NAV_AXIS_ID_Y = 1; JOY_NAV_AXIS_ID_X = 0; nav_threshold = 0.65; axis_nav_dir = 0
        axis_key_y = f"{joy_instance_id}_y" 
        axis_key_x = f"{joy_instance_id}_x"

        if joy.get_numaxes() > JOY_NAV_AXIS_ID_Y:
            axis_y_val = joy.get_axis(JOY_NAV_AXIS_ID_Y)
            if axis_y_val > nav_threshold and not main_window._pygame_joy_axis_was_active_pos.get(axis_key_y, False): axis_nav_dir = 1    
            elif axis_y_val < -nav_threshold and not main_window._pygame_joy_axis_was_active_neg.get(axis_key_y, False): axis_nav_dir = -1 
            main_window._pygame_joy_axis_was_active_pos[axis_key_y] = axis_y_val > nav_threshold
            main_window._pygame_joy_axis_was_active_neg[axis_key_y] = axis_y_val < -nav_threshold
        
        if joy.get_numaxes() > JOY_NAV_AXIS_ID_X and axis_nav_dir == 0: 
            axis_x_val = joy.get_axis(JOY_NAV_AXIS_ID_X)
            if axis_x_val > nav_threshold and not main_window._pygame_joy_axis_was_active_pos.get(axis_key_x, False): axis_nav_dir = 2   
            elif axis_x_val < -nav_threshold and not main_window._pygame_joy_axis_was_active_neg.get(axis_key_x, False): axis_nav_dir = -2 
            main_window._pygame_joy_axis_was_active_pos[axis_key_x] = axis_x_val > nav_threshold
            main_window._pygame_joy_axis_was_active_neg[axis_key_x] = axis_x_val < -nav_threshold
            
        if axis_nav_dir != 0:
            grid_nav_val_axis = axis_nav_dir
            if active_ui_element == "map_select":
                if axis_nav_dir == 2: grid_nav_val_axis = 1 
                elif axis_nav_dir == -2: grid_nav_val_axis = -1
            elif active_ui_element == "ip_input" and axis_nav_dir not in [-2,2]: 
                continue
            
            action_input_source = f"controller_{ui_controller_idx}"
            _navigate_current_menu_pygame_joy(main_window, grid_nav_val_axis, action_input_source)
            navigated_this_poll = True
            break
        if navigated_this_poll: break

        if joy_instance_id >= len(main_window._pygame_joy_button_prev_state):
            warning(f"MERGE_DEBUG_UI: joy_instance_id {joy_instance_id} out of bounds for _pygame_joy_button_prev_state (len {len(main_window._pygame_joy_button_prev_state)}). Skipping button press check for this joystick.")
            continue

        current_joy_buttons = {i: joy.get_button(i) for i in range(joy.get_numbuttons())}
        prev_joy_buttons = main_window._pygame_joy_button_prev_state[joy_instance_id] 

        joy_mappings_to_use = game_config.get_translated_pygame_joystick_mappings() 
        if not joy_mappings_to_use: joy_mappings_to_use = game_config.DEFAULT_PYGAME_JOYSTICK_MAPPINGS
        
        confirm_mapping = joy_mappings_to_use.get("menu_confirm"); 
        cancel_mapping = joy_mappings_to_use.get("menu_cancel"); 
        retry_mapping = joy_mappings_to_use.get("reset") 

        action_input_source_for_button = f"controller_{ui_controller_idx}"

        if confirm_mapping and confirm_mapping.get("type") == "button" and \
           current_joy_buttons.get(confirm_mapping["id"], False) and \
           not prev_joy_buttons.get(confirm_mapping["id"], False):
            if active_ui_element in ["menu", "map_select"]: 
                _activate_current_menu_selected_button_pygame_joy(main_window, action_input_source_for_button)
            elif active_ui_element == "lan_search": main_window._join_selected_lan_server_from_dialog()
            elif active_ui_element == "ip_input": _activate_ip_dialog_button(main_window)
            navigated_this_poll = True; action_input_source = action_input_source_for_button; break
        
        if cancel_mapping and cancel_mapping.get("type") == "button" and \
           current_joy_buttons.get(cancel_mapping["id"], False) and \
           not prev_joy_buttons.get(cancel_mapping["id"], False):
            if active_ui_element == "menu": main_window.request_close_app()
            elif active_ui_element == "map_select": main_window.show_view("menu")
            elif active_ui_element == "lan_search" and main_window.lan_search_dialog: main_window.lan_search_dialog.reject()
            elif active_ui_element == "ip_input" and main_window.ip_input_dialog: main_window.ip_input_dialog.reject()
            navigated_this_poll = True; action_input_source = action_input_source_for_button; break
            
        if active_ui_element == "lan_search" and retry_mapping and retry_mapping.get("type") == "button" and \
           current_joy_buttons.get(retry_mapping["id"], False) and \
           not prev_joy_buttons.get(retry_mapping["id"], False) and \
           main_window.lan_search_dialog and hasattr(main_window.lan_search_dialog, 'button_box'):
            main_window.lan_search_dialog.button_box.button(QDialogButtonBox.StandardButton.Retry).click()
            navigated_this_poll = True; action_input_source = action_input_source_for_button; break
        
        if navigated_this_poll: break 

    if navigated_this_poll and action_input_source:
        main_window._last_pygame_joy_nav_time = current_time
        _reset_all_prev_press_flags(main_window) 

        main_window._last_active_input_source = action_input_source
        try:
            main_window._ui_nav_focus_controller_index = int(action_input_source.split("_")[1])
        except (IndexError, ValueError):
            main_window._ui_nav_focus_controller_index = -1 

        acted_joy_instance_id = -1
        if action_input_source.startswith("controller_"):
            try:
                acted_ui_idx = int(action_input_source.split("_")[1])
                if 0 <= acted_ui_idx < len(main_window._pygame_joysticks):
                    acted_joy_object = main_window._pygame_joysticks[acted_ui_idx]
                    if acted_joy_object.get_init():
                        acted_joy_instance_id = acted_joy_object.get_instance_id()
            except (ValueError, IndexError):
                pass
        
        if acted_joy_instance_id != -1 and acted_joy_instance_id < len(main_window._pygame_joy_button_prev_state):
            # It's better to re-fetch the joystick by its instance_id to ensure we have the current object
            # especially if joysticks can be unplugged/replugged, though _refresh_appcore_joystick_list handles that.
            # For now, assuming the joy object from main_window._pygame_joysticks is still valid.
            joy_to_update_state_for = None
            for j_obj in game_config.get_joystick_objects(): # Find the joystick by instance ID from the full list
                if j_obj and j_obj.get_instance_id() == acted_joy_instance_id:
                    joy_to_update_state_for = j_obj
                    break
            
            if joy_to_update_state_for and joy_to_update_state_for.get_init():
                 main_window._pygame_joy_button_prev_state[acted_joy_instance_id] = {i: joy_to_update_state_for.get_button(i) for i in range(joy_to_update_state_for.get_numbuttons())}

        _update_current_menu_button_focus(main_window)
        return 

    for joy_obj_for_state_update in game_config.get_joystick_objects(): 
        if joy_obj_for_state_update and joy_obj_for_state_update.get_init():
            instance_id = joy_obj_for_state_update.get_instance_id()
            if instance_id < len(main_window._pygame_joy_button_prev_state):
                 main_window._pygame_joy_button_prev_state[instance_id] = {i: joy_obj_for_state_update.get_button(i) for i in range(joy_obj_for_state_update.get_numbuttons())}


def _navigate_current_menu_pygame_joy(main_window: 'MainWindow', direction: int, input_source: str):
    print(f"MERGE_DEBUG_UI: Navigate: dir={direction}, source='{input_source}'")
    active_ui = main_window.current_modal_dialog if main_window.current_modal_dialog else main_window.current_view_name

    if active_ui == "map_select":
        buttons_to_nav = main_window._map_selection_buttons_ref
        current_idx = main_window._map_selection_selected_button_idx 
        if not buttons_to_nav: return
        num_buttons = len(buttons_to_nav)
        if num_buttons == 0: return
        
        new_idx = current_idx
        row, col = divmod(current_idx, main_window.NUM_MAP_COLUMNS)
        num_rows = (num_buttons + main_window.NUM_MAP_COLUMNS - 1) // main_window.NUM_MAP_COLUMNS

        if direction == -1 : row = max(0, row - 1) 
        elif direction == 1: row = min(num_rows - 1, row + 1) 
        # The poll function now sends simple -1 (left) or 1 (right) for map column changes
        elif direction == -1 and active_ui == "map_select": # Left (interpret -1 also as left if not handled by row logic)
             col = max(0, col - 1)
        elif direction == 1 and active_ui == "map_select": # Right (interpret 1 also as right if not handled by row logic)
            # Ensure items_in_this_row is calculated correctly
            items_in_last_full_row = (num_rows -1) * main_window.NUM_MAP_COLUMNS if num_rows > 0 else 0
            items_in_this_row = main_window.NUM_MAP_COLUMNS if row < num_rows - 1 else (num_buttons - items_in_last_full_row)

            if items_in_this_row <= 0 and num_buttons > 0: # Should not happen if num_buttons > 0
                items_in_this_row = main_window.NUM_MAP_COLUMNS # Fallback, unlikely needed
            col = min(items_in_this_row - 1, col + 1) if items_in_this_row > 0 else 0

        new_idx = row * main_window.NUM_MAP_COLUMNS + col
        new_idx = min(num_buttons - 1, max(0, new_idx))
        main_window._map_selection_selected_button_idx = new_idx
        _set_selected_idx_for_source(main_window, new_idx, input_source) 
        
    elif active_ui == "lan_search":
        if main_window.lan_servers_list_widget:
            current_lan_idx = main_window._lan_search_list_selected_idx if main_window._lan_search_list_selected_idx != -1 else 0
            if main_window.lan_servers_list_widget.count() > 0:
                if direction == 1: new_lan_idx = min(main_window.lan_servers_list_widget.count() - 1, current_lan_idx + 1)
                elif direction == -1: new_lan_idx = max(0, current_lan_idx - 1)
                else: new_lan_idx = current_lan_idx 
                main_window._lan_search_list_selected_idx = new_lan_idx
            _update_lan_search_list_focus(main_window)
            if input_source.startswith("controller_"):
                 _set_selected_idx_for_source(main_window, main_window._lan_search_list_selected_idx, input_source)
            return 
            
    elif active_ui == "ip_input":
        if direction in [-2, 2, -1, 1]: 
            main_window._ip_dialog_selected_button_idx = 1 - main_window._ip_dialog_selected_button_idx
        _update_ip_dialog_button_focus(main_window) 
        if input_source.startswith("controller_"):
             _set_selected_idx_for_source(main_window, main_window._ip_dialog_selected_button_idx, input_source)
        return

    else: 
        buttons_to_nav = main_window._current_active_menu_buttons
        if not buttons_to_nav: return
        num_buttons = len(buttons_to_nav)
        if num_buttons == 0: return

        current_idx = _get_selected_idx_for_source(main_window, input_source)
        new_idx = current_idx

        actual_direction = 0
        if direction == -1: actual_direction = -1 
        elif direction == 1: actual_direction = 1  
        elif direction == -2: actual_direction = -1 # Map Left to Up for simple lists
        elif direction == 2: actual_direction = 1  # Map Right to Down for simple lists
        
        if actual_direction != 0:
            new_idx = (current_idx + actual_direction + num_buttons) % num_buttons
        
        _set_selected_idx_for_source(main_window, new_idx, input_source)

    _update_current_menu_button_focus(main_window)


def _activate_current_menu_selected_button_pygame_joy(main_window: 'MainWindow', input_source: str):
    print(f"MERGE_DEBUG_UI: Activate: source='{input_source}'")
    active_ui = main_window.current_modal_dialog if main_window.current_modal_dialog else main_window.current_view_name
    
    buttons_to_activate: List[QPushButton] = [] # Ensure it's typed
    current_idx = -1

    if active_ui == "map_select":
        buttons_to_activate = main_window._map_selection_buttons_ref
        current_idx = main_window._map_selection_selected_button_idx
    elif active_ui == "menu": 
        buttons_to_activate = main_window._main_menu_buttons_ref
        current_idx = _get_selected_idx_for_source(main_window, input_source)
    else: # Should not be called for other UIs if _poll is correct
        warning(f"MERGE_DEBUG_UI: _activate called for unexpected UI '{active_ui}'")
        return


    if not buttons_to_activate: 
        warning(f"MERGE_DEBUG_UI: No buttons to activate for UI: {active_ui}"); return
    if not (0 <= current_idx < len(buttons_to_activate)): 
        warning(f"MERGE_DEBUG_UI: Activation index {current_idx} out of bounds for {len(buttons_to_activate)} buttons."); return
    
    selected_button = buttons_to_activate[current_idx]
    selected_button.click()

def _reset_all_prev_press_flags(main_window: 'MainWindow'):
    main_window._pygame_joy_axis_was_active_neg.clear()
    main_window._pygame_joy_axis_was_active_pos.clear()

def _activate_ip_dialog_button(main_window: 'MainWindow'):
    if main_window.ip_input_dialog and main_window._ip_dialog_buttons_ref and \
       0 <= main_window._ip_dialog_selected_button_idx < len(main_window._ip_dialog_buttons_ref):
        main_window._ip_dialog_buttons_ref[main_window._ip_dialog_selected_button_idx].click()

def _update_current_menu_button_focus(main_window: 'MainWindow'):
    active_ui = main_window.current_modal_dialog if main_window.current_modal_dialog else main_window.current_view_name
    if active_ui not in ["menu", "map_select"]: return

    buttons_to_update: List[QPushButton] = []
    current_selected_idx = -1
    
    input_source_for_styling = main_window._last_active_input_source

    if active_ui == "menu":
        buttons_to_update = main_window._main_menu_buttons_ref
        current_selected_idx = _get_selected_idx_for_source(main_window, input_source_for_styling)
    elif active_ui == "map_select":
        buttons_to_update = main_window._map_selection_buttons_ref
        current_selected_idx = main_window._map_selection_selected_button_idx 
    else:
        return

    if not buttons_to_update: return
    
    # Ensure current_selected_idx is valid, default to 0 if not
    if not (0 <= current_selected_idx < len(buttons_to_update)):
        if len(buttons_to_update) > 0:
            current_selected_idx = 0
            if active_ui == "menu":
                _set_selected_idx_for_source(main_window, 0, input_source_for_styling)
            elif active_ui == "map_select":
                main_window._map_selection_selected_button_idx = 0
        else:
            return # No buttons to focus

    selected_button_widget = None
    focus_color_hex = main_window._keyboard_ui_focus_color_str 

    if input_source_for_styling == "keyboard":
        focus_color_hex = main_window._keyboard_ui_focus_color_str
    elif input_source_for_styling == "controller_0":
        focus_color_hex = main_window._p1_ui_focus_color_str
    elif input_source_for_styling == "controller_1":
        focus_color_hex = main_window._p2_ui_focus_color_str
    elif input_source_for_styling == "controller_2":
        focus_color_hex = main_window._p3_ui_focus_color_str
    elif input_source_for_styling == "controller_3":
        focus_color_hex = main_window._p4_ui_focus_color_str
    
    for i, button in enumerate(buttons_to_update):
        is_selected = (i == current_selected_idx)
        if is_selected:
            button.setStyleSheet(f"QPushButton {{ border: 2px solid {focus_color_hex}; background-color: #555; color: white; }} QPushButton:focus {{ outline: none; }}")
            button.setFocus(Qt.FocusReason.OtherFocusReason); selected_button_widget = button
        else:
            button.setStyleSheet("") 

    if selected_button_widget and main_window.current_view_name == "map_select" and main_window.map_select_scroll_area:
        main_window.map_select_scroll_area.ensureWidgetVisible(selected_button_widget, 50, 50)