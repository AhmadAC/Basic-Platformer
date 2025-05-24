# level_loader.py
# -*- coding: utf-8 -*-
"""
Loads map data for the game.
Now specifically loads .py modules which define a map-loading function.
Employs aggressive cache busting for reloading maps.
"""
# version 2.0.2 (Aggressive cache busting)
import time
import os
import sys # For sys.path manipulation
import importlib.util # For loading .py modules dynamically
import importlib # For reload and invalidate_caches
import traceback # For more detailed error printing if logger fails

# --- Logger Setup ---
# Attempt to use the project's main logger first
try:
    from logger import info, error, debug, critical # Added critical
except ImportError:
    # Fallback basic console logging if the main logger isn't available
    # This is crucial for standalone testing or if logger.py has issues
    import logging
    logging.basicConfig(level=logging.DEBUG, format='LEVEL_LOADER (FallbackConsole): %(levelname)s - %(message)s')
    _fallback_logger_ll = logging.getLogger(__name__ + "_fallback_ll") # Unique name for fallback

    def info(msg, *args, **kwargs): _fallback_logger_ll.info(msg, *args, **kwargs)
    def error(msg, *args, **kwargs): _fallback_logger_ll.error(msg, *args, **kwargs)
    def debug(msg, *args, **kwargs): _fallback_logger_ll.debug(msg, *args, **kwargs)
    def critical(msg, *args, **kwargs): _fallback_logger_ll.critical(msg, *args, **kwargs)
    
    critical("LevelLoader: Failed to import project's logger. Using isolated fallback for level_loader.py.")
# --- End Logger Setup ---

class LevelLoader:
    def __init__(self):
        info("LevelLoader initialized (for .py map modules with cache busting).")

    def load_map(self, map_name: str, maps_base_dir: str) -> dict | None:
        """
        Loads map data from a .py module file, ensuring a fresh load from disk.

        Args:
            map_name (str): The base name of the map (e.g., "one", "original"),
                            without the .py extension.
            maps_base_dir (str): The absolute path to the directory containing
                                 the map modules (e.g., ".../project_root/maps").

        Returns:
            dict | None: A dictionary containing the map data if successful,
                         None otherwise.
        """
        map_module_file_name = f"{map_name}.py"
        map_file_path = os.path.join(maps_base_dir, map_module_file_name)
        
        # The module name for importlib needs to be in Python's dot-separated format.
        # e.g., "maps.map_name" if 'maps' is a package.
        module_import_name = f"maps.{map_name}"

        info(f"LevelLoader: Attempting to load map module '{module_import_name}' from file: {map_file_path}")

        if not os.path.exists(map_file_path):
            error(f"LevelLoader: Map module file not found: {map_file_path}")
            return None

        try:
            # Ensure the 'maps' directory is treated as a package.
            # This usually requires an __init__.py file in the 'maps' directory.
            maps_package_init_path = os.path.join(maps_base_dir, "__init__.py")
            if not os.path.exists(maps_package_init_path):
                debug(f"LevelLoader: Note: '{maps_package_init_path}' not found. "
                      "For robust module loading, the 'maps' directory should ideally be a package. "
                      "Attempting load anyway.")
                # Depending on Python version and sys.path, this might still work,
                # but it's best practice for 'maps' to be a package.

            # --- AGGRESSIVE CACHE BUSTING ---
            # 1. Remove the module from sys.modules if it's already there.
            #    This forces Python to find and load it again.
            if module_import_name in sys.modules:
                debug(f"LevelLoader: Removing existing map module '{module_import_name}' from sys.modules to force full reload.")
                del sys.modules[module_import_name]
            
            # 2. Invalidate Python's import caches.
            #    This tells Python to re-check the filesystem for modules rather than using cached info.
            importlib.invalidate_caches()
            debug(f"LevelLoader: Invalidated import caches.")
            # --- END AGGRESSIVE CACHE BUSTING ---

            # 3. Import the module.
            #    Because of the steps above, this should load it fresh from the .py file.
            debug(f"LevelLoader: Attempting to import fresh module: {module_import_name}")
            map_module = importlib.import_module(module_import_name)
            debug(f"LevelLoader: Successfully imported module: {module_import_name}")


            # Construct the expected function name, e.g., load_map_one, load_map_original
            safe_map_name_for_func = map_name.replace('-', '_').replace(' ', '_')
            function_name = f"load_map_{safe_map_name_for_func}"
            
            if hasattr(map_module, function_name):
                load_func = getattr(map_module, function_name)
                data = load_func() # Call the function in the freshly loaded module
                if not isinstance(data, dict):
                    error(f"LevelLoader: Map function '{function_name}' in '{map_module_file_name}' did not return a dictionary. Returned type: {type(data)}")
                    return None
                info(f"LevelLoader: Map data for '{map_name}' loaded successfully via function '{function_name}'.")
                return data
            else:
                error(f"LevelLoader: Map module '{map_module_file_name}' (path: {getattr(map_module, '__file__', 'Unknown')}) does not have the expected function '{function_name}'. Available attributes: {dir(map_module)}")
                return None

        except ImportError as e_imp:
            error(f"LevelLoader: ImportError loading map module '{module_import_name}' (from file '{map_file_path}'): {e_imp}", exc_info=True)
            error(f"  Sys.path includes: {sys.path}")
            error(f"  Ensure the 'maps' directory is a Python package (contains an __init__.py file) "
                  f"and its parent directory (your project root) is correctly added to sys.path.")
            return None
        except AttributeError as e_attr:
            error(f"LevelLoader: AttributeError (likely missing function or data issue) in map module '{map_name}': {e_attr}", exc_info=True)
            return None
        except Exception as e:
            error(f"LevelLoader: An unexpected error occurred while loading map module {map_file_path}: {e}", exc_info=True)
            return None

if __name__ == '__main__':
    # This test block requires:
    # 1. A 'maps' subdirectory in the same directory as this level_loader.py (or project root if level_loader.py is there).
    # 2. The 'maps' directory to contain an __init__.py file.
    # 3. A 'maps/test_map_loader_level.py' file with content like:
    #
    #    # maps/test_map_loader_level.py
    #    print("DEBUG: test_map_loader_level.py is being executed/reloaded!") # Add this to see reloads
    #    import time
    #    _load_time = time.time()
    #    def load_map_test_map_loader_level():
    #        return {
    #            "level_name": "Test Map for Loader (from PY)",
    #            "load_timestamp": _load_time, # To check if it's truly reloading
    #            "platforms_list": [{"rect": (0, 500, 800, 50), "color": (100,100,100), "type": "ground"}]
    #        }
    #
    print("--- Testing LevelLoader (with aggressive reload) ---")
    
    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    # Adjust project_root_for_test based on where level_loader.py is relative to the project root
    # If level_loader.py is in the project root:
    project_root_for_test = current_script_dir
    # If level_loader.py is in a subdirectory (e.g., 'utils'):
    # project_root_for_test = os.path.dirname(current_script_dir)

    if project_root_for_test not in sys.path:
        sys.path.insert(0, project_root_for_test)
        print(f"Test: Added '{project_root_for_test}' to sys.path.")

    test_maps_dir_abs = os.path.join(project_root_for_test, "maps")

    if not os.path.exists(test_maps_dir_abs):
        os.makedirs(test_maps_dir_abs)
        print(f"Test: Created directory '{test_maps_dir_abs}'")
    
    init_py_path = os.path.join(test_maps_dir_abs, "__init__.py")
    if not os.path.exists(init_py_path):
        with open(init_py_path, "w") as f_init_test:
            f_init_test.write("# Test __init__.py for maps package\n")
        print(f"Test: Created '{init_py_path}'")

    test_map_name = "test_map_loader_level"
    dummy_map_py_content = f"""
# maps/{test_map_name}.py
print("DEBUG: {test_map_name}.py is being executed/reloaded!") 
import time
_load_time_{test_map_name} = time.time()
def load_map_{test_map_name}():
    print(f"DEBUG: load_map_{test_map_name}() called at timestamp {{_load_time_{test_map_name}}}")
    return {{
        "level_name": "{test_map_name}",
        "load_timestamp": _load_time_{test_map_name},
        "platforms_list": [{{"rect": (0, 500, 800, 50), "color": (100,100,100), "type": "ground"}}]
    }}
"""
    dummy_map_file_path_abs = os.path.join(test_maps_dir_abs, f"{test_map_name}.py")
    with open(dummy_map_file_path_abs, "w") as f_map_test:
        f_map_test.write(dummy_map_py_content)
    print(f"Test: Created/Updated dummy map file '{dummy_map_file_path_abs}'")

    loader = LevelLoader()
    
    print("\n--- First Load ---")
    map_data1 = loader.load_map(test_map_name, test_maps_dir_abs)
    if map_data1:
        print(f"Map '{test_map_name}' loaded successfully (1st time). Timestamp: {map_data1.get('load_timestamp')}")
    else:
        print(f"Map '{test_map_name}' FAILED to load (1st time).")

    print(f"\nSimulating a short delay...")
    time.sleep(0.1) # Small delay to ensure timestamp difference if reload works

    print("\n--- Second Load (should be reloaded from disk) ---")
    map_data2 = loader.load_map(test_map_name, test_maps_dir_abs)
    if map_data2:
        print(f"Map '{test_map_name}' loaded successfully (2nd time). Timestamp: {map_data2.get('load_timestamp')}")
        if map_data1 and map_data2.get('load_timestamp') != map_data1.get('load_timestamp'):
            print("SUCCESS: Timestamps are different, indicating a true reload from disk!")
        elif map_data1:
            print("WARNING: Timestamps are the same. Reload might not have been fully fresh or module execution side effects are minimal.")
        else:
            print("INFO: Second load successful, but first load failed, so cannot compare timestamps.")
    else:
        print(f"Map '{test_map_name}' FAILED to load (2nd time).")
    
    # Clean up test files (optional)
    # os.remove(dummy_map_file_path_abs)
    # os.remove(init_py_path)
    # if not os.listdir(test_maps_dir_abs): os.rmdir(test_maps_dir_abs)

    print("\n--- LevelLoader Test Finished ---")