# level_loader.py
# -*- coding: utf-8 -*-
"""
Loads map data for the game.
Now specifically loads .py modules which define a map-loading function.
"""
# version 2.0.1 (Switched to .py module loading)

import os
import sys # For sys.path manipulation
import importlib.util # For loading .py modules dynamically
from logger import info, error, debug # Assuming you have a logger

class LevelLoader:
    def __init__(self):
        info("LevelLoader initialized (for .py map modules).")

    def load_map(self, map_name: str, maps_base_dir: str) -> dict | None:
        """
        Loads map data from a .py module file.

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
        # If maps_base_dir is ".../project_root/maps", and "maps" is a package,
        # then the module name would be "maps.map_name".
        module_import_name = f"maps.{map_name}"

        info(f"Attempting to load map module '{module_import_name}' from file: {map_file_path}")

        if not os.path.exists(map_file_path):
            error(f"Map module file not found: {map_file_path}")
            return None

        try:
            # If the 'maps' directory is not directly on sys.path or is not a standard package
            # location, sys.path might need adjustment. However, app_core.py should have
            # added the project root to sys.path, making "import maps.map_name" work
            # if 'maps' is a package in the project root.

            # Ensure the 'maps' directory is treated as a package by having an __init__.py file.
            maps_package_init_path = os.path.join(maps_base_dir, "__init__.py")
            if not os.path.exists(maps_package_init_path):
                debug(f"Note: '{maps_package_init_path}' not found. Creating it to ensure 'maps' is a package.")
                try:
                    with open(maps_package_init_path, "w") as f_init:
                        f_init.write("# This file makes 'maps' a Python package.\n")
                except OSError as e_init:
                    error(f"Could not create '{maps_package_init_path}': {e_init}. Map loading might fail if 'maps' is not discoverable.")


            # Check if the module is already loaded and reload it for freshness
            if module_import_name in sys.modules:
                debug(f"Reloading existing map module: {module_import_name}")
                # Ensure parent directory of 'maps' is in sys.path for reload to work correctly
                # This is usually handled by app_core.py setting up the project root.
                map_module = importlib.reload(sys.modules[module_import_name])
            else:
                debug(f"Importing new map module: {module_import_name}")
                # This relies on 'maps' being a discoverable package.
                map_module = importlib.import_module(module_import_name)

            # Construct the expected function name, e.g., load_map_one, load_map_original
            safe_map_name_for_func = map_name.replace('-', '_').replace(' ', '_')
            function_name = f"load_map_{safe_map_name_for_func}"
            
            if hasattr(map_module, function_name):
                load_func = getattr(map_module, function_name)
                data = load_func()
                if not isinstance(data, dict):
                    error(f"Map function '{function_name}' in '{map_module_file_name}' did not return a dictionary. Returned type: {type(data)}")
                    return None
                info(f"Map data for '{map_name}' loaded successfully via function '{function_name}'.")
                return data
            else:
                error(f"Map module '{map_module_file_name}' does not have the expected function '{function_name}'.")
                return None

        except ImportError as e_imp:
            error(f"ImportError loading map module '{module_import_name}' (from file '{map_file_path}'): {e_imp}", exc_info=True)
            error(f"  Sys.path includes: {sys.path}")
            error(f"  Ensure the 'maps' directory is a Python package (contains an __init__.py file) "
                  f"and its parent directory (your project root) is correctly added to sys.path.")
            return None
        except AttributeError as e_attr:
            error(f"AttributeError (likely missing function '{function_name}') in map module '{map_name}': {e_attr}", exc_info=True)
            return None
        except Exception as e:
            error(f"An unexpected error occurred while loading map module {map_file_path}: {e}", exc_info=True)
            return None

if __name__ == '__main__':
    # This test block requires:
    # 1. A 'maps' subdirectory in the same directory as this level_loader.py (or project root if level_loader.py is there).
    # 2. The 'maps' directory to contain an __init__.py file.
    # 3. A 'maps/test_map.py' file with content like:
    #
    #    # maps/test_map.py
    #    def load_map_test_map():
    #        return {
    #            "level_name": "Test Map from PY",
    #            "platforms_list": [{"rect": (0, 500, 800, 50), "color": (100,100,100), "type": "ground"}]
    #        }
    #
    print("--- Testing LevelLoader ---")
    # For testing, assume level_loader.py is in the project root or a directory
    # from which 'maps.map_name' can be imported.
    
    # Setup a temporary sys.path and maps directory structure for isolated testing
    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    # If level_loader.py is in the root of the project:
    project_root_for_test = current_script_dir
    # If level_loader.py is in a subdirectory (e.g., 'utils'):
    # project_root_for_test = os.path.dirname(current_script_dir) # Adjust if necessary

    # Ensure project root is in sys.path for the test
    if project_root_for_test not in sys.path:
        sys.path.insert(0, project_root_for_test)
        print(f"Test: Added '{project_root_for_test}' to sys.path.")

    test_maps_dir_abs = os.path.join(project_root_for_test, "maps")

    # Create dummy maps directory and files if they don't exist
    if not os.path.exists(test_maps_dir_abs):
        os.makedirs(test_maps_dir_abs)
        print(f"Test: Created directory '{test_maps_dir_abs}'")
    
    init_py_path = os.path.join(test_maps_dir_abs, "__init__.py")
    if not os.path.exists(init_py_path):
        with open(init_py_path, "w") as f_init_test:
            f_init_test.write("# Test __init__.py for maps package\n")
        print(f"Test: Created '{init_py_path}'")

    dummy_map_py_content = """
# Dummy map file for testing level_loader.py
def load_map_dummy_test_level():
    return {
        "level_name": "Dummy Test Level from PY",
        "background_color": (100, 149, 237), # Cornflower Blue
        "player_start_pos_p1": (50.0, 400.0),
        "platforms_list": [
            {'rect': (0.0, 450.0, 800.0, 50.0), 'color': (128,128,128), 'type': 'ground'}
        ],
        "hazards_list": [],
        "level_pixel_width": 800.0,
        "level_min_y_absolute": 0.0,
        "level_max_y_absolute": 600.0
    }
"""
    dummy_map_file_path_abs = os.path.join(test_maps_dir_abs, "dummy_test_level.py")
    with open(dummy_map_file_path_abs, "w") as f_map_test:
        f_map_test.write(dummy_map_py_content)
    print(f"Test: Created dummy map file '{dummy_map_file_path_abs}'")

    loader = LevelLoader()
    map_data = loader.load_map("dummy_test_level", test_maps_dir_abs)
    
    if map_data:
        print("\nTest map 'dummy_test_level' loaded successfully:")
        import json
        print(json.dumps(map_data, indent=2))
    else:
        print("\nTest map 'dummy_test_level' FAILED to load.")

    print("--- LevelLoader Test Finished ---")