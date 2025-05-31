import pyperclip
from pathlib import Path
# os was mentioned as potentially used by an external 'controller.py',
# but is not used in this script. Pathlib handles path operations.

# --- Configuration ---
# Set to False to only process .py files in the root of the target_folder (Folder Mode).
# Set to True to include .py files in subdirectories as well (Folder Mode).
INCLUDE_SUBDIRECTORIES = True

# Add names of subdirectories to ignore (Folder Mode). Case-sensitive.
# If a .py file or an image file is found within any of these subdirectories (relative to target_folder),
# it will be skipped. This applies if INCLUDE_SUBDIRECTORIES is True.
# Example: ["venv", ".venv", "__pycache__", "node_modules", ".git", "build", "dist", "docs_old"]
EXCLUDED_SUBDIRECTORIES = ["venv", ".venv", "__pycache__", "tests_to_ignore", "maps", ".git", "node_modules"]
# --- End Configuration ---

# --- Constants ---
# MERGED_OUTPUT_FILENAME = "merged.txt" # No longer writing to a file
TEMP_CODERUNNER_FILENAME_LOWER = "tempcoderunnerfile.py"
FILE_CONTENT_SEPARATOR = "=" * 80
FILE_START_MARKER_CHAR = "#"
FILE_START_MARKER_COUNT = 20
ERROR_MARKER_CHAR = "!"
ERROR_MARKER_COUNT = 20
IMAGE_EXTENSIONS_LOWERCASE = {".png", ".jpg", ".jpeg", ".gif"}
# --- End Constants ---

# --- Helper Functions (General Purpose) ---
def _clean_path_str(s: str) -> str:
    """Removes leading/trailing whitespace and surrounding quotes from a string."""
    s = s.strip()
    if (s.startswith('"') and s.endswith('"')) or \
       (s.startswith("'") and s.endswith("'")):
        s = s[1:-1]
    return s

def get_display_path(file_path: Path, base_path: Path) -> str:
    """
    Generates a display string for a file path.
    Tries to make it relative to base_path, otherwise returns the absolute path.
    """
    try:
        return str(file_path.relative_to(base_path))
    except ValueError:
        return str(file_path.resolve()) # Absolute path if not relative

# --- Helper Functions (Core Logic for File Collection) ---
def _collect_files_from_folder(
    folder_path: Path, include_subdirs: bool, excluded_subdirs_list: list[str]
) -> list[Path]:
    """
    Scans a folder for .py files, applying exclusions.
    This is used for "Folder Mode".
    """
    files_found_in_folder = []
    print(f"Searching for .py files in {folder_path}...")
    if include_subdirs:
        file_iterator = folder_path.rglob("*.py")
        print("  (Including subdirectories for .py files)")
    else:
        file_iterator = folder_path.glob("*.py")
        print("  (Root directory only for .py files)")

    for py_file in file_iterator:
        if not py_file.is_file():
            continue
            
        try:
            # Path relative to the scan root (folder_path)
            relative_file_path = py_file.relative_to(folder_path)
        except ValueError:
            print(f"  Warning: File {py_file} could not be made relative to {folder_path}. Skipping.")
            continue

        # Exclusion 1: Folders starting with '0'
        # This checks any parent directory component in the relative path.
        if any(part.startswith('0') for part in relative_file_path.parent.parts):
            print(
                f"  Skipping .py (in subdir starting with '0'): {relative_file_path}"
            )
            continue

        # Exclusion 2: EXCLUDED_SUBDIRECTORIES
        if include_subdirs and excluded_subdirs_list:
            is_in_excluded_dir = False
            # EXCLUDED_SUBDIRECTORIES are names of directory components relative to folder_path.
            for dir_component in relative_file_path.parent.parts:
                if dir_component in excluded_subdirs_list:
                    print(
                        f"  Skipping .py (in excluded subdir '{dir_component}'): {relative_file_path}"
                    )
                    is_in_excluded_dir = True
                    break
            if is_in_excluded_dir:
                continue

        if py_file.name.lower() == TEMP_CODERUNNER_FILENAME_LOWER:
            print(f"  Skipping .py (excluded by name): {relative_file_path}")
            continue
        
        files_found_in_folder.append(py_file)
    return files_found_in_folder

def _collect_image_files(
    scan_root_path: Path, 
    include_subdirs: bool, 
    excluded_subdirs_list: list[str],
    base_path_for_display: Path # Used for consistent display paths in messages
) -> list[Path]:
    """
    Scans for image files (png, jpg, jpeg, gif) applying exclusions.
    Exclusions (like EXCLUDED_SUBDIRECTORIES and '0' prefix folders) are relative
    to the scan_root_path.
    """
    image_files_found = []
    print(f"\nSearching for image files ({', '.join(sorted(list(IMAGE_EXTENSIONS_LOWERCASE)))}) in {scan_root_path}...")
    
    if include_subdirs:
        file_iterator = scan_root_path.rglob("*")
        print("  (Including subdirectories for images)")
    else:
        file_iterator = scan_root_path.glob("*")
        print("  (Root directory only for images)")

    for file_path in file_iterator:
        if not file_path.is_file():
            continue
        
        if file_path.suffix.lower() not in IMAGE_EXTENSIONS_LOWERCASE:
            continue

        try:
            # Path relative to the current scan root (scan_root_path)
            path_relative_to_scan_root = file_path.relative_to(scan_root_path)
        except ValueError:
            # Should not happen if file_path is from scan_root_path.glob/rglob
            print(f"  Warning: Image file {get_display_path(file_path, base_path_for_display)} could not be made relative to scan root {scan_root_path}. Skipping.")
            continue
            
        # Exclusion 1: Folders starting with '0'
        # This checks any parent directory component in path_relative_to_scan_root.
        if any(part.startswith('0') for part in path_relative_to_scan_root.parent.parts):
            display_path_for_skip_msg = get_display_path(file_path, base_path_for_display)
            print(
                f"  Skipping image (in subdir starting with '0'): {display_path_for_skip_msg}"
            )
            continue
        
        # Exclusion 2: EXCLUDED_SUBDIRECTORIES
        # These are also checked against parts of path_relative_to_scan_root.
        if include_subdirs and excluded_subdirs_list:
            is_in_excluded_dir = False
            for dir_component in path_relative_to_scan_root.parent.parts: 
                if dir_component in excluded_subdirs_list:
                    display_path_for_skip_msg = get_display_path(file_path, base_path_for_display)
                    print(
                        f"  Skipping image (in excluded subdir '{dir_component}'): {display_path_for_skip_msg}"
                    )
                    is_in_excluded_dir = True
                    break
            if is_in_excluded_dir:
                continue
        
        image_files_found.append(file_path)
    
    return sorted(list(set(image_files_found))) # Deduplicate and sort

# --- Helper Functions (Main Workflow Steps) ---
def _get_raw_paths_from_clipboard() -> list[str] | None:
    """Reads and cleans potential path strings from the clipboard."""
    try:
        clipboard_content = pyperclip.paste()
        if not clipboard_content:
            print("Error: Clipboard is empty.")
            return None
        print(f"Read from clipboard:\n---\n{clipboard_content}\n---")
    except pyperclip.PyperclipException as e:
        print(f"Error: pyperclip could not access the clipboard: {e}")
        print("Please ensure a copy/paste mechanism is installed (e.g., xclip, xsel on Linux).")
        return None
    except Exception as e: # pylint: disable=broad-except
        print(f"An unexpected error occurred with pyperclip (paste): {e}")
        return None

    lines = clipboard_content.strip().splitlines()
    potential_path_strs = [_clean_path_str(line) for line in lines if _clean_path_str(line)]

    if not potential_path_strs:
        print("Error: Clipboard contained no parsable paths after cleaning.")
        return None
    return potential_path_strs

def _determine_files_and_display_base_path(
    potential_path_strs: list[str]
) -> tuple[list[Path] | None, list[Path] | None, Path | None, str | None]:
    """
    Determines the processing mode, collects .py files and image files, 
    and sets the display base path.
    The display_base_path is used to generate relative paths in the output content
    and as the root for image scanning.
    Returns (list_of_py_files, list_of_image_files, display_base_path, mode_name) 
    or (None, None, None, None) on critical error.
    """
    py_files_to_process: list[Path] = []
    image_files_to_list: list[Path] = []
    display_base_path: Path | None = None
    processing_mode_name: str = "unknown"

    if len(potential_path_strs) == 1:
        single_path_str = potential_path_strs[0]
        p = Path(single_path_str)
        if not p.exists():
            print(f"Error: Path '{single_path_str}' does not exist.")
            return None, None, None, None

        if p.is_dir():
            processing_mode_name = "folder"
            target_folder = p.resolve() # Resolve to absolute path for consistency
            display_base_path = target_folder
            print(f"\nProcessing Mode: Folder ({target_folder})")
            print(f"Configuration: Include subdirectories = {INCLUDE_SUBDIRECTORIES}")
            if EXCLUDED_SUBDIRECTORIES:
                print(f"Configuration: Ignoring subdirectories named = {', '.join(EXCLUDED_SUBDIRECTORIES)}")
            else:
                print("Configuration: No subdirectories explicitly configured for exclusion.")
            print("Configuration: Also ignoring any subdirectory whose name starts with '0'.")
            
            py_files_to_process = _collect_files_from_folder(
                target_folder, INCLUDE_SUBDIRECTORIES, EXCLUDED_SUBDIRECTORIES
            )
            # Image scan is always from the display_base_path
            image_files_to_list = _collect_image_files(
                display_base_path, INCLUDE_SUBDIRECTORIES, EXCLUDED_SUBDIRECTORIES, display_base_path
            )

        elif p.is_file() and p.suffix.lower() == ".py":
            processing_mode_name = "files"
            py_files_to_process = [p.resolve()]
            display_base_path = p.resolve().parent
            print(f"\nProcessing Mode: Single File ({p})")
            # Image scan from the parent directory of the .py file
            image_files_to_list = _collect_image_files(
                display_base_path, INCLUDE_SUBDIRECTORIES, EXCLUDED_SUBDIRECTORIES, display_base_path
            )
        else:
            print(f"Error: Clipboard item '{single_path_str}' is not a valid "
                  "directory or an existing .py file.")
            return None, None, None, None
    else:  # Multiple lines/paths from clipboard
        processing_mode_name = "files"
        print(f"\nProcessing Mode: Multiple Files (found {len(potential_path_strs)} potential paths)")
        temp_files_list = []
        for path_str in potential_path_strs:
            p_candidate = Path(path_str).resolve()
            if p_candidate.is_file() and p_candidate.suffix.lower() == ".py":
                temp_files_list.append(p_candidate)
                print(f"  Will process: {p_candidate}")
            else:
                if not p_candidate.exists():
                    print(f"  Skipping: '{path_str}' (path does not exist)")
                elif not p_candidate.is_file():
                     print(f"  Skipping: '{path_str}' (not a file)")
                elif p_candidate.suffix.lower() != ".py":
                     print(f"  Skipping: '{path_str}' (not a .py file)")
                else:
                     print(f"  Skipping: '{path_str}' (unknown reason, not a valid .py file)")

        if not temp_files_list:
            print("Error: No valid existing .py files found among the clipboard paths.")
            return None, None, None, None
        
        py_files_to_process = temp_files_list
        if py_files_to_process: # Should always be true if temp_files_list was not empty
            # Base path for display and image scanning is the parent of the first .py file
            display_base_path = py_files_to_process[0].parent 
            image_files_to_list = _collect_image_files(
                display_base_path, INCLUDE_SUBDIRECTORIES, EXCLUDED_SUBDIRECTORIES, display_base_path
            )


    if display_base_path is None: # Should be set if any valid path was processed
        print("Critical Error: Display base path for relative paths could not be determined.")
        return None, None, None, None

    if not py_files_to_process:
        print("\nNo Python files found matching the criteria to merge.")
        # Still return image list if any, and base path for context
        return [], image_files_to_list, display_base_path, processing_mode_name
    
    py_files_to_process.sort()
    # image_files_to_list is already sorted by _collect_image_files
    return py_files_to_process, image_files_to_list, display_base_path, processing_mode_name


def _build_merged_content_string(
    py_files_to_process: list[Path], 
    image_files_to_list: list[Path],
    display_base_path: Path
) -> str:
    """Reads content from .py files and merges them into a single string with headers,
       also including a list of found image files."""
    
    summary_header_parts = []

    if py_files_to_process:
        print(f"\nFound {len(py_files_to_process)} Python file(s) to merge:")
        for py_file in py_files_to_process:
            print(f"  - {get_display_path(py_file, display_base_path)}")
        
        summary_header_parts.append(
            f"Total Python files compiled: {len(py_files_to_process)}\n"
        )
        summary_header_parts.append("List of compiled .py files (in order of appearance in this content):\n")
        for py_file in py_files_to_process:
            summary_header_parts.append(f"- {get_display_path(py_file, display_base_path)}\n")
    else:
        summary_header_parts.append("No Python files were processed.\n")


    if image_files_to_list:
        print(f"\nFound {len(image_files_to_list)} image file(s):")
        for img_file in image_files_to_list:
            print(f"  - {get_display_path(img_file, display_base_path)}")

        summary_header_parts.append("\n") # Add a separator line
        summary_header_parts.append(f"Total image files found ({', '.join(sorted(list(IMAGE_EXTENSIONS_LOWERCASE)))}): {len(image_files_to_list)}\n")
        summary_header_parts.append(f"List of found image files (relative to: {display_base_path}):\n")
        for img_file in image_files_to_list:
            summary_header_parts.append(f"- {get_display_path(img_file, display_base_path)}\n")
    else:
        summary_header_parts.append(f"\nNo image files ({', '.join(sorted(list(IMAGE_EXTENSIONS_LOWERCASE)))}) found matching criteria in or under {display_base_path}.\n")

    summary_header_parts.append("\n" + FILE_CONTENT_SEPARATOR + "\n")
    file_summary_header = "".join(summary_header_parts)

    all_content_parts = [file_summary_header]

    if not py_files_to_process: # If no .py files, only summary is returned.
        return "".join(all_content_parts)

    for py_file in py_files_to_process:
        display_name = get_display_path(py_file, display_base_path)
        try:
            with open(py_file, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            header = (
                f"\n\n{FILE_START_MARKER_CHAR * FILE_START_MARKER_COUNT}"
                f" START OF FILE: {display_name} "
                f"{FILE_START_MARKER_CHAR * FILE_START_MARKER_COUNT}\n\n"
            )
            all_content_parts.append(header)
            all_content_parts.append(content)
        except (IOError, OSError) as e:
            error_msg_content = (
                f"\n\n{ERROR_MARKER_CHAR * ERROR_MARKER_COUNT}"
                f" ERROR READING FILE: {display_name} - {e} "
                f"{ERROR_MARKER_CHAR * ERROR_MARKER_COUNT}\n\n"
            )
            print(f"  Error reading {display_name}: {e}")
            all_content_parts.append(error_msg_content)
        except Exception as e: # pylint: disable=broad-except
            error_msg_content = (
                f"\n\n{ERROR_MARKER_CHAR * ERROR_MARKER_COUNT}"
                f" UNEXPECTED ERROR PROCESSING FILE: {display_name} - {e} "
                f"{ERROR_MARKER_CHAR * ERROR_MARKER_COUNT}\n\n"
            )
            print(f"  Unexpected error for {display_name}: {e}")
            all_content_parts.append(error_msg_content)

    return "".join(all_content_parts)

def _copy_content_to_clipboard(content: str) -> None:
    """Copies the merged content to the clipboard."""
    try:
        pyperclip.copy(content)
        print("\nSuccessfully copied content to clipboard.")
    except pyperclip.PyperclipException as e:
        print(f"Error: Could not copy content to clipboard: {e}")
        print("Ensure pyperclip is installed and a copy/paste mechanism (e.g., xclip or xsel on Linux, or a VNC/RDP clipboard manager) is available.")
    except Exception as e: # pylint: disable=broad-except
        print(f"An unexpected error occurred while copying content to clipboard: {e}")

# --- Main Public Function ---
def merge_python_content():
    """
    Main orchestrator: Reads path(s) from clipboard, finds .py files and image files,
    merges .py files' content, lists images, and copies the result to the clipboard.
    """
    print("--- Python Code Merger & Image Lister (Clipboard Output Only) ---")
    raw_paths = _get_raw_paths_from_clipboard()
    if raw_paths is None:
        return

    py_files, image_files, base_path, mode_name = _determine_files_and_display_base_path(raw_paths)

    if py_files is None or image_files is None or base_path is None or mode_name is None:
        # This case indicates a critical error during path determination (e.g., clipboard path doesn't exist)
        print("Aborting due to critical error in path processing or base path determination.")
        return
    
    # If no .py files were found BUT it was a valid path processing (e.g., folder mode, just no .py files)
    # We might still have image files to report.
    # The script's primary function is merging .py, so if none, we still inform.
    if not py_files and mode_name != "unknown": # mode_name is "unknown" on some errors
        print("No Python files were selected or found to merge.")
        # If there are image files, we can still proceed to list them.
        # If user wants to exit if no .py files, uncomment the following:
        # if not image_files:
        #     print("No image files found either. Exiting.")
        #     return
        # print("Proceeding to list image files only.")
    
    # At this point, we always build content, even if it's just the summary of images.
    # _build_merged_content_string handles empty py_files list gracefully.
    merged_content_str = _build_merged_content_string(py_files, image_files, base_path)
    
    if not py_files and not image_files:
        print("No Python files and no image files found to report. Nothing to copy.")
    else:
        _copy_content_to_clipboard(merged_content_str)
        
    print("--- Process complete ---")

# --- Alias for external compatibility (if script is named ReadCode.py) ---
merge_python_files_from_clipboard_path = merge_python_content

# --- Script Execution ---
if __name__ == "__main__":
    merge_python_content()
    # input("\nPress Enter to exit...") # Uncomment if running from a terminal that closes immediately