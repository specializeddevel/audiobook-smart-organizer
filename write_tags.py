import os
import json
import argparse
import sys
import time
import requests
from ddgs import DDGS
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC, TPE1, TALB, TIT2, TCON, TDRC, TRCK, COMM
from mutagen.mp4 import MP4, MP4Cover
from mutagen.flac import FLAC, Picture
from mutagen import File

# Supported audio extensions
AUDIO_EXTENSIONS = ('.mp3', '.m4a', '.wav', '.flac', '.m4b')

def download_cover_from_internet(book_data, title_dir, dry_run=False):
    """
    Searches the internet for a book cover using DuckDuckGo and downloads the first result.
    """
    if dry_run:
        print(f"  - DRY RUN: Would search online for cover for title: '{book_data.get('title')}'")
        return False

    try:
        title = book_data.get("title", "")
        authors = book_data.get("authors", [])
        author = authors[0] if authors else ""

        if not title or title == "Unknown" or not author or author == "Unknown":
            print("  - Cannot search online without a valid title and author.")
            return False

        keywords = f'{title} {author} book cover'
        print(f"  - Searching for cover online with keywords: \"{keywords}\"")

        with DDGS() as ddgs:
            results = list(ddgs.images(keywords, region='wt-wt', safesearch='moderate', size=None, color=None, type_image=None, layout=None, license_image=None, max_results=5))

        if not results:
            print("  - Online search returned no image results.")
            return False

        image_url = results[0].get("image")
        print(f"  - Found potential cover: {image_url}")

        response = requests.get(image_url, stream=True, timeout=15)
        response.raise_for_status()

        cover_path = os.path.join(title_dir, "cover.jpg")
        with open(cover_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        print("  - Successfully downloaded and saved cover.jpg.")
        return True

    except Exception as e:
        print(f"  - ERROR: Failed to download cover: {e}")
        return False

def sort_audio_files(files):
    """
    Sorts a list of audio filenames naturally to handle chapter numbers correctly.
    """
    import re
    def natural_keys(text):
        return [int(c) if c.isdigit() else c for c in re.split('(\d+)', text)]
    
    files.sort(key=natural_keys)
    return files

def tag_audio_file(file_path, metadata, cover_image_data, track_num, total_tracks, mode, dry_run=False):
    """
    Applies metadata tags to a single audio file based on the selected mode.
    """
    try:
        audio = File(file_path, easy=False)
        if audio is None:
            raise ValueError("Could not load file.")

        if mode == 'cover-only':
            print(f"      - Updating cover art only for: {os.path.basename(file_path)}")
            if isinstance(audio, MP3):
                audio.tags.delall('APIC')
                if cover_image_data:
                    audio.tags.add(APIC(encoding=3, mime='image/jpeg', type=3, desc='Cover', data=cover_image_data))
            elif isinstance(audio, MP4):
                if cover_image_data:
                    audio.tags["covr"] = [MP4Cover(cover_image_data, imageformat=MP4Cover.FORMAT_JPEG)]
                elif "covr" in audio.tags:
                    del audio.tags["covr"]
            elif isinstance(audio, FLAC):
                audio.clear_pictures()
                if cover_image_data:
                    pic = Picture()
                    pic.type = 3
                    pic.mime = "image/jpeg"
                    pic.desc = "Cover"
                    pic.data = cover_image_data
                    audio.add_picture(pic)
            if not dry_run:
                audio.save()
            return

        audio.delete()

        title = metadata.get("title", "Unknown Title")
        authors = metadata.get("authors", [])
        author = authors[0] if authors else ""
        genres = metadata.get("genres", [])
        genre = genres[0] if genres else ""
        series_list = metadata.get("series", [])
        series_name = series_list[0].get("name") if series_list and isinstance(series_list[0], dict) else None
        year = metadata.get("publishedYear")
        synopsis = metadata.get("description", "")

        album_title = title
        if series_name:
            album_title = f"{series_name} - {title}"

        track_title = album_title
        if total_tracks > 1:
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            if base_name.lower().startswith(("chapter", "capitulo", "part", "parte")):
                 track_title = base_name.replace('_', ' ').title()
            else:
                 track_title = f"Chapter {track_num:02d}"

        effective_mode = 'all' if mode == 'smart' else mode

        if isinstance(audio, MP3):
            audio.tags = ID3()
            if effective_mode in ['all', 'tags-only']:
                audio.tags.add(TPE1(encoding=3, text=author))
                audio.tags.add(TALB(encoding=3, text=album_title))
                audio.tags.add(TIT2(encoding=3, text=track_title))
                audio.tags.add(TCON(encoding=3, text=genre))
                audio.tags.add(TRCK(encoding=3, text=f"{track_num}/{total_tracks}"))
                if year:
                    audio.tags.add(TDRC(encoding=3, text=str(year)))
                if synopsis:
                    audio.tags.add(COMM(encoding=3, lang='eng', desc='Synopsis', text=synopsis))
            if effective_mode == 'all' and cover_image_data:
                audio.tags.add(APIC(encoding=3, mime='image/jpeg', type=3, desc='Cover', data=cover_image_data))
        
        elif isinstance(audio, MP4):
            if effective_mode in ['all', 'tags-only']:
                audio.tags["\xa9ART"] = author
                audio.tags["\xa9alb"] = album_title
                audio.tags["\xa9nam"] = track_title
                audio.tags["\xa9gen"] = genre
                audio.tags["trkn"] = [(track_num, total_tracks)]
                if year:
                    audio.tags["\xa9day"] = str(year)
                if synopsis:
                    audio.tags["ldes"] = synopsis
                    audio.tags["\xa9cmt"] = synopsis
            if effective_mode == 'all' and cover_image_data:
                audio.tags["covr"] = [MP4Cover(cover_image_data, imageformat=MP4Cover.FORMAT_JPEG)]

        elif isinstance(audio, FLAC):
            if effective_mode in ['all', 'tags-only']:
                audio["ARTIST"] = author
                audio["ALBUM"] = album_title
                audio["TITLE"] = track_title
                audio["GENRE"] = genre
                audio["TRACKNUMBER"] = str(track_num)
                audio["TRACKTOTAL"] = str(total_tracks)
                if year:
                    audio["DATE"] = str(year)
                if synopsis:
                    audio["DESCRIPTION"] = synopsis
            if effective_mode == 'all' and cover_image_data:
                pic = Picture()
                pic.type = 3
                pic.mime = "image/jpeg"
                pic.desc = "Cover"
                pic.data = cover_image_data
                audio.add_picture(pic)
        else:
            print(f"      - Unsupported file type: {type(audio)}. Skipping tagging.")
            return

        if not dry_run:
            audio.save()
        
        print(f"      - {'DRY RUN: Would tag' if dry_run else 'Successfully tagged'}: {os.path.basename(file_path)}")

    except Exception as e:
        print(f"      - ERROR: Failed to tag {os.path.basename(file_path)}: {e}")

def process_book_folder(book_path, marker_filepath, mode, dry_run=False):
    """
    Finds metadata and audio files in a book folder and processes them.
    """
    print(f"\nProcessing book folder: {os.path.basename(book_path)}")
    json_path = os.path.join(book_path, "metadata.json")
    cover_path = os.path.join(book_path, "cover.jpg")

    if not os.path.exists(json_path):
        print("  - metadata.json not found. Skipping folder.")
        return

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        print("  - Loaded metadata.json")
    except Exception as e:
        print(f"  - ERROR: Could not read or parse metadata.json: {e}. Skipping folder.")
        return

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

    audio_files = [f for f in os.listdir(book_path) if f.lower().endswith(AUDIO_EXTENSIONS)]
    if not audio_files:
        print("  - No audio files found in this folder. Skipping.")
        return
    
    sorted_audio_files = sort_audio_files(audio_files)
    total_tracks = len(sorted_audio_files)
    print(f"  - Found {total_tracks} audio file(s). Starting tagging process (mode: {mode})...")

    for i, filename in enumerate(sorted_audio_files):
        file_path = os.path.join(book_path, filename)
        track_num = i + 1
        tag_audio_file(file_path, metadata, cover_image_data, track_num, total_tracks, mode, dry_run=dry_run)
    
    if mode in ['smart', 'all']:
        if not dry_run:
            try:
                print(f"  - Creating marker file: {os.path.basename(marker_filepath)}")
                with open(marker_filepath, 'a'):
                    os.utime(marker_filepath, None)
            except Exception as e:
                print(f"  - WARNING: Could not create marker file: {e}")
        else:
            print(f"  - DRY RUN: Would create marker file: {os.path.basename(marker_filepath)}")

def process_single_file(file_path, mode, dry_run=False):
    """
    Processes a single audio file by finding its corresponding metadata.
    """
    print(f"\nProcessing single file: {os.path.basename(file_path)}")
    book_path = os.path.dirname(file_path)
    json_path = os.path.join(book_path, "metadata.json")
    cover_path = os.path.join(book_path, "cover.jpg")

    if not os.path.exists(json_path):
        print(f"  - ERROR: metadata.json not found in parent directory '{book_path}'. Skipping.")
        return

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        print("  - Loaded metadata.json")
    except Exception as e:
        print(f"  - ERROR: Could not read or parse metadata.json: {e}. Skipping.")
        return

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

    audio_files = [f for f in os.listdir(book_path) if f.lower().endswith(AUDIO_EXTENSIONS)]
    if not audio_files:
        print("  - No audio files found in the parent directory. Skipping.")
        return
    
    sorted_audio_files = sort_audio_files(audio_files)
    total_tracks = len(sorted_audio_files)
    
    try:
        track_num = sorted_audio_files.index(os.path.basename(file_path)) + 1
    except ValueError:
        print(f"  - ERROR: Could not determine track number for the file. Skipping.")
        return

    print(f"  - File is track {track_num}/{total_tracks}. Starting tagging process (mode: {mode})...")
    tag_audio_file(file_path, metadata, cover_image_data, track_num, total_tracks, mode, dry_run=dry_run)

def main():
    parser = argparse.ArgumentParser(
        description="Writes metadata from JSON files into the audio file tags.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "target_path",
        help="The path to the library directory OR a single audio file to process."
    )
    parser.add_argument(
        "--mode",
        choices=['smart', 'all', 'tags-only', 'cover-only', 'fix-covers'],
        default='smart',
        help="'smart': Process new books only (default).\n"
             "'all': Force re-tag of all metadata and covers for all books.\n"
             "'tags-only': Force re-tag of text metadata only.\n"
             "'cover-only': Force update of cover art only.\n"
             "'fix-covers': Find books missing a cover, download it, and embed it."
    )
    parser.add_argument("--dry-run", action="store_true", help="Perform a simulation without writing any tags or files.")
    args = parser.parse_args()

    if args.dry_run:
        print("\n--- PERFORMING A DRY RUN ---")
        print("No files will be modified.\n")

    target_path_abs = os.path.abspath(args.target_path)

    if not os.path.exists(target_path_abs):
        print(f"Error: The specified path '{target_path_abs}' does not exist.", file=sys.stderr)
        sys.exit(1)

    if os.path.isfile(target_path_abs):
        if not target_path_abs.lower().endswith(AUDIO_EXTENSIONS):
            print(f"Error: The specified file is not a supported audio format.", file=sys.stderr)
            sys.exit(1)
        
        print("--- Starting Audiobook Tagger (Single File Mode) ---")
        process_single_file(target_path_abs, args.mode, dry_run=args.dry_run)
        print("\n--- Tagger Finished ---")
        return

    if os.path.isdir(target_path_abs):
        print("--- Starting Audiobook Tagger (Directory Mode) ---")
        print(f"Library: {target_path_abs}")
        print(f"Mode: {args.mode}")
        
        if args.mode == 'fix-covers':
            for root, dirs, files in os.walk(target_path_abs):
                if "metadata.json" in files:
                    print(f"\nChecking book: {os.path.basename(root)}")
                    json_path = os.path.join(root, "metadata.json")
                    cover_path = os.path.join(root, "cover.jpg")
                    cover_was_newly_downloaded = False
                    
                    try:
                        if not os.path.exists(cover_path):
                            print("  - No cover.jpg found. Attempting to download...")
                            with open(json_path, 'r+', encoding='utf-8') as f:
                                metadata = json.load(f)
                                if download_cover_from_internet(metadata, root, dry_run=args.dry_run):
                                    print("  - Download successful.")
                                    cover_was_newly_downloaded = True
                                    metadata['cover_art_found'] = True # This key doesn't exist in new format, but is harmless
                                    if not args.dry_run:
                                        f.seek(0)
                                        json.dump(metadata, f, ensure_ascii=False, indent=4)
                                        f.truncate()
                                else:
                                    print("  - Failed to download a new cover. Skipping.")
                        else:
                            print("  - Local cover.jpg already exists. No action needed.")

                        if cover_was_newly_downloaded:
                            print("  - Syncing newly downloaded cover art to audio file tags...")
                            with open(json_path, 'r', encoding='utf-8') as f:
                                metadata = json.load(f)
                            with open(cover_path, 'rb') as f:
                                cover_image_data = f.read()
                            
                            audio_files = [f for f in os.listdir(root) if f.lower().endswith(AUDIO_EXTENSIONS)]
                            if not audio_files:
                                print("  - No audio files found to tag.")
                                continue

                            sorted_audio_files = sort_audio_files(audio_files)
                            total_tracks = len(sorted_audio_files)

                            for i, filename in enumerate(sorted_audio_files):
                                file_path = os.path.join(root, filename)
                                tag_audio_file(file_path, metadata, cover_image_data, i + 1, total_tracks, 'cover-only', dry_run=args.dry_run)
                        
                    except Exception as e:
                        print(f"  - An unexpected ERROR occurred while processing {os.path.basename(root)}: {e}")
                    
                    finally:
                        if not args.dry_run:
                            time.sleep(2)
                        dirs[:] = []
            
            print("\n--- Fix Covers Finished ---")
            return

        marker_filename = ".tags_written"
        for root, dirs, files in os.walk(target_path_abs):
            if "metadata.json" in files:
                marker_filepath = os.path.join(root, marker_filename)

                if args.mode == 'smart' and os.path.exists(marker_filepath):
                    print(f"\nSkipping folder (already processed): {os.path.basename(root)}")
                    dirs[:] = []
                    continue

                process_book_folder(root, marker_filepath, args.mode, dry_run=args.dry_run)
                dirs[:] = [] 
        
        print("\n--- Tagger Finished ---")
        return

if __name__ == "__main__":
    main()