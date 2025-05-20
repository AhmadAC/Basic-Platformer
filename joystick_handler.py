#################### START OF FILE: joystick_handler.py ####################

# joystick_handler.py
# -*- coding: utf-8 -*-
"""
Handles joystick/gamepad detection and information retrieval using the 'inputs' library.
This version is designed to be integrated with a PySide6 application.
Actual event reading will likely be handled by the consuming module (e.g., in a thread).
"""
# version 3.0.4 (Corrected GamePad_Type definition using TYPE_CHECKING and proper aliasing)

import sys
import os
from typing import Optional, List, Any, Dict, TYPE_CHECKING

# --- Conditional import for 'inputs' library and GamePad type ---
INPUTS_LIB_AVAILABLE = False

if TYPE_CHECKING:
    # For type checkers, pretend inputs.GamePad is always available.
    from inputs import GamePad as GamePad_Interface
else:
    # At runtime, define a fallback.
    class GamePad_Interface: # This acts as a common interface or dummy
        def __init__(self, path: Optional[str] = None, **kwargs: Any): # Added **kwargs
            self.name: str = "Dummy GamePad (inputs lib missing or failed to load)"
        def read(self) -> List[Any]: return []
        def __enter__(self) -> 'GamePad_Interface': return self
        def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None: pass
        def __getattr__(self, name: str) -> Any: # Handle any other attribute access gracefully
            # print(f"Warning: Accessed undefined attribute '{name}' on Dummy GamePad.")
            return None # Or raise AttributeError if stricter behavior is needed

# Actual runtime import and assignment
try:
    from inputs import get_gamepad as inputs_get_gamepad, UnpluggedError, GamePad as ActualInputsGamePad
    INPUTS_LIB_AVAILABLE = True
    # Runtime GamePad will be the real one if import succeeds
    _RuntimeGamePadClass: Any = ActualInputsGamePad
except ImportError:
    # Runtime GamePad will be the dummy if import fails
    _RuntimeGamePadClass: Any = GamePad_Interface
    class UnpluggedError(Exception): pass # Define dummy UnpluggedError if inputs not found
    def inputs_get_gamepad(*args: Any, **kwargs: Any) -> Any:
        # print("JOY_HANDLER: 'inputs.get_gamepad' called but library is missing.")
        raise ImportError("The 'inputs' library is not installed.")
except Exception as e_inputs_load:
    print(f"JOY_HANDLER ERROR: Failed to import or initialize 'inputs' library: {e_inputs_load}")
    _RuntimeGamePadClass: Any = GamePad_Interface # Fallback to dummy on other import errors
    class UnpluggedError(Exception): pass
    def inputs_get_gamepad(*args: Any, **kwargs: Any) -> Any:
        raise ImportError(f"Error during 'inputs' import: {e_inputs_load}")

# _gamepads_devices_cache will store info about gamepads, including a potential instance
_gamepads_devices_cache: List[Dict[str, Any]] = []
_is_initialized = False

def init_joysticks() -> None:
    global _is_initialized, _gamepads_devices_cache
    _gamepads_devices_cache = [] # Reset cache on init
    if not INPUTS_LIB_AVAILABLE:
        _is_initialized = False
        return
    _is_initialized = True

def get_joystick_count() -> int:
    if not _is_initialized or not INPUTS_LIB_AVAILABLE:
        return 0
    return len(_gamepads_devices_cache)

def add_known_gamepad_device(device_info: Dict[str, Any]) -> None:
    """
    Allows other parts of the application (like a controller mapper)
    to register a gamepad device it has found.
    device_info should be like {'path': ..., 'name': ..., 'instance': Optional[GamePad_Interface]}
    """
    global _gamepads_devices_cache
    if not _is_initialized: return

    device_path = device_info.get('path')
    if device_path:
        for i, existing_dev in enumerate(_gamepads_devices_cache):
            if existing_dev.get('path') == device_path:
                _gamepads_devices_cache[i] = device_info # Update if already exists
                return
    _gamepads_devices_cache.append(device_info)


def get_joystick_name(joystick_index: int) -> str:
    if not _is_initialized or not INPUTS_LIB_AVAILABLE:
        return f"Gamepad {joystick_index} (Handler not init)"
    if 0 <= joystick_index < len(_gamepads_devices_cache):
        return _gamepads_devices_cache[joystick_index].get('name', f"Gamepad {joystick_index}")
    return f"Gamepad {joystick_index} (Not in cache)"


def get_joystick_instance(joystick_index: int) -> Optional[GamePad_Interface]:
    """
    Returns a GamePad instance from the cache if available and valid.
    If no instance is cached but a path is known, it attempts to create one.
    """
    if not _is_initialized or not INPUTS_LIB_AVAILABLE:
        return None

    if 0 <= joystick_index < len(_gamepads_devices_cache):
        device_info = _gamepads_devices_cache[joystick_index]
        instance = device_info.get('instance')

        # Check if the cached instance is valid and of the correct runtime type
        if instance is not None and isinstance(instance, _RuntimeGamePadClass):
            # Add a basic check to see if the gamepad might be disconnected
            # This is heuristic as `inputs` GamePad doesn't have a direct `is_connected()`
            try:
                if hasattr(instance, '_read_thread') and instance._read_thread is not None and not instance._read_thread.is_alive(): # type: ignore
                    if hasattr(instance, '_GamePad__find_input_device'): # only if it's a real inputs.GamePad
                        # print(f"JOY_HANDLER: Cached instance for index {joystick_index} read thread not alive. Assuming disconnected.")
                        device_info['instance'] = None # Clear stale instance
                        instance = None
            except AttributeError: # If it's the dummy, it won't have _read_thread
                pass
            except Exception: # Catch any other error during the check
                # print(f"JOY_HANDLER: Error checking cached instance validity for index {joystick_index}. Re-creating.")
                device_info['instance'] = None
                instance = None
            
            if instance is not None:
                 return instance # type: ignore

        # If no valid instance, but path is known, try to create one.
        device_path = device_info.get('path')
        if device_path:
            try:
                # print(f"JOY_HANDLER: Creating new GamePad instance for index {joystick_index} path {device_path}")
                new_instance = _RuntimeGamePadClass(device_path)
                device_info['instance'] = new_instance # Cache the new instance
                return new_instance # type: ignore
            except UnpluggedError: # type: ignore
                # print(f"JOY_HANDLER: Gamepad at path {device_path} (index {joystick_index}) is unplugged on creation attempt.")
                if 'instance' in device_info: del device_info['instance'] # Ensure no stale instance
                return None
            except Exception as e:
                # print(f"JOY_HANDLER ERROR: Could not create GamePad instance for path {device_path}: {e}")
                return None
    return None

def quit_joysticks() -> None:
    global _is_initialized, _gamepads_devices_cache
    # print("JOY_HANDLER INFO: Quitting joystick handler.")
    for device_info in _gamepads_devices_cache:
        instance = device_info.get('instance')
        if instance and INPUTS_LIB_AVAILABLE and isinstance(instance, ActualInputsGamePad):
            # Real inputs.GamePad instances are typically closed by their __exit__
            # or when their file descriptor is closed by GC if not used in a `with` statement.
            # If we held onto them, we might need to explicitly call a close-like method
            # if the library provided one, or manage their lifecycle more directly.
            # For now, we assume the part of the code that *uses* the instance (e.g., controller_mapper_gui thread)
            # will handle its closure or the `with` statement.
            pass
    _gamepads_devices_cache = []
    _is_initialized = False

# --- Test block ---
if __name__ == "__main__":
    print("JOY_HANDLER_TEST (inputs library v3.0.4): Initializing...")
    init_joysticks()
    
    count = get_joystick_count()
    print(f"JOY_HANDLER_TEST: Number of 'cached' gamepads: {count}")
    
    if INPUTS_LIB_AVAILABLE:
        print("JOY_HANDLER_TEST: Scanning for available gamepads using inputs.devices.gamepads...")
        import inputs # Import locally for test block
        found_any = False
        try:
            # Iterate through the generator provided by inputs.devices.gamepads
            temp_device_list_for_test = []
            for device_obj in inputs.devices.gamepads: # type: ignore
                temp_device_list_for_test.append(device_obj)
            
            if temp_device_list_for_test:
                found_any = True
                print(f"  Found {len(temp_device_list_for_test)} gamepad(s) via inputs.devices.gamepads:")
                for i, device_instance in enumerate(temp_device_list_for_test):
                    path = getattr(device_instance, '_Device__path', f"no_path_{i}")
                    name = getattr(device_instance, 'name', f"Unknown Gamepad {i}")
                    print(f"    - Name='{name}', Path='{path}'")
                    # To make it usable by the handler's functions, we'd normally add it:
                    # add_known_gamepad_device({'path': path, 'name': name, 'instance': None}) # Store info, instance created on demand
            else:
                print("  No gamepads found by iterating inputs.devices.gamepads.")

        except NameError:
             print("  Error: 'inputs' module components not available for test scan (NameError).")
        except UnpluggedError: # type: ignore
            print("  Gamepad unplugged during test scan.")
        except Exception as e:
            print(f"  Error during test scan: {e}")
    else:
        print("JOY_HANDLER_TEST: 'inputs' library not available.")

    # Test getting an instance if one was theoretically added
    if get_joystick_count() > 0:
        print("\nJOY_HANDLER_TEST: Attempting to get instance for index 0 (if cached by a mapper)...")
        gp_inst = get_joystick_instance(0)
        if gp_inst:
            print(f"  Instance for index 0: {gp_inst.name}")
        else:
            print("  Could not get instance for index 0 (or not cached).")


    print("\nJOY_HANDLER_TEST: Quitting...")
    quit_joysticks()
    print("JOY_HANDLER_TEST: Test finished.")

#################### END OF FILE: joystick_handler.py ####################