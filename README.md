An open source, completely python generated local couch co-op platformer game.



**. Scripts Responsible for Drawing & Logic**

* **tiles.py**:

  * **Defines the classes** **Platform**, **Ladder**, and **Lava**.
* **Logic**: Each class is initialized with coordinates, dimensions, and color. They have a **@property def image(self)** **method that lazily creates a** **QPixmap**. **Platform** **and** **Lava** **fill this pixmap with their** **q_color**. **Ladder** **creates a transparent pixmap and then draws rungs and rails on it.**
* **Each class has a** **draw_pyside(self, painter: QPainter, camera: Any)** **method. This method takes the** **camera** **object, applies its transformation to the tile's** **rect**, and then uses the **painter** **to draw the tile's** **image** **at the calculated screen position. This is the correct way for these static elements to be drawn.**
* **game_ui.py** **(**GameSceneWidget.paintEvent**)**:

  * **This is the central rendering loop for the game scene.**
* **Logic**: It iterates through **self.game_elements.get("all_renderable_objects", [])**.

  * **If an entity has a** **draw_pyside** **method (like your** **Platform**, **Lava**, **Ladder** **objects, as well as** **Player**, **Enemy**, **Chest**, **Statue**, **Projectile** **classes), that method is called.**
    * **There's a fallback for entities that only have** **.rect** **and** **.image** **(and don't have an** **alive** **attribute that is** **False**). This fallback is less relevant for your custom tile classes since they do have **draw_pyside**.
* **app_game_modes.py** **(**_initialize_game_entities**)**:

  * **This function is responsible for loading map data and creating the actual game objects (like** **Platform**, **Lava**, **Player**, **Enemy**, etc.) for the current game mode.
* **Logic**:

  * **It calls** **reset_game_state** **(from** **game_state_manager.py**) which clears out dynamic lists.
    * **It then loads map data using** **level_loader.load_map()**.
    * **It iterates through lists like** **level_data.get('platforms_list', [])**, **level_data.get('hazards_list', [])**, etc.
    * **For each entry, it instantiates the corresponding Python object (e.g.,** **Platform(...)**, **Lava(...)**).
    * **Crucially, it appends these newly created tile objects to** **main_window.game_elements['platforms_list']** **(and similar for hazards/ladders) AND to** **main_window.game_elements['all_renderable_objects']**. This step is vital for them to be rendered.
* **couch_play_logic.py** **(**run_couch_play_mode**)**:

  * **This is the main game loop function for couch coop.**
* **Logic (relevant to rendering)**: It contains a section for "Generic Pruning of **all_renderable_objects**". This logic iterates through **game_elements_ref.get("all_renderable_objects", [])** **and builds a new list:**

  * **It** **explicitly keeps** **objects that are** **isinstance(obj, (Platform, Ladder, Lava))**.
    * **For other objects, it keeps them if** **hasattr(obj, 'alive') and obj.alive()**.
    * **This pruning logic is** **correct** **for ensuring static tiles like platforms and lava are not accidentally removed.**

**2. Why Walls, Lava, etc., Are Invisible in Couch Coop**

**The core issue is** **not** **directly related to the "not being alive" status of tiles in the** **couch_play_logic.py** **pruning or the** **GameSceneWidget.paintEvent** **rendering (because your** **Platform**/**Lava** **objects have** **draw_pyside**). The pruning in **couch_play_logic.py** **is fine.**

**The problem lies in how map data is loaded and interpreted for game modes versus how the editor loads it:**

* **Editor's Map Loading**:

  * **The editor uses** **editor_map_utils.load_map_from_json**, which calls **editor_history.restore_map_from_snapshot**. This populates **editor_state.placed_objects**.
* **The** **MapViewWidget** **in the editor then iterates** **editor_state.placed_objects** **and uses** **editor_assets.get_asset_pixmap** **to display them. This works because the editor's** **.json** **save format is essentially a direct dump of** **editor_state.placed_objects**.
* **Game's Map Loading (via** **level_loader.py**)**:**

  * **level_loader.py** **in its current form loads a** **.json** **file.**
* **app_game_modes.py** **(**_initialize_game_entities**) then expects this JSON data to have specific top-level keys like** **"platforms_list"**, **"hazards_list"**, **"enemies_list"**, etc. (This is the format that **editor_map_utils.export_map_to_game_python_script** **creates for** **.py** **map files).**
* **The Discrepancy**: The editor saves its map data into a **.json** **file where all placeable objects (platforms, enemies, items, etc.) are typically stored under a single list, often something like** **"placed_objects"** **(as seen in** **editor_history.get_map_snapshot**). This editor **.json** **file does** **not** **inherently have separate** **"platforms_list"**, **"hazards_list"**, etc., at the top level.
