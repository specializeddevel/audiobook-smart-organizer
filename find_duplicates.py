# find_duplicates.py
import os
import argparse
import re
from collections import defaultdict
from mutagen import File, MutagenError

# Supported audio extensions
AUDIO_EXTENSIONS = ('.mp3', '.m4a', '.flac', '.wav', '.m4b', '.ogg', '.opus', '.aac')

def normalize_name_for_fs(filename):
    """
    Normalizes a filename for basic filesystem comparison.
    - Removes extension.
    - Converts to lowercase.
    - Removes track numbers, special characters, and common tags like (remix).
    """
    name_without_ext = os.path.splitext(filename)[0]
    
    # Remove common tags like [explicit], (live), (remastered), etc.
    name = re.sub(r'\s*[\(\[].*?[\)\]]', '', name_without_ext, flags=re.IGNORECASE).strip()
    
    # Remove leading track numbers (e.g., "01.", "01 - ", "1-")
    name = re.sub(r'^\d+\s*[-._]?\s*', '', name).strip()
    
    # Convert to lowercase and remove all non-alphanumeric characters
    name = re.sub(r'[^a-z0-9]', '', name.lower())
    
    return name

def find_duplicates_filesystem(directory):
    """
    Finds potential duplicates based on normalized filenames.
    This is fast but less accurate than metadata scanning.
    """
    print(f"Starting filesystem scan in: {directory}")
    potential_duplicates = defaultdict(list)

    for root, _, files in os.walk(directory):
        print(f"Scanning folder: {root}")
        files_in_folder = defaultdict(list)
        for f in files:
            if f.lower().endswith(AUDIO_EXTENSIONS):
                normalized = normalize_name_for_fs(f)
                if normalized: # Ensure we don't group empty names
                    files_in_folder[normalized].append(os.path.join(root, f))
        
        for normalized_name, file_paths in files_in_folder.items():
            if len(file_paths) > 1:
                folder_path = os.path.dirname(file_paths[0])
                potential_duplicates[folder_path].append(file_paths)

    return potential_duplicates

def get_metadata_tags(file_path):
    """
    Extracts (artist, title) from an audio file using mutagen.
    Handles various tag names across different formats.
    """
    try:
        audio = File(file_path, easy=True)
        if not audio:
            return None, None

        # easy=True provides a standardized dictionary-like interface
        artist = audio.get('artist', [None])[0]
        title = audio.get('title', [None])[0]

        # Fallback for some formats if 'easy' tags are missing
        if not artist and hasattr(audio, 'tags'):
            if isinstance(audio.tags, dict):
                artist = audio.tags.get('TPE1', [None])[0] or audio.tags.get('\xa9ART', [None])[0]
        if not title and hasattr(audio, 'tags'):
             if isinstance(audio.tags, dict):
                title = audio.tags.get('TIT2', [None])[0] or audio.tags.get('\xa9nam', [None])[0]

        # Clean up the tags
        artist = artist.strip().lower() if artist else None
        title = title.strip().lower() if title else None

        return artist, title

    except MutagenError as e:
        print(f"  - Warning: Could not process file {os.path.basename(file_path)}: {e}")
        return None, None
    except Exception as e:
        print(f"  - Error reading metadata for {os.path.basename(file_path)}: {e}")
        return None, None

def find_duplicates_metadata(directory):
    """
    Finds duplicates based on 'artist' and 'title' metadata tags.
    This is slower but much more accurate.
    """
    print(f"Starting metadata scan in: {directory} (this may take a while...)")
    potential_duplicates = defaultdict(list)

    for root, _, files in os.walk(directory):
        print(f"Scanning folder: {root}")
        tags_in_folder = defaultdict(list)
        audio_files = [f for f in files if f.lower().endswith(AUDIO_EXTENSIONS)]
        
        for i, f in enumerate(audio_files):
            print(f"  - Processing file {i+1}/{len(audio_files)}: {f}", end='\r')
            file_path = os.path.join(root, f)
            artist, title = get_metadata_tags(file_path)
            
            if artist and title:
                tags_in_folder[(artist, title)].append(file_path)
        
        print("\n" + " " * 80 + "\r", end="") # Clear the line

        for (artist, title), file_paths in tags_in_folder.items():
            if len(file_paths) > 1:
                folder_path = os.path.dirname(file_paths[0])
                potential_duplicates[folder_path].append(file_paths)

    return potential_duplicates

def find_folders_with_multiple_audio(directory):
    """
    Finds folders that contain more than one audio file.
    """
    print(f"Starting simple count scan in: {directory}")
    folders_with_multiple = {}

    for root, _, files in os.walk(directory):
        audio_files = [f for f in files if f.lower().endswith(AUDIO_EXTENSIONS)]
        if len(audio_files) > 1:
            print(f"Found {len(audio_files)} audio files in: {root}")
            folders_with_multiple[root] = audio_files
            
    return folders_with_multiple

def print_duplicate_results(duplicate_groups, mode):
    """
    Prints the found duplicate groups in a readable format.
    """
    print("\n--- Scan Complete ---")
    if not duplicate_groups:
        print("No potential duplicates found.")
        return

    print(f"Found {len(duplicate_groups)} folder(s) with potential duplicates (Mode: {mode})\n")
    
    folder_count = 0
    for folder, groups in duplicate_groups.items():
        folder_count += 1
        print(f"[{folder_count}] Folder: {folder}")
        for i, group in enumerate(groups):
            print(f"  - Group {i+1}:")
            for file_path in group:
                print(f"    - {os.path.basename(file_path)}")
        print("-" * 20)

def print_count_results(folders):
    """
    Prints the results for the 'count' mode.
    """
    print("\n--- Scan Complete ---")
    if not folders:
        print("No folders with more than one audio file found.")
        return

    print(f"Found {len(folders)} folder(s) containing more than one audio file.\n")
    
    for i, (folder, files) in enumerate(folders.items()):
        print(f"[{i+1}] Folder: {folder} ({len(files)} files)")
        for f in files:
            print(f"  - {f}")
        print("-" * 20)

def main():
    parser = argparse.ArgumentParser(
        description="Finds potential duplicate audio files in a directory.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "directory",
        help="The root directory of your music collection to scan."
    )
    parser.add_argument(
        "--mode",
        choices=['metadata', 'filesystem', 'count'],
        default='metadata',
        help="Analysis mode:\n" 
             "'metadata':   (default) Slow but accurate scan based on Artist/Title tags.\n" 
             "'filesystem': Fast but less accurate scan based on similar filenames.\n" 
             "'count':      Very fast scan that only lists folders with more than one audio file."
    )
    args = parser.parse_args()

    target_dir = os.path.abspath(args.directory)

    if not os.path.isdir(target_dir):
        print(f"Error: The specified directory '{target_dir}' does not exist.")
        return

    if args.mode == 'filesystem':
        results = find_duplicates_filesystem(target_dir)
        print_duplicate_results(results, args.mode)
    elif args.mode == 'metadata':
        results = find_duplicates_metadata(target_dir)
        print_duplicate_results(results, args.mode)
    elif args.mode == 'count':
        results = find_folders_with_multiple_audio(target_dir)
        print_count_results(results)

if __name__ == "__main__":
    main()
