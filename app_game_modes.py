# app_game_modes.py
import os
import sys # Added sys import
import time
from typing import Dict, Optional, Any, List
from PySide6.QtCore import Qt

from PySide6.QtWidgets import QApplication, QMessageBox, QDialog, QDialogButtonBox,QWidget, QListWidgetItem
from PySide6.QtCore import Slot, QThread, Signal

from logger import info, debug, warning, error, critical
import constants as C
from game_setup import initialize_game_elements
from game_state_manager import reset_game_state
from server_logic import ServerState, run_server_mode
from client_logic import ClientState, run_client_mode, find_server_on_lan

from app_ui_creator import (
    _show_status_dialog, _update_status_dialog, _close_status_dialog,
    _show_lan_search_dialog, _update_lan_search_list_focus
)
from game_ui import SelectMapDialog, IPInputDialog


# Forward declaration for MainWindow type hint
if sys.version_info >= (3,9):
    from typing import TYPE_CHECKING
    if TYPE_CHECKING:
        from app_core import MainWindow, NetworkThread # Import NetworkThread here too for type hint
else:
    MainWindow = Any
    NetworkThread = Any # Fallback type for NetworkThread


# These are the actual logic functions called by MainWindow's event handlers
def start_couch_play_actual(main_window: 'MainWindow'): # Renamed from on_start_couch_play
    if main_window.map_select_title_label: main_window.map_select_title_label.setText("Select Map for Couch Co-op")
    main_window._populate_map_list_for_selection("couch_coop")
    main_window.show_view("map_select")

def start_host_game_actual(main_window: 'MainWindow'): # Renamed from on_start_host_game
    if main_window.map_select_title_label: main_window.map_select_title_label.setText("Select Map to Host")
    main_window._populate_map_list_for_selection("host_game")
    main_window.show_view("map_select")

def start_join_lan_actual(main_window: 'MainWindow'): # Renamed from on_start_join_lan
    _show_lan_search_dialog(main_window)

def start_join_ip_actual(main_window: 'MainWindow'): # Renamed from on_start_join_ip
    main_window.ip_input_dialog = IPInputDialog(parent=main_window)
    main_window._ip_dialog_buttons_ref = [
        main_window.ip_input_dialog.button_box.button(QDialogButtonBox.StandardButton.Ok),
        main_window.ip_input_dialog.button_box.button(QDialogButtonBox.StandardButton.Cancel)
    ]
    main_window._ip_dialog_selected_button_idx = 0
    main_window.current_modal_dialog = "ip_input"
    main_window._update_ip_dialog_button_focus()
    if main_window.ip_input_dialog.exec() == QDialog.DialogCode.Accepted and main_window.ip_input_dialog.ip_port_string:
        prepare_and_start_game_logic(main_window, "join_ip", target_ip_port=main_window.ip_input_dialog.ip_port_string)
    else:
        info("Join by IP cancelled."); main_window.show_view("menu")
    main_window.current_modal_dialog = None; main_window._ip_dialog_buttons_ref.clear()

# This is the one called by MainWindow._on_map_selected_for_couch_coop
def start_couch_play_logic(main_window: 'MainWindow', selected_map_name: str):
    info(f"GAME_MODES: Starting Couch Co-op with map: {selected_map_name}")
    prepare_and_start_game_logic(main_window, "couch_play", map_name=selected_map_name)

# This is the one called by MainWindow._on_map_selected_for_host_game
def start_host_game_logic(main_window: 'MainWindow', selected_map_name: str):
    info(f"GAME_MODES: Starting Host Game (waiting) with map: {selected_map_name}")
    prepare_and_start_game_logic(main_window, "host_waiting", map_name=selected_map_name)


def _select_map_dialog_legacy(main_window: 'MainWindow') -> Optional[str]:
    dialog = SelectMapDialog(main_window.fonts, main_window)
    if dialog.exec() == QDialog.DialogCode.Accepted: return dialog.selected_map_name
    return None

def prepare_and_start_game_logic(main_window: 'MainWindow', mode: str, map_name: Optional[str] = None, target_ip_port: Optional[str] = None): # Renamed from _prepare_and_start_game
    info(f"Preparing to start game mode: {mode}, Map: {map_name}, Target: {target_ip_port}")
    main_window_size = main_window.size()
    initial_hint_width, initial_hint_height = main_window_size.width(), main_window_size.height()
    if initial_hint_width <= 100 or initial_hint_height <= 100:
        initial_hint_width, initial_hint_height = main_window.initial_main_window_width, main_window.initial_main_window_height
        info(f"Window size small, using defaults for game init hint: {initial_hint_width}x{initial_hint_height}")
    else:
        info(f"Window size for game init hint: {initial_hint_width}x{initial_hint_height}")
    
    if map_name is None and mode not in ["join_ip", "join_lan"]:
        map_name = getattr(C, 'DEFAULT_LEVEL_MODULE_NAME', "level_default")

    initialized_elements = initialize_game_elements(
        initial_hint_width, initial_hint_height, mode, None,
        map_name if mode not in ["join_ip", "join_lan"] else None
    )
    if initialized_elements is None:
        QMessageBox.critical(main_window, "Error", f"Failed to init game elements for {mode}, map '{map_name}'.")
        main_window.show_view("menu"); return
    
    main_window.game_elements.clear(); main_window.game_elements.update(initialized_elements)
    main_window.game_elements['current_game_mode'] = mode; main_window.current_game_mode = mode
    main_window.setWindowTitle(f"Platformer - {mode.replace('_',' ').title()}")
    
    main_window.show_view("game_scene")
    QApplication.processEvents()

    camera = main_window.game_elements.get("camera")
    if camera and hasattr(camera, 'set_screen_dimensions') and hasattr(camera, 'set_level_dimensions'):
        game_scene_w = main_window.game_scene_widget.width()
        game_scene_h = main_window.game_scene_widget.height()
        if game_scene_w <=1 or game_scene_h <=1 :
            game_scene_w = initial_hint_width; game_scene_h = initial_hint_height
            warning(f"GameSceneWidget size invalid after show_view. Using hints: {game_scene_w}x{game_scene_h}")
        
        info(f"Setting camera screen dimensions to actual GameSceneWidget size: {game_scene_w}x{game_scene_h}")
        camera.set_screen_dimensions(float(game_scene_w), float(game_scene_h))
        
        if "level_pixel_width" in main_window.game_elements:
            camera.set_level_dimensions(
                main_window.game_elements["level_pixel_width"],
                main_window.game_elements.get("level_min_x_absolute", 0.0),
                main_window.game_elements.get("level_min_y_absolute", 0.0),
                main_window.game_elements.get("level_max_y_absolute", game_scene_h)
            )
        p1_cam = main_window.game_elements.get("player1")
        if p1_cam and hasattr(camera, 'update'): camera.update(p1_cam)
    
    main_window.game_scene_widget.update_game_state(0)
    
    if mode == "host_waiting": start_network_mode_logic(main_window, "host_listen_only")
    elif mode in ["host", "join_lan", "join_ip"]: start_network_mode_logic(main_window, mode, target_ip_port)
    info(f"Game mode '{mode}' prepared.")

def on_client_fully_synced_for_host_logic(main_window: 'MainWindow'): # Renamed from on_client_fully_synced_for_host_external
    info("APP_GAME_MODES: Client is fully synced with Host. Resetting game state for multiplayer.")
    if main_window.current_game_mode == "host_waiting":
        reset_game_state(main_window.game_elements)
        main_window.current_game_mode = "host"
        info("APP_GAME_MODES: Game state reset. Host mode now active for multiplayer.")
        main_window.setWindowTitle(f"Platformer Adventure LAN - Host (Multiplayer)")
    else:
        warning("on_client_fully_synced_for_host_logic called but not in 'host_waiting' mode.")

def start_network_mode_logic(main_window: 'MainWindow', mode_name: str, target_ip_port: Optional[str] = None): # Renamed from _start_network_mode
    if main_window.network_thread and main_window.network_thread.isRunning():
        warning("NetworkThread already running."); main_window.network_thread.quit(); main_window.network_thread.wait(1000); main_window.network_thread = None
    
    NetworkThreadType = main_window.NetworkThread

    if mode_name == "host_listen_only":
        main_window.server_state = ServerState()
        main_window.server_state.current_map_name = main_window.game_elements.get("loaded_map_name", "unknown_map")
        main_window.network_thread = NetworkThreadType("host", main_window.game_elements, main_window.server_state, parent=main_window)
        main_window.network_thread.client_fully_synced_signal.connect(lambda: on_client_fully_synced_for_host_logic(main_window))
    elif mode_name == "host":
        if not main_window.server_state: main_window.server_state = ServerState(); main_window.server_state.current_map_name = main_window.game_elements.get("loaded_map_name", "unknown_map")
        if not (main_window.network_thread and main_window.network_thread.isRunning()):
            main_window.network_thread = NetworkThreadType("host", main_window.game_elements, main_window.server_state, parent=main_window)
            main_window.network_thread.client_fully_synced_signal.connect(lambda: on_client_fully_synced_for_host_logic(main_window))
    elif mode_name in ["join_lan", "join_ip"]:
        main_window.client_state = ClientState()
        main_window.network_thread = NetworkThreadType("join", main_window.game_elements, client_state_ref=main_window.client_state, target_ip_port=target_ip_port, parent=main_window)
    
    if main_window.network_thread and not main_window.network_thread.isRunning():
        main_window.network_thread.status_update_signal.connect(main_window.on_network_status_update_slot)
        main_window.network_thread.operation_finished_signal.connect(main_window.on_network_operation_finished_slot)
        main_window.network_thread.start()
        if mode_name != "host_listen_only": _show_status_dialog(main_window, "Network Operation", f"Initializing {mode_name} mode...")
    elif not main_window.network_thread and mode_name != "host_listen_only":
        error(f"Failed to create/start NetworkThread for {mode_name}"); QMessageBox.critical(main_window, "Network Error", f"Could not start {mode_name} mode."); main_window.show_view("menu")

def on_network_status_update_logic(main_window: 'MainWindow', title: str, message: str, progress: float): # Renamed
    is_hosting_waiting = (main_window.current_game_mode == "host_waiting")
    show_dialog_now = not (main_window.status_dialog and main_window.status_dialog.isVisible()) and \
                      (not is_hosting_waiting or (is_hosting_waiting and "Player 2 needs" in message))
    if show_dialog_now: _show_status_dialog(main_window, title, message)
    if main_window.status_dialog and main_window.status_dialog.isVisible(): _update_status_dialog(main_window, message, progress)
    if title in ["game_starting", "game_active"] or (title == "Map Sync" and "Player 2 has" in message and "Ready" in message and progress >= 99.9):
        _close_status_dialog(main_window)

def on_network_operation_finished_logic(main_window: 'MainWindow', message: str): # Renamed
    info(f"Network operation finished: {message}"); _close_status_dialog(main_window)
    if "error" in message.lower() or "failed" in message.lower():
        QMessageBox.critical(main_window, "Network Error", f"Network op error: {message}"); stop_current_game_mode_logic(main_window, show_menu=True)
    elif "ended" in message.lower() and main_window.current_game_mode and main_window.current_game_mode != "host_waiting":
        info(f"Mode {main_window.current_game_mode} finished via network signal."); stop_current_game_mode_logic(main_window, show_menu=True)

def on_lan_server_search_status_update_logic(main_window: 'MainWindow', data_tuple: Any): # Renamed
    if not main_window.lan_search_dialog or not main_window.lan_search_dialog.isVisible(): info("LAN search status update received, but dialog is not visible. Ignoring."); return
    if not isinstance(data_tuple, tuple) or len(data_tuple) != 2: warning(f"Invalid data_tuple received in on_lan_server_search_status_update: {data_tuple}"); return
    status_key, data = data_tuple; debug(f"LAN Search Status: Key='{status_key}', Data='{str(data)[:100]}'")
    if main_window.lan_search_status_label: main_window.lan_search_status_label.setText(f"Status: {status_key}")
    if status_key == "found" and isinstance(data, tuple) and len(data)==2:
        ip, port = data; item_text = f"Server at {ip}:{port}"
        if not main_window.lan_servers_list_widget.findItems(item_text, Qt.MatchFlag.MatchExactly): list_item = QListWidgetItem(item_text); list_item.setData(Qt.ItemDataRole.UserRole, f"{ip}:{port}"); main_window.lan_servers_list_widget.addItem(list_item)
        _update_lan_search_list_focus(main_window)
    elif status_key == "timeout" or status_key == "error" or (status_key == "final_result" and data is None and main_window.lan_servers_list_widget.count() == 0):
        if main_window.lan_servers_list_widget.count() == 0 and main_window.lan_search_status_label: main_window.lan_search_status_label.setText(f"Search {status_key}. No servers found.")
        _update_lan_search_list_focus(main_window)
    elif status_key == "final_result" and data is not None:
         ip, port = data; item_text = f"Server at {ip}:{port} (Recommended)"
         if not main_window.lan_servers_list_widget.findItems(item_text, Qt.MatchFlag.MatchExactly): list_item = QListWidgetItem(item_text); list_item.setData(Qt.ItemDataRole.UserRole, f"{ip}:{port}"); main_window.lan_servers_list_widget.addItem(list_item); main_window.lan_servers_list_widget.setCurrentItem(list_item)
         _update_lan_search_list_focus(main_window)

def start_lan_server_search_thread_logic(main_window: 'MainWindow'): # Renamed
    if hasattr(main_window, 'lan_search_worker') and main_window.lan_search_worker and main_window.lan_search_worker.isRunning(): warning("LAN search worker already running."); main_window.lan_search_worker.quit(); main_window.lan_search_worker.wait(500)
    if main_window.lan_servers_list_widget: main_window.lan_servers_list_widget.clear()
    if main_window.lan_search_status_label: main_window.lan_search_status_label.setText("Searching...")
    if main_window.lan_search_dialog and hasattr(main_window.lan_search_dialog, 'button_box'): main_window.lan_search_dialog.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
    
    main_window.lan_search_worker = QThread(parent=main_window)

    class LanSearchRunner(QWidget):
        found_signal = Signal(object)
        search_finished_signal = Signal()
        def __init__(self, parent=None): super().__init__(parent); self.client_state_for_search = ClientState()
        @Slot()
        def run_search(self):
            info("LanSearchRunner: Starting find_server_on_lan.")
            try:
                def cb(key: str, data: Any): self.found_signal.emit((key,data))
                res = find_server_on_lan(self.client_state_for_search, cb)
                self.found_signal.emit(("final_result", res))
            except Exception as e: critical(f"LanSearchRunner Error: {e}", exc_info=True); self.found_signal.emit(("error",f"Search failed: {e}"))
            finally: self.search_finished_signal.emit(); info("LanSearchRunner: run_search finished.")
            
    main_window.lan_search_run_obj = LanSearchRunner()
    main_window.lan_search_run_obj.moveToThread(main_window.lan_search_worker)
    main_window.lan_search_worker.started.connect(main_window.lan_search_run_obj.run_search)
    main_window.lan_search_run_obj.found_signal.connect(lambda data_tuple: on_lan_server_search_status_update_logic(main_window, data_tuple))
    main_window.lan_search_worker.finished.connect(main_window.lan_search_worker.deleteLater)
    main_window.lan_search_run_obj.search_finished_signal.connect(main_window.lan_search_worker.quit)
    main_window.lan_search_run_obj.search_finished_signal.connect(main_window.lan_search_run_obj.deleteLater)
    main_window.lan_search_worker.start(); info("LAN server search thread started.")

def join_selected_lan_server_from_dialog_logic(main_window: 'MainWindow'): # Renamed
    if not main_window.lan_servers_list_widget or not main_window.lan_search_dialog: warning("Attempt to join LAN server, but list widget or dialog is missing."); return
    selected_item = main_window.lan_servers_list_widget.currentItem()
    if selected_item:
        ip_port_str = selected_item.data(Qt.ItemDataRole.UserRole)
        if ip_port_str and isinstance(ip_port_str, str):
            info(f"Joining selected LAN server: {ip_port_str}"); main_window.lan_search_dialog.accept(); main_window.current_modal_dialog = None
            prepare_and_start_game_logic(main_window, "join_lan", target_ip_port=ip_port_str); return
        else: warning(f"Selected LAN server item has invalid data: {ip_port_str}")
    QMessageBox.warning(main_window, "No Server Selected", "Please select a server from the list to join, or Cancel.")

def stop_current_game_mode_logic(main_window: 'MainWindow', show_menu: bool = True): # Renamed
    mode_stopped = main_window.current_game_mode; info(f"Stopping game mode: {mode_stopped}")
    main_window.current_game_mode = None
    if main_window.network_thread and main_window.network_thread.isRunning():
        info("Requesting network thread to stop...")
        if main_window.server_state: main_window.server_state.app_running = False
        if main_window.client_state: main_window.client_state.app_running = False
        main_window.network_thread.quit()
        if not main_window.network_thread.wait(1500): warning("Network thread did not stop gracefully. Terminating."); main_window.network_thread.terminate(); main_window.network_thread.wait(500)
        info("Network thread stopped.")
    main_window.network_thread = None; main_window.server_state = None; main_window.client_state = None
    _close_status_dialog(main_window)
    if main_window.lan_search_dialog and main_window.lan_search_dialog.isVisible(): main_window.lan_search_dialog.reject(); main_window.current_modal_dialog = None
    main_window.game_elements.clear(); main_window.game_scene_widget.update_game_state(0)
    if show_menu: main_window.show_view("menu")
    info(f"Game mode '{mode_stopped}' stopped and cleaned up.")