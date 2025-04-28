# -*- mode: python ; coding: utf-8 -*-

# Import the necessary Analysis components
from PyInstaller.utils.hooks import collect_data_files

# Define the base directory (where this spec file is located)
block_cipher = None

# --- Analysis Phase --- (Stays the same - defines what to find)
a = Analysis(
    ['main.py'],  # Your main script entry point
    pathex=[],     # Add paths here if modules are in non-standard locations
    binaries=[],   # Add non-Python libraries (.dll, .so) if needed
    datas=[
        # Include the ENTIRE 'characters' directory and all its contents recursively.
        # Format: ('source_path_on_disk', 'destination_path_in_bundle')
        ('characters', 'characters')
        # Add other asset folders if you have them (e.g., sounds, fonts, levels)
        # ('assets/sounds', 'assets/sounds'),
        # ('assets/fonts', 'assets/fonts'),
    ],
    hiddenimports=[
        # Add modules PyInstaller might miss, especially ones used by libraries
        'PIL',        # Explicitly include Pillow's base module
        'PIL.Image',  # Often needed for core image operations
        'numpy',      # Pillow might depend on numpy internally for some formats
        # Common pygame hidden imports (add if you get SDL errors in logs)
        # 'pygame._sdl2.video',
        # 'pygame._sdl2.font',
        # 'pygame._sdl2.mixer',
        # 'pygame._sdl2.image',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    # noarchive=False # Setting noarchive is less critical for onefile
)

# --- PYZ (Python Archive) Phase --- (Stays the same)
# Bundles the pure Python modules discovered by Analysis.
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# --- EXE Phase (Configured for One-File) ---
# Defines the single executable file and embeds necessary components.
exe = EXE(
    pyz,                # The bundled Python code archive
    a.scripts,          # The main script(s) to run
    [],                 # Binaries are usually handled by Analysis for one-file
    [],                 # Zipfiles are usually handled by Analysis for one-file
    a.datas,            # <<< Include data files directly HERE for one-file build >>>
    name='BasicPlatformer',  # The name of your final .exe file (without .exe extension)
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,        # Set to True to strip debug symbols (smaller file)
    upx=True,           # Set to False if you don't have UPX installed or don't want UPX compression
    upx_exclude=[],
    runtime_tmpdir=None,# Let PyInstaller manage the temporary extraction directory
    console=False,      # IMPORTANT: False for GUI (Pygame) apps - hides the console window
    disable_windowed_traceback=False,
    target_arch=None,   # Auto-detect architecture
    codesign_identity=None,
    entitlements_file=None,
    # icon='path/to/your/icon.ico' # Optional: Add an icon for your executable
)

# --- COLLECT Phase ---
# <<< This block is NOT used for one-file builds. REMOVE or COMMENT IT OUT. >>>
# coll = COLLECT(
#     exe,
#     a.binaries,
#     a.zipfiles,
#     a.datas,
#     strip=False,
#     upx=True,
#     upx_exclude=[],
#     name='BasicPlatformer'
# )
