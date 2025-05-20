# level_loader.py
import os
import json # Or whatever format your map files are in (e.g., .py modules themselves)
from logger import info, error # Assuming you have a logger

class LevelLoader:
    def __init__(self):
        info("LevelLoader initialized.")

    def load_map(self, map_name: str, maps_base_dir: str) -> dict | None:
        map_file_name = f"{map_name}.json" # Assuming .json, adjust if .py or other
        map_path = os.path.join(maps_base_dir, map_file_name)
        info(f"Attempting to load map from: {map_path}")

        if not os.path.exists(map_path):
            error(f"Map file not found: {map_path}")
            return None

        try:
            # If maps are .py files defining a get_level_data() function:
            # import importlib.util
            # spec = importlib.util.spec_from_file_location(map_name, map_path)
            # if spec and spec.loader:
            #     map_module = importlib.util.module_from_spec(spec)
            #     spec.loader.exec_module(map_module)
            #     if hasattr(map_module, 'get_level_data'):
            #         return map_module.get_level_data()
            #     else:
            #         error(f"Map module {map_name} does not have get_level_data()")
            #         return None
            # else:
            #     error(f"Could not create module spec for {map_path}")
            #     return None

            # If maps are .json files:
            with open(map_path, 'r') as f:
                data = json.load(f)
            info(f"Map '{map_name}' loaded successfully.")
            return data
        except json.JSONDecodeError as e_json:
            error(f"Error decoding JSON from map file {map_path}: {e_json}")
            return None
        except Exception as e:
            error(f"An unexpected error occurred while loading map {map_path}: {e}", exc_info=True)
            return None

if __name__ == '__main__':
    # Simple test
    loader = LevelLoader()
    # Create a dummy maps directory and a dummy_map.json for this test
    # For example, in a 'maps' subdir relative to this file:
    # maps/original.json:
    # {
    #   "level_width_pixels": 1600,
    #   "level_height_pixels": 600,
    #   "player_starts": { "P1": [50, 500], "P2": [100, 500]},
    #   "platforms": [ {"x":0, "y":550, "width":1600, "height":50} ]
    # }
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root_guess = os.path.dirname(script_dir) # if level_loader is in a subdir
    # If level_loader.py IS in the project root:
    # project_root_guess = script_dir

    # test_maps_dir = os.path.join(project_root_guess, "maps") # Assuming 'maps' is in project root
    # if not os.path.exists(test_maps_dir):
    #     os.makedirs(test_maps_dir)
    #     # Create a dummy map file for testing
    #     dummy_map_data = {
    #         "level_width_pixels": 800, "level_height_pixels": 600,
    #         "player_starts": {"P1": [50,500]},
    #         "platforms": [{"x":0, "y":550, "width":800, "height":50}]
    #     }
    #     with open(os.path.join(test_maps_dir, "test_map.json"), "w") as f:
    #         json.dump(dummy_map_data, f)

    # map_data = loader.load_map("test_map", test_maps_dir)
    # if map_data:
    #     print("Test map loaded:", map_data)
    # else:
    #     print("Test map failed to load.")
    pass # Actual testing requires map files