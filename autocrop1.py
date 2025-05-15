# autocropgif.py
from PIL import Image, ImageSequence
import os
import traceback  # For better error reporting
import pyperclip    # Import pyperclip
from collections import Counter # For summarizing results
import warnings # To potentially catch Pillow warnings if needed

# --- Helper Function to check for pyperclip ---
def check_pyperclip():
    """Checks if pyperclip is available."""
    try:
        import pyperclip # Attempt local import for this check
        pyperclip.paste() # Test if paste works (can sometimes fail on headless systems)
        print("Pyperclip library found and accessible.")
        return True
    except ImportError:
        print("Error: The 'pyperclip' library is not installed.")
        print("Please install it using: pip install pyperclip")
        return False
    except (pyperclip.PyperclipException, Exception) as e: # PyperclipException for its specific errors
        print(f"Error: Pyperclip could not access the clipboard.")
        print(f"Details: {e}")
        print("This might happen on systems without a clipboard manager (e.g., some servers).")
        return False

# --- analyze_gif_frames function (largely the same) ---
def analyze_gif_frames(im):
    """Analyzes GIF frames to find the overall content bounding box."""
    results = {
        'min_left': None, 'min_upper': None,
        'max_right': None, 'max_lower': None
    }
    frames_rgba = []
    durations = []
    disposal_methods = []
    loop_count = im.info.get('loop', 0) # Default loop 0 (infinite)
    frame_index = 0

    for frame_image in ImageSequence.Iterator(im):
        frame_rgba = frame_image.convert("RGBA") # Convert to RGBA for consistent alpha handling
        frames_rgba.append(frame_rgba)
        try:
            # Get bounding box of non-transparent pixels from alpha channel
            alpha_channel = frame_rgba.getchannel('A')
            frame_bbox = alpha_channel.getbbox()
        except ValueError: # If no alpha channel (e.g. mode "RGB" frame in a GIF)
            # Assume full frame is content if no alpha channel
            frame_bbox = (0, 0, frame_rgba.width, frame_rgba.height)

        if frame_bbox: # If content found in this frame
            left, upper, right, lower = frame_bbox
            if results['min_left'] is None or left < results['min_left']: results['min_left'] = left
            if results['min_upper'] is None or upper < results['min_upper']: results['min_upper'] = upper
            if results['max_right'] is None or right > results['max_right']: results['max_right'] = right
            if results['max_lower'] is None or lower < results['max_lower']: results['max_lower'] = lower

        durations.append(frame_image.info.get('duration', 100)) # Default duration 100ms
        disposal = frame_image.info.get('disposal', 2) 
        disposal_methods.append(disposal)
        frame_index += 1

    if None not in results.values(): # Check if any bounding box component was found
        overall_bbox = (results['min_left'], results['min_upper'], results['max_right'], results['max_lower'])
    else: 
        overall_bbox = None # Indicates no content found or GIF was empty
    return overall_bbox, frames_rgba, durations, loop_count, disposal_methods

# --- New function to auto-crop PNG images ---
def auto_crop_png(input_path, output_path):
    """
    Automatically crops a PNG image to its content, saving to output_path.
    The original input_path file is not modified or deleted.
    Returns 'CROPPED', 'SKIPPED', or 'ERROR'.
    """
    print("-" * 30)
    print(f"Processing PNG: '{os.path.basename(input_path)}'")
    img = None
    try:
        img = Image.open(input_path)
        original_info = img.info.copy() # Preserve metadata like DPI, comments

        img_rgba = img.convert("RGBA")
        
        bbox = img_rgba.getbbox() 

        if bbox is None:
            print("  Skipping: PNG is empty or fully transparent (no content found).")
            return 'SKIPPED'

        original_width, original_height = img.size 
        
        if bbox == (0, 0, original_width, original_height):
            print("  Skipping: PNG content already fills the entire frame (no cropping needed).")
            return 'SKIPPED'
        
        crop_width = bbox[2] - bbox[0]
        crop_height = bbox[3] - bbox[1]
        if crop_width <= 0 or crop_height <= 0:
            print(f"  Error: Calculated bounding box has zero or negative dimensions {bbox}. Cannot crop.")
            return 'ERROR'

        print(f"  Original dims: {original_width}x{original_height}")
        print(f"  Content BBox: {bbox}")
        print(f"  Cropped dims: {crop_width}x{crop_height}")

        cropped_img_rgba = img_rgba.crop(bbox)

        if os.path.abspath(input_path) == os.path.abspath(output_path):
            print(f"  Critical Error: Input and output paths are identical for PNG ('{output_path}'). Aborting save to prevent data loss.")
            return 'ERROR'

        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except OSError as e:
                print(f"  Warning: Could not remove existing target file '{os.path.basename(output_path)}': {e}")
                return 'ERROR' 

        cropped_img_rgba.save(output_path, **original_info)
        print(f"  Auto-cropped PNG saved successfully to '{os.path.basename(output_path)}'.")
        return 'CROPPED'

    except FileNotFoundError:
        print(f"Error: Input PNG file not found at '{input_path}'")
        return 'ERROR'
    except Exception as e:
        print(f"An unexpected error occurred processing PNG '{os.path.basename(input_path)}': {e}")
        traceback.print_exc()
        return 'ERROR'
    finally:
        if img:
            try:
                img.close()
            except Exception: 
                pass

# --- auto_crop_animated_gif function (UPDATED with fix for disposal/duration handling) ---
def auto_crop_animated_gif(input_path, output_path):
    """
    Automatically crops an animated GIF, preserving transparency and animation.
    Saves to output_path. Original input_path file is not modified or deleted.
    Returns 'CROPPED', 'SKIPPED', or 'ERROR'.
    """
    print("-" * 30)
    print(f"Processing GIF: '{os.path.basename(input_path)}'")
    original_gif = None 
    try:
        original_gif = Image.open(input_path)

        # --- Step 1: Analyze frames ---
        # overall_bbox_from_analysis, frames_rgba_from_analysis, durations_from_analysis, 
        # loop_count_from_analysis, disposal_methods_from_analysis
        overall_bbox, frames_rgba, durations, loop_count, disposal_methods = analyze_gif_frames(original_gif)

        if overall_bbox is None:
            print("  Skipping: GIF is empty, fully transparent, or bounding box could not be determined.")
            return 'SKIPPED' 

        original_width, original_height = original_gif.size
        bbox_width = overall_bbox[2] - overall_bbox[0]
        bbox_height = overall_bbox[3] - overall_bbox[1]

        if overall_bbox == (0, 0, original_width, original_height):
             print("  Skipping: GIF content already fills the entire frame (no cropping needed).")
             return 'SKIPPED'
        
        if bbox_width <= 0 or bbox_height <= 0:
             print(f"  Error: Calculated bounding box has zero or negative dimensions {overall_bbox}. Cannot crop.")
             return 'ERROR'

        print(f"  Original dims: {original_width}x{original_height}")
        print(f"  Content BBox: {overall_bbox}")
        print(f"  Cropped dims: {bbox_width}x{bbox_height}")

        # --- Step 2: Crop frames and prepare their info ---
        cropped_pil_frames = []
        for i, frame_rgba_source in enumerate(frames_rgba):
            cropped_img = frame_rgba_source.crop(overall_bbox)
            
            # Set per-frame info directly onto the cropped Image object's .info dictionary
            cropped_img.info['duration'] = durations[i]
            cropped_img.info['disposal'] = disposal_methods[i]
            
            cropped_pil_frames.append(cropped_img)

        if not cropped_pil_frames:
            print("  Error: No frames were generated after cropping attempt.")
            return 'ERROR'

        # --- Step 3: Save the cropped animation ---
        print(f"  Saving {len(cropped_pil_frames)} cropped frames to '{os.path.basename(output_path)}'...")

        save_kwargs = {
            "save_all": True,
            "append_images": cropped_pil_frames[1:] if len(cropped_pil_frames) > 1 else [],
            "loop": loop_count,
            "optimize": False, # Consider True for smaller files, but slower & can affect quality
            # Duration and disposal are now set in each frame's .info,
            # so they are not passed as top-level list arguments here.
            # Pillow will pick them up from each frame's .info.
        }
        
        # Add known global GIF properties from original if they exist and are safe
        if 'version' in original_gif.info:
            save_kwargs['version'] = original_gif.info['version']
        # 'background' color index can be tricky if palette changes.
        # For RGBA frames, Pillow usually manages background/transparency well.
        # if 'background' in original_gif.info:
        #     save_kwargs['background'] = original_gif.info['background']
        if 'comment' in original_gif.info: # Preserve comments if any
             save_kwargs['comment'] = original_gif.info['comment']
        # Let Pillow handle 'transparency' based on the RGBA alpha of the frames.
        # Explicitly setting original_gif.info.get('transparency') can be problematic.

        if os.path.abspath(input_path) == os.path.abspath(output_path):
            print(f"  Critical Error: Input and output paths are identical for GIF ('{output_path}'). Aborting save to prevent data loss.")
            return 'ERROR'
        
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except OSError as e:
                print(f"  Warning: Could not remove existing target file '{os.path.basename(output_path)}': {e}")
                return 'ERROR'

        try:
            # The first frame (cropped_pil_frames[0]) saves, and appends the rest.
            # Each frame in cropped_pil_frames now has its .info['duration'] and .info['disposal'] set.
            cropped_pil_frames[0].save(output_path, **save_kwargs)
            print("  Auto-cropped GIF saved successfully.")
            return 'CROPPED'
        except Exception as e:
             print(f"  Error during final GIF save operation: {e}")
             traceback.print_exc()
             return 'ERROR'

    except FileNotFoundError:
        print(f"Error: Input GIF file not found at '{input_path}'")
        return 'ERROR'
    except Exception as e:
        print(f"An unexpected error occurred processing GIF '{os.path.basename(input_path)}': {e}")
        traceback.print_exc()
        return 'ERROR'
    finally:
        if original_gif:
            try:
                original_gif.close()
            except Exception as close_e:
                print(f"Warning: Error closing original GIF file: {close_e}")


# --- Main Execution Logic ---
def main():
    """
    Main function to handle clipboard input, find GIF/PNG files,
    and process them using respective auto-crop functions.
    """
    print("--- AutoCropGIF/PNG Script ---") 
    if not check_pyperclip():
        print("Exiting: Pyperclip is required and not functional.")
        return

    try:
        clipboard_content = pyperclip.paste().strip()
    except (pyperclip.PyperclipException, Exception) as e:
        print(f"Error reading from clipboard: {e}")
        print("Exiting.")
        return

    if not clipboard_content:
        print("Clipboard is empty. Please copy a file or folder path.")
        return

    if clipboard_content.startswith(('"', "'")) and clipboard_content.endswith(('"', "'")):
        clipboard_content = clipboard_content[1:-1]

    if not os.path.exists(clipboard_content):
        print(f"Error: The path from the clipboard does not exist: '{clipboard_content}'")
        return

    files_to_process = []
    supported_extensions = ('.gif', '.png')

    if os.path.isfile(clipboard_content):
        if clipboard_content.lower().endswith(supported_extensions):
            base, _ = os.path.splitext(clipboard_content)
            if base.lower().endswith("_c"):
                print(f"Skipping single file '{os.path.basename(clipboard_content)}' as it appears to be already cropped.")
            else:
                print("Processing single file from clipboard.")
                files_to_process.append(clipboard_content)
        else:
            print(f"Error: The file '{os.path.basename(clipboard_content)}' is not a supported type (GIF or PNG).")
    elif os.path.isdir(clipboard_content):
        print(f"Scanning folder from clipboard: '{clipboard_content}'")
        found_files_in_dir = []
        try:
            for filename in os.listdir(clipboard_content):
                if filename.lower().endswith(supported_extensions):
                    base, _ = os.path.splitext(filename)
                    if base.lower().endswith("_c"):
                        continue 
                    full_path = os.path.join(clipboard_content, filename)
                    if os.path.isfile(full_path):
                         found_files_in_dir.append(full_path)
        except OSError as e:
            print(f"Error reading directory '{clipboard_content}': {e}")
            return

        if not found_files_in_dir:
            print(f"No suitable image files ({', '.join(e.upper() for e in supported_extensions)}) found in '{clipboard_content}' (or they already end with '_c').")
        else:
            print(f"Found {len(found_files_in_dir)} image file(s) to process.")
            files_to_process.extend(found_files_in_dir)
    else:
        print(f"Error: The path '{clipboard_content}' is neither a file nor a directory.")
        return

    if not files_to_process:
        print("\nNo new image files selected for processing.")
        return
    
    print(f"\nStarting processing for {len(files_to_process)} image file(s)...")
    
    processed_details = [] 

    for input_path in files_to_process:
        base, ext = os.path.splitext(input_path)
        output_path = f"{base}_c{ext}"

        file_ext_lower = ext.lower()
        status = 'ERROR_UNKNOWN' 

        try:
            if file_ext_lower == '.gif':
                status = auto_crop_animated_gif(input_path, output_path)
            elif file_ext_lower == '.png':
                status = auto_crop_png(input_path, output_path)
            else:
                status = 'ERROR_UNSUPPORTED_TYPE'
                print(f"  Skipping unsupported file type: {os.path.basename(input_path)}")
        except Exception as e: 
            print(f"!! Critical error during processing dispatch for {os.path.basename(input_path)}: {e}")
            traceback.print_exc()
            status = 'ERROR_DISPATCH_CRASH'
            
        actual_output_path = output_path if status == 'CROPPED' else ""
        processed_details.append({'input': input_path, 'output': actual_output_path, 'status': status})

    print("-" * 30)
    print("\nProcessing Summary:")
    
    status_counts = Counter(item['status'] for item in processed_details)

    cropped_count = status_counts['CROPPED']
    skipped_no_crop_needed_count = status_counts['SKIPPED']
    
    failed_count = 0
    error_items = []
    for item in processed_details:
        if item['status'] not in ['CROPPED', 'SKIPPED']:
            failed_count += 1
            error_items.append(item)

    print(f"  Successfully cropped: {cropped_count}")
    if cropped_count > 0:
        for item in processed_details:
            if item['status'] == 'CROPPED':
                print(f"      - Saved: {os.path.basename(item['output'])} (from {os.path.basename(item['input'])})")
    
    print(f"  Skipped (no crop needed/empty): {skipped_no_crop_needed_count}")
    
    print(f"  Failed or other non-success statuses: {failed_count}")
    if failed_count > 0:
        for item in error_items:
            print(f"      - File: {os.path.basename(item['input'])} (Status: {item['status']})")
    
    print("-" * 30)

# --- Guard for Direct Execution ---
if __name__ == "__main__":
    main()