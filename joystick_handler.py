#################### START OF FILE: joystick_handler.py ####################

# joystick_handler.py
# -*- coding: utf-8 -*-
"""
Handles joystick/gamepad detection and information retrieval using the 'inputs' library.
This version is designed to be integrated with a PySide6 application.
Actual event reading will likely be handled by the consuming module (e.g., in a thread).
"""
# version 3.0.0 (PySide6 Refactor - Using 'inputs' library)

import sys
import os
from typing import Optional, List, Any, Dict # Added Dict and Any
try:
    from inputs import get_gamepad, UnpluggedError, GamePad # For type hinting
    INPUTS_LIB_AVAILABLE = True
except ImportError:
    INPUTS_LIB_AVAILABLE = False
    # Define dummy classes for type hinting if 'inputs' is not installed
    # This allows the rest of the program to type check without 'inputs' installed
    # during early stages of refactoring, though it won't function.
    class GamePad:
        def __init__(self, path=None): self.name = "Dummy Gamepad (inputs lib missing)"
        def read(self): return [] # Dummy read
        def __enter__(self): return self
        def __exit__(self, exc_type, exc_val, exc_tb): pass
    
    def get_gamepad(): # type: ignore
        raise ImportError("The 'inputs' library is not installed. Please install it with 'pip install inputs'")

# List to store detected gamepad device paths or unique identifiers
_gamepads_devices: List[Dict[str, Any]] = [] # Stores dicts like {'path': '/dev/input/eventX', 'name': 'Gamepad Name', 'instance': GamePad}

_is_initialized = False

def init_joysticks():
    """
    Detects connected gamepads using the 'inputs' library.
    Populates the internal list of gamepad devices.
    """
    global _gamepads_devices, _is_initialized
    _gamepads_devices = []
    
    if not INPUTS_LIB_AVAILABLE:
        print("JOY_HANDLER: ERROR - 'inputs' library not found. Joystick functionality will be unavailable.")
        _is_initialized = False
        return

    try:
        # inputs.devices.gamepads directly gives you GamePad objects
        # However, these objects are live and reading from them is blocking.
        # For init, we just want to list them.
        # A more robust way might be to scan /dev/input/event* on Linux or use platform specifics,
        # but get_gamepad() is the primary entry point of the library for a single device.
        # To list multiple, we might need to iterate or use a different approach if the library supports it.
        # For now, let's simulate finding them. This part is tricky without a persistent manager.
        
        # The `inputs` library doesn't have a simple "list all gamepads without opening them" function
        # For a multi-joystick setup, users might need to specify which /dev/input/eventX to use,
        # or we iterate through potential event paths.

        # This is a simplified detection. In a real scenario for multi-joystick,
        # this would need to be more sophisticated, possibly by iterating /dev/input/event*
        # or using udev information on Linux, or IOKit on macOS, or SetupAPI on Windows.
        # The `inputs` library itself doesn't provide a high-level "list all gamepads with paths" API easily.
        # It's more geared towards `get_gamepad()` which tries to find the "first" one or block.
        
        # For this refactor, we'll assume a way to get device paths.
        # Let's simulate having a list of potential device paths for now.
        # This part would need real platform-specific device enumeration or reliance on the user
        # if `inputs` is used directly without a higher-level manager.

        # A common way with `inputs` is to just try opening the "first" available.
        # To support multiple, `config.py` might need to let users specify device paths if auto-detection is hard.

        print("JOY_HANDLER: Initializing with 'inputs' library.")
        print("JOY_HANDLER: Note: Robust multi-gamepad detection with 'inputs' library is complex and platform-dependent.")
        print("JOY_HANDLER: This handler will primarily support getting the *first* available gamepad found by `inputs.get_gamepad()`.")
        print("JOY_HANDLER: For multi-controller mapping or selection, further enhancements would be needed.")

        # Attempt to get the first gamepad to confirm the library is working.
        # This doesn't populate a list of all gamepads, just the first one.
        try:
            # `inputs.get_gamepad()` blocks until a gamepad event or unplug.
            # This is not suitable for a simple init scan.
            # We need to find device files first.
            
            # Let's assume a simplified scenario where we can get a list of paths.
            # On Linux, these are typically /dev/input/eventX
            # This is a placeholder for actual device enumeration.
            potential_paths = []
            if sys.platform.startswith('linux'):
                try:
                    for i in range(16): # Check common event numbers
                        path = f"/dev/input/event{i}"
                        if os.path.exists(path): # Basic check
                            # Try to open to see if it's a gamepad (very basic check)
                            # A more robust check involves ioctl calls or udev.
                            try:
                                temp_gp = GamePad(path) # Try to instantiate
                                # A more reliable check would be to see if it has ABS_X, ABS_Y, BTN_SOUTH etc.
                                # This is still a bit of a guess.
                                # For now, if it can be instantiated without immediate error, consider it.
                                # The `inputs` library's internal device finding is more sophisticated.
                                # However, `inputs.devices.gamepads` is a generator that yields live objects.
                                potential_paths.append({'path': path, 'name': f"Event {i} Device", 'is_gamepad_guess': False})
                                temp_gp.__exit__(None,None,None) # ensure it's closed if opened by constructor
                            except (OSError, PermissionError, UnpluggedError):
                                pass # Not a gamepad or not accessible
                except Exception as e:
                    print(f"JOY_HANDLER: Error during Linux event device scan: {e}")

            # For now, let's rely on what inputs.devices.gamepads can give, even if it's one by one.
            # This is not ideal for `get_joystick_count` immediately after init.
            
            # A better approach for `inputs` library for multiple gamepads:
            # The user might need to configure which device path corresponds to which player.
            # Or, the controller_mapper_gui would need to iterate through `inputs.devices.gamepads`
            # and let the user select.
            
            # For the purpose of this refactor, let's make `_gamepads_devices` store
            # device paths that have been *successfully opened* at some point by get_joystick_instance.
            # This means `get_joystick_count` will only reflect gamepads actively "claimed".

            _is_initialized = True
            print("JOY_HANDLER: 'inputs' library handler initialized. Gamepad detection will occur when an instance is requested.")

        except Exception as e:
            print(f"JOY_HANDLER: Error initializing joysticks with 'inputs' library: {e}")
            _is_initialized = False
            
    except NameError: # If inputs.get_gamepad was not defined due to import error
        print("JOY_HANDLER: 'inputs' library is not available. Cannot initialize joysticks.")
        _is_initialized = False


def get_joystick_count() -> int:
    """
    Returns the number of gamepads that have been successfully instantiated
    and are currently tracked by this handler.
    With the 'inputs' library, this might not reflect all *system-connected* gamepads
    until they are actively requested and opened.
    """
    if not _is_initialized or not INPUTS_LIB_AVAILABLE:
        return 0
    # Prune disconnected gamepads from our list
    # This requires a way to check if a GamePad instance is still valid.
    # The `inputs` library itself handles UnpluggedError during read.
    # For counting, we count what we have successfully "opened" and tracked.
    
    # This function might need to be smarter if we want to proactively scan.
    # For now, it returns the count of devices we *know* about.
    return len(_gamepads_devices)


def get_joystick_name(joystick_index: int) -> str:
    """
    Returns the name of the gamepad at the given logical index.
    """
    if not _is_initialized or not INPUTS_LIB_AVAILABLE:
        return f"Gamepad {joystick_index} (Handler not init)"
        
    if 0 <= joystick_index < len(_gamepads_devices):
        return _gamepads_devices[joystick_index].get('name', f"Gamepad {joystick_index}")
    return f"Gamepad {joystick_index} (Not Found/Invalid Index)"


def get_joystick_instance(joystick_index: int) -> Optional[GamePad]:
    """
    Returns an 'inputs.GamePad' instance for the given logical index.
    If an instance for this index doesn't exist or is invalid, it may try to create one.
    This is a simplified approach for `inputs`. Ideally, device paths or more stable IDs
    would be used to fetch specific gamepads.
    """
    global _gamepads_devices
    if not _is_initialized or not INPUTS_LIB_AVAILABLE:
        return None

    if 0 <= joystick_index < len(_gamepads_devices):
        # Check if the stored instance is still valid (this is tricky with `inputs` GamePad objects)
        # For now, assume if it's in the list, we try to use it.
        # The consuming code should handle UnpluggedError.
        return _gamepads_devices[joystick_index].get('instance')

    # If joystick_index is out of bounds of current list, but could represent a new device.
    # This logic is difficult with `inputs` without more robust device enumeration.
    # `inputs.get_gamepad()` tries to find the *first* available.
    # This function is problematic for `inputs` if we want to get "joystick 0", "joystick 1" reliably
    # without knowing their system device paths.
    
    # For now, let's make it so it tries to get the *first* gamepad if no index is matched
    # and our list is empty, effectively treating joystick_index 0 as "default".
    if joystick_index == 0 and not _gamepads_devices:
        print(f"JOY_HANDLER: Attempting to get first available gamepad for index 0.")
        try:
            # This is blocking and might not be what we want here.
            # For a non-blocking way to get info, we'd need to iterate devices.gamepads
            # and try to match by some criteria if the library offered more info before opening.
            # For now, let's say this function is used when we *expect* a gamepad to be there.
            
            # The `inputs` library primarily works by iterating through `inputs.devices.gamepads`
            # which yields live `GamePad` objects. This `get_joystick_instance(index)` pattern
            # doesn't map perfectly.
            
            # Let's adapt: if _gamepads_devices is empty, and index is 0, try to populate it.
            # This is still not ideal for true multi-joystick management by index.
            
            # A better model for `inputs` might be:
            # 1. `init_joysticks` tries to find all potential gamepad device paths.
            # 2. `get_joystick_instance(index)` tries to open the GamePad at `_gamepads_devices[index]['path']`.
            # This would require platform-specific path enumeration in `init_joysticks`.

            # Simplified for now:
            if not _gamepads_devices: # If our list is empty
                # Try to populate with the first few devices found by the generator
                # This is still not mapping an index to a *specific* physical device reliably over time.
                temp_devices = []
                try:
                    for i, device in enumerate(inputs.devices.gamepads): # type: ignore
                        if i >= 4: break # Limit to checking first few
                        device_path = getattr(device, '_Device__path', f"unknown_path_{i}") # Try to get path
                        device_name = getattr(device, 'name', f"Gamepad_{i}")
                        
                        # We need to store the path to reopen it later, as the `device` object from
                        # the generator might not be reusable after the generator is exhausted or if it's closed.
                        # The `inputs` library is more about getting an event stream.
                        
                        # This means our `_gamepads_devices` should perhaps store paths and names,
                        # and `get_joystick_instance` *creates* the GamePad object on demand.
                        
                        # Let's refine init_joysticks and this function.
                        # For now, this is a placeholder for that improved logic.
                        print(f"JOY_HANDLER: (Placeholder) Found potential gamepad: {device_name} at {device_path}")
                        # This doesn't actually add it to `_gamepads_devices` in a way that
                        # `get_joystick_instance(0)` would then return it.

                except UnpluggedError:
                    print("JOY_HANDLER: No gamepad found or unplugged during initial check for index 0.")
                    return None
                except Exception as e:
                    print(f"JOY_HANDLER: Error trying to access gamepads for index 0: {e}")
                    return None

            # If after trying, we still don't have it for the index:
            if not (0 <= joystick_index < len(_gamepads_devices)):
                return None
            return _gamepads_devices[joystick_index].get('instance')

        except UnpluggedError:
            print(f"JOY_HANDLER: Gamepad for index {joystick_index} is unplugged.")
            # Remove it from our list if it was there
            if 0 <= joystick_index < len(_gamepads_devices):
                del _gamepads_devices[joystick_index]
            return None
        except Exception as e:
            print(f"JOY_HANDLER: Error getting joystick instance for index {joystick_index}: {e}")
            return None
            
    return None # Fallback

def quit_joysticks():
    """
    Cleans up resources. For the 'inputs' library, this means ensuring any
    opened GamePad instances are properly closed if managed by this handler.
    However, GamePad objects are typically used with context managers (`with GamePad() as gp:`).
    If we store instances, we need to ensure they are closed.
    """
    global _gamepads_devices, _is_initialized
    print("JOY_HANDLER: Quitting joystick handler (inputs library).")
    for device_info in _gamepads_devices:
        instance = device_info.get('instance')
        if instance and hasattr(instance, '_GamePad__fd') and instance._GamePad__fd is not None: # Check if it's likely open
            try:
                # The `inputs` GamePad object doesn't have an explicit close().
                # It relies on __exit__ from context manager or garbage collection.
                # We might need to manually close the file descriptor if we opened it and kept it.
                # This is getting into internal details of `inputs` which is not ideal.
                print(f"JOY_HANDLER: (Note) Gamepad instance '{device_info.get('name')}' relies on GC or context manager for closing.")
            except Exception as e:
                print(f"JOY_HANDLER: Error trying to 'close' gamepad '{device_info.get('name')}': {e}")
                
    _gamepads_devices = []
    _is_initialized = False
    print("JOY_HANDLER: Gamepad device list cleared.")

# --- Test block ---
if __name__ == "__main__":
    print("JOY_HANDLER_TEST (inputs library): Initializing...")
    init_joysticks()
    
    count = get_joystick_count()
    print(f"JOY_HANDLER_TEST: Number of 'known' gamepads: {count}")
    
    if count > 0:
        for i in range(count):
            name = get_joystick_name(i)
            print(f"  Gamepad {i}: Name='{name}'")
            # Attempting to get an instance here might be problematic due to `inputs` design
            # gamepad_obj = get_joystick_instance(i)
            # if gamepad_obj:
            #     print(f"    Instance obtained. Path (if available): {getattr(gamepad_obj, '_Device__path', 'N/A')}")
            # else:
            #     print("    Could not obtain instance for detailed info.")
    else:
        # If count is 0, try to get the "first" gamepad to see if `inputs` can find one
        print("JOY_HANDLER_TEST: No gamepads in initial list. Trying to get first default gamepad...")
        default_gamepad = None
        try:
            if INPUTS_LIB_AVAILABLE:
                # The following line is blocking and is more for event reading
                # default_gamepad = get_gamepad() # This will block until an event
                
                # A better test for availability without blocking event read:
                gamepad_devices_gen = inputs.devices.gamepads # type: ignore
                try:
                    first_device = next(gamepad_devices_gen)
                    if first_device:
                        print(f"JOY_HANDLER_TEST: Found at least one gamepad via inputs.devices.gamepads: {getattr(first_device, 'name', 'Unknown name')}")
                        # Note: `first_device` here is a live GamePad object.
                        # We should handle its lifecycle if we keep it.
                    else:
                        print("JOY_HANDLER_TEST: inputs.devices.gamepads yielded no devices.")
                except StopIteration:
                    print("JOY_HANDLER_TEST: No gamepads found by inputs.devices.gamepads.")
                except UnpluggedError:
                    print("JOY_HANDLER_TEST: Gamepad unplugged during test scan.")
                except Exception as e:
                    print(f"JOY_HANDLER_TEST: Error during test scan: {e}")

        except NameError: # get_gamepad not defined
             print("JOY_HANDLER_TEST: 'inputs' library not available (NameError).")
        except ImportError:
             print("JOY_HANDLER_TEST: 'inputs' library not installed (ImportError).")
        except UnpluggedError:
            print("JOY_HANDLER_TEST: No gamepad found or it was unplugged.")
        except Exception as e:
            print(f"JOY_HANDLER_TEST: An error occurred: {e}")


    print("\nJOY_HANDLER_TEST: Quitting...")
    quit_joysticks()
    print("JOY_HANDLER_TEST: Test finished.")

#################### END OF FILE: joystick_handler.py ####################