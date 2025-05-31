# main_game/level_loader.py
# -*- coding: utf-8 -*-
"""
Loads map data for the game.
Now loads .py modules from named subfolders: maps_base_dir/map_name_folder/map_name_file.py.
Employs aggressive cache busting for reloading maps.
Version 2.1.1 (Verified asset path resolution for project structure)
"""
import time
import os
import sys 
import importlib.util 
import importlib 
import traceback 

# --- Logger Setup ---
try:
    from .logger import info, error, debug, critical # Use relative import if logger.py is in main_game
except ImportError:
    # Fallback if this script is run standalone or logger isn't in main_game
    try:
        from logger import info, error, debug, critical # Try root import
    except ImportError:
        import logging
        logging.basicConfig(level=logging.DEBUG, format='LEVEL_LOADER (FallbackConsole): %(levelname)s - %(message)s')
        _fallback_logger_ll = logging.getLogger(__name__ + "_fallback_ll")

        def info(msg, *args, **kwargs): _fallback_logger_ll.info(msg, *args, **kwargs)
        def error(msg, *args, **kwargs): _fallback_logger_ll.error(msg, *args, **kwargs)
        def debug(msg, *args, **kwargs): _fallback_logger_ll.debug(msg, *args, **kwargs)
        def critical(msg, *args, **kwargs): _fallback_logger_ll.critical(msg, *args, **kwargs)
        
        critical("LevelLoader: Failed to import project's logger. Using isolated fallback for level_loader.py.")
# --- End Logger Setup ---

class LevelLoader:
    def __init__(self):
        info("LevelLoader initialized (for .py map modules within named folders, with cache busting).")

    def load_map(self, map_name: str, maps_base_dir_abs: str) -> dict | None:
        """
        Loads map data from a .py module file located in a subdirectory named after the map,
        ensuring a fresh load from disk.

        Args:
            map_name (str): The base name of the map, used for both the subdirectory
                            and the Python file stem (e.g., "one", "original").
            maps_base_dir_abs (str): The absolute path to the base 'maps' directory
                                     (e.g., ".../project_root/maps").

        Returns:
            dict | None: A dictionary containing the map data if successful,
                         None otherwise.
        """
        map_folder_name = map_name 
        map_file_stem = map_name   
        map_module_file_name = f"{map_file_stem}.py"

        map_folder_path_abs = os.path.join(maps_base_dir_abs, map_folder_name)
        map_file_path_abs = os.path.join(map_folder_path_abs, map_module_file_name)
        
        # Module import name: "maps.map_folder_name.map_file_stem"
        # Example: "maps.my_level.my_level"
        module_import_name = f"maps.{map_folder_name}.{map_file_stem}"

        info(f"LevelLoader: Attempting to load map module '{module_import_name}'")
        debug(f"  Map Folder Path (abs): {map_folder_path_abs}")
        debug(f"  Map File Path (abs):   {map_file_path_abs}")

        if not os.path.exists(map_file_path_abs):
            error(f"LevelLoader: Map module file not found: {map_file_path_abs}")
            return None

        try:
            # --- Ensure 'maps' and 'maps/map_folder_name' can be treated as packages ---
            # This involves checking for __init__.py files and potentially adjusting sys.path.
            # The parent directory of 'maps_base_dir_abs' should be in sys.path for `importlib.import_module("maps.something")` to work.
            
            # Path to the parent of the 'maps' directory
            parent_of_maps_dir = os.path.dirname(maps_base_dir_abs)
            
            # Ensure parent_of_maps_dir is in sys.path
            if parent_of_maps_dir not in sys.path:
                debug(f"LevelLoader: Temporarily adding '{parent_of_maps_dir}' to sys.path for import.")
                sys.path.insert(0, parent_of_maps_dir)
                # Note: Ideally, this path management should be done at a higher level (e.g., main app start),
                # but for robustness in loading, we do a local check and modification here.
                # Be mindful of long-term sys.path pollution if this is called many times without cleanup.
            
            maps_package_init_path = os.path.join(maps_base_dir_abs, "__init__.py")
            if not os.path.exists(maps_package_init_path):
                debug(f"LevelLoader: Note: '{maps_package_init_path}' not found. 'maps' directory might not be fully importable as a package.")

            map_specific_package_init_path = os.path.join(map_folder_path_abs, "__init__.py")
            if not os.path.exists(map_specific_package_init_path):
                debug(f"LevelLoader: Note: '{map_specific_package_init_path}' not found in map folder '{map_folder_name}'. This folder might not be fully importable as a sub-package.")

            # --- AGGRESSIVE CACHE BUSTING ---
            if module_import_name in sys.modules:
                debug(f"LevelLoader: Removing existing module '{module_import_name}' from sys.modules.")
                del sys.modules[module_import_name]
            
            importlib.invalidate_caches()
            debug("LevelLoader: Invalidated import caches.")
            # --- END AGGRESSIVE CACHE BUSTING ---

            debug(f"LevelLoader: Attempting import: importlib.import_module('{module_import_name}')")
            map_module = importlib.import_module(module_import_name)
            debug(f"LevelLoader: Successfully imported module: {module_import_name} (Path: {getattr(map_module, '__file__', 'N/A')})")

            safe_map_file_stem_for_func = map_file_stem.replace('-', '_').replace(' ', '_')
            function_name = f"load_map_{safe_map_file_stem_for_func}"
            
            if hasattr(map_module, function_name):
                load_func = getattr(map_module, function_name)
                data = load_func()
                if not isinstance(data, dict):
                    error(f"LevelLoader: Map function '{function_name}' in '{map_module_file_name}' did not return a dictionary. Returned type: {type(data)}")
                    return None
                info(f"LevelLoader: Map data for '{map_name}' (from folder '{map_folder_name}') loaded successfully via function '{function_name}'.")
                return data
            else:
                error(f"LevelLoader: Map module '{map_module_file_name}' (path: {getattr(map_module, '__file__', 'N/A')}) "
                      f"does not have the expected function '{function_name}'. Available attributes: {dir(map_module)}")
                return None

        except ImportError as e_imp:
            error(f"LevelLoader: ImportError loading map module '{module_import_name}' (from file '{map_file_path_abs}'): {e_imp}", exc_info=True)
            error(f"  Current sys.path: {sys.path}")
            error(f"  Ensure the parent directory of '{maps_base_dir_abs}' is in sys.path, and that necessary __init__.py files exist.")
            return None
        except AttributeError as e_attr:
            error(f"LevelLoader: AttributeError (likely missing function or data issue) in map module '{map_name}': {e_attr}", exc_info=True)
            return None
        except Exception as e:
            error(f"LevelLoader: An unexpected error occurred while loading map module {map_file_path_abs}: {e}", exc_info=True)
            return None
        finally:
            # Clean up sys.path if it was modified (optional, but good practice for one-off additions)
            if parent_of_maps_dir in sys.path and sys.path[0] == parent_of_maps_dir:
                debug(f"LevelLoader: Removing temporarily added '{parent_of_maps_dir}' from sys.path.")
                sys.path.pop(0)


if __name__ == '__main__':
    print("--- Testing LevelLoader (with named folders and aggressive reload) ---")
    
    project_root_for_test = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    if project_root_for_test not in sys.path:
        sys.path.insert(0, project_root_for_test)
        print(f"Test: Added '{project_root_for_test}' to sys.path.")

    test_maps_base_dir_abs = os.path.join(project_root_for_test, "maps")
    print(f"Test: Using maps_base_dir: '{test_maps_base_dir_abs}'")

    if not os.path.exists(test_maps_base_dir_abs):
        os.makedirs(test_maps_base_dir_abs)
        print(f"Test: Created base maps directory '{test_maps_base_dir_abs}'")
    
    base_maps_init_py_path = os.path.join(test_maps_base_dir_abs, "__init__.py")
    if not os.path.exists(base_maps_init_py_path):
        with open(base_maps_init_py_path, "w") as f_init_base:
            f_init_base.write("# Base maps package __init__.py\n")
        print(f"Test: Created '{base_maps_init_py_path}'")

    test_map_name_stem = "test_map_loader_folder_level" 

    test_map_specific_folder_abs = os.path.join(test_maps_base_dir_abs, test_map_name_stem)
    if not os.path.exists(test_map_specific_folder_abs):
        os.makedirs(test_map_specific_folder_abs)
        print(f"Test: Created map-specific folder '{test_map_specific_folder_abs}'")

    map_specific_init_py_path = os.path.join(test_map_specific_folder_abs, "__init__.py")
    if not os.path.exists(map_specific_init_py_path):
        with open(map_specific_init_py_path, "w") as f_init_map:
            f_init_map.write(f"# Map-specific __init__.py for {test_map_name_stem}\n")
        print(f"Test: Created '{map_specific_init_py_path}'")

    safe_func_stem = test_map_name_stem.replace('-', '_').replace(' ', '_')
    dummy_map_py_content = f"""
# maps/{test_map_name_stem}/{test_map_name_stem}.py
# This file should be importable as maps.{test_map_name_stem}.{test_map_name_stem}
# Ensure parent of 'maps' folder is in sys.path and 'maps/__init__.py' & 'maps/{test_map_name_stem}/__init__.py' exist.
print(f"DEBUG_MODULE_EXEC: maps/{test_map_name_stem}/{test_map_name_stem}.py is being executed/reloaded!")
import time
_load_time_{safe_func_stem} = time.time()
def load_map_{safe_func_stem}():
    print(f"DEBUG_FUNCTION_CALL: load_map_{safe_func_stem}() called at timestamp {{_load_time_{safe_func_stem}}}")
    return {{
        "level_name": "{test_map_name_stem}",
        "load_timestamp": _load_time_{safe_func_stem},
        "platforms_list": [{{"rect": (0, 500, 800, 50), "color": (100,100,100), "type": "ground"}}]
    }}
"""
    dummy_map_file_path_abs = os.path.join(test_map_specific_folder_abs, f"{test_map_name_stem}.py")
    with open(dummy_map_file_path_abs, "w") as f_map_test:
        f_map_test.write(dummy_map_py_content)
    print(f"Test: Created/Updated dummy map file '{dummy_map_file_path_abs}'")

    loader = LevelLoader()
    
    print("\n--- First Load ---")
    map_data1 = loader.load_map(test_map_name_stem, test_maps_base_dir_abs)
    if map_data1:
        ts1 = map_data1.get('load_timestamp', 0)
        print(f"Map '{test_map_name_stem}' loaded successfully (1st time). Timestamp: {ts1}")
    else:
        print(f"Map '{test_map_name_stem}' FAILED to load (1st time). Check paths and __init__.py files.")
        ts1 = 0

    print(f"\nSimulating a short delay...")
    time.sleep(0.1) 

    print("\n--- Second Load (should be reloaded from disk) ---")
    map_data2 = loader.load_map(test_map_name_stem, test_maps_base_dir_abs)
    if map_data2:
        ts2 = map_data2.get('load_timestamp', 0)
        print(f"Map '{test_map_name_stem}' loaded successfully (2nd time). Timestamp: {ts2}")
        if ts1 > 0 and abs(ts2 - ts1) > 1e-5 :
            print("SUCCESS: Timestamps are different, indicating a true reload from disk!")
        elif ts1 > 0:
            print("WARNING: Timestamps are the same or very close. Reload might not have been fully fresh, or module execution time is too short for timestamp difference.")
        else:
            print("INFO: Second load successful, but first load failed or had no timestamp, so cannot compare timestamps effectively.")
    else:
        print(f"Map '{test_map_name_stem}' FAILED to load (2nd time).")
    
    print("\n--- LevelLoader Test Finished ---")