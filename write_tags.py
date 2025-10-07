
import os
import json
import argparse
import sys
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC, TPE1, TALB, TIT2, TCON, TDRC, TRCK, COMM
from mutagen.mp4 import MP4, MP4Cover
from mutagen.flac import FLAC, Picture
from mutagen import File

# Supported audio extensions
AUDIO_EXTENSIONS = ('.mp3', '.m4a', '.wav', '.flac', '.m4b')

def sort_audio_files(files):
    """
    Sorts a list of audio filenames naturally to handle chapter numbers correctly.
    (e.g., "chapter 1.mp3", "chapter 2.mp3", "chapter 10.mp3")
    """
    import re
    def natural_keys(text):
        return [int(c) if c.isdigit() else c for c in re.split('(\\d+)', text)]
    
    files.sort(key=natural_keys)
    return files

def tag_audio_file(file_path, metadata, cover_image_data, track_num, total_tracks):
    """
    Applies metadata tags to a single audio file, handling different formats.
    """
    try:
        audio = File(file_path, easy=False)
        if audio is None:
            raise ValueError("Could not load file.")
        
        # --- Clear existing tags to start fresh ---
        audio.delete()

        # --- Prepare metadata values ---
        album_title = metadata.get("title", "Unknown Title")
        if metadata.get("series") and metadata["series"] != "Unknown":
            album_title = f"{metadata['series']} - {album_title}"

        track_title = album_title
        if total_tracks > 1:
            track_title = f"Chapter {track_num:02}"

        # --- Apply Tags based on file type ---
        if isinstance(audio, MP3):
            audio.tags = ID3()
            audio.tags.add(TPE1(encoding=3, text=metadata.get("author", "")))
            audio.tags.add(TALB(encoding=3, text=album_title))
            audio.tags.add(TIT2(encoding=3, text=track_title))
            audio.tags.add(TCON(encoding=3, text=metadata.get("genre", "")))
            audio.tags.add(TRCK(encoding=3, text=f"{track_num}/{total_tracks}"))
            if metadata.get("year", "") != "Unknown":
                audio.tags.add(TDRC(encoding=3, text=str(metadata.get("year"))))
            # Add synopsis to the standard comment tag (for players like AIMP)
            audio.tags.add(COMM(encoding=3, lang='eng', desc='', text=metadata.get("synopsis", "")))
            # Add synopsis to a described comment tag (for dedicated tag readers)
            audio.tags.add(COMM(encoding=3, lang='eng', desc='Synopsis', text=metadata.get("synopsis", "")))
            if cover_image_data:
                audio.tags.add(APIC(encoding=3, mime='image/jpeg', type=3, desc='Cover', data=cover_image_data))
        
        elif isinstance(audio, MP4):
            audio.tags["\xa9ART"] = metadata.get("author", "")
            audio.tags["\xa9alb"] = album_title
            audio.tags["\xa9nam"] = track_title
            audio.tags["\xa9gen"] = metadata.get("genre", "")
            audio.tags["trkn"] = [(track_num, total_tracks)]
            if metadata.get("year", "") != "Unknown":
                audio.tags["\xa9day"] = str(metadata.get("year"))
            audio.tags["\xa9cmt"] = metadata.get("synopsis", "") # Standard Comment
            audio.tags["ldes"] = metadata.get("synopsis", "")      # Long Description
            if cover_image_data:
                audio.tags["covr"] = [MP4Cover(cover_image_data, imageformat=MP4Cover.FORMAT_JPEG)]

        elif isinstance(audio, FLAC):
            audio["ARTIST"] = metadata.get("author", "")
            audio["ALBUM"] = album_title
            audio["TITLE"] = track_title
            audio["GENRE"] = metadata.get("genre", "")
            audio["TRACKNUMBER"] = str(track_num)
            audio["TRACKTOTAL"] = str(total_tracks)
            if metadata.get("year", "") != "Unknown":
                audio["DATE"] = str(metadata.get("year"))
            audio["COMMENT"] = metadata.get("synopsis", "")     # Standard Comment
            audio["DESCRIPTION"] = metadata.get("synopsis", "") # Dedicated Description
            if cover_image_data:
                pic = Picture()
                pic.type = 3
                pic.mime = "image/jpeg"
                pic.desc = "Cover"
                pic.data = cover_image_data
                audio.add_picture(pic)

        else:
            print(f"      - Unsupported file type: {type(audio)}. Skipping tagging.")
            return

        audio.save()
        print(f"      - Successfully tagged: {os.path.basename(file_path)}")

    except Exception as e:
        print(f"      - ERROR: Failed to tag {os.path.basename(file_path)}: {e}")


def process_book_folder(book_path, marker_filepath):
    """
    Finds metadata and audio files in a book folder and processes them.
    """
    print(f"\nProcessing book folder: {os.path.basename(book_path)}")
    json_path = os.path.join(book_path, "metadata.json")
    cover_path = os.path.join(book_path, "cover.jpg")

    if not os.path.exists(json_path):
        print("  - metadata.json not found. Skipping folder.")
        return

    # --- Load Metadata ---
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        print("  - Loaded metadata.json")
    except Exception as e:
        print(f"  - ERROR: Could not read or parse metadata.json: {e}. Skipping folder.")
        return

    # --- Load Cover Art ---
    cover_image_data = None
    if os.path.exists(cover_path):
        try:
            with open(cover_path, 'rb') as f:
                cover_image_data = f.read()
            print("  - Loaded cover.jpg")
        except Exception as e:
            print(f"  - WARNING: Could not read cover.jpg: {e}. Proceeding without cover.")
    else:
        print("  - No cover.jpg found in this folder.")

    # --- Find and Sort Audio Files ---
    audio_files = [f for f in os.listdir(book_path) if f.lower().endswith(AUDIO_EXTENSIONS)]
    if not audio_files:
        print("  - No audio files found in this folder. Skipping.")
        return
    
    sorted_audio_files = sort_audio_files(audio_files)
    total_tracks = len(sorted_audio_files)
    print(f"  - Found {total_tracks} audio file(s). Starting tagging process...")

    # --- Loop through files and apply tags ---
    for i, filename in enumerate(sorted_audio_files):
        file_path = os.path.join(book_path, filename)
        track_num = i + 1
        tag_audio_file(file_path, metadata, cover_image_data, track_num, total_tracks)
    
    # --- Create marker file to indicate successful processing ---
    try:
        print(f"  - Creating marker file: {os.path.basename(marker_filepath)}")
        with open(marker_filepath, 'a'):
            os.utime(marker_filepath, None)
    except Exception as e:
        print(f"  - WARNING: Could not create marker file: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Writes metadata from JSON files into the audio file tags for an entire library.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "library_directory",
        help="The root directory of your organized audiobook library.\n"
             "WARNING: This script MODIFIES audio files in place.\n"
             "Please BACK UP your library before running."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force the script to re-process all books, even those already marked as processed."
    )
    args = parser.parse_args()

    library_path_abs = os.path.abspath(args.library_directory)

    if not os.path.isdir(library_path_abs):
        print(f"Error: The specified directory '{library_path_abs}' does not exist.", file=sys.stderr)
        sys.exit(1)

    print("--- Starting Audiobook Tagger ---")
    print(f"Library: {library_path_abs}")
    if args.force:
        print("Mode: Forcing re-processing of all books.")
    
    marker_filename = ".tags_written"

    # Walk through the library and find book folders (containing metadata.json)
    for root, dirs, files in os.walk(library_path_abs):
        if "metadata.json" in files:
            marker_filepath = os.path.join(root, marker_filename)

            # Check if we should skip this folder
            if os.path.exists(marker_filepath) and not args.force:
                print(f"\nSkipping folder (already processed): {os.path.basename(root)}")
                dirs[:] = []  # Don't go into sub-folders of a processed book
                continue

            # We found a book folder, process it.
            process_book_folder(root, marker_filepath)
            # To avoid processing sub-folders of a book, clear the 'dirs' list
            dirs[:] = [] 

    print("\n--- Tagger Finished ---")

if __name__ == "__main__":
    main()
