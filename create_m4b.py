# create_m4b.py
import os
import json
import argparse
import sys
import subprocess
import shutil
from mutagen import File

def check_dependencies():
    """Checks if FFmpeg and ffprobe are installed and available in the system's PATH."""
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        print("--- ERROR: FFmpeg/ffprobe not found. ---", file=sys.stderr)
        print("FFmpeg and ffprobe are required to create M4B files.", file=sys.stderr)
        print("Please install it and ensure it's in your system's PATH.", file=sys.stderr)
        print("You can download it from: https://ffmpeg.org/download.html", file=sys.stderr)
        return False
    print("FFmpeg and ffprobe found, proceeding...")
    return True

def sort_audio_files(files):
    """
    Sorts a list of audio filenames naturally to handle chapter numbers correctly.
    """
    import re
    def natural_keys(text):
        return [int(c) if c.isdigit() else c for c in re.split('(\d+)', text)]
    
    files.sort(key=natural_keys)
    return files

def process_book_folder(book_path, dry_run=False):
    """
    Processes a single book folder, combining its audio files into one M4B file.
    """
    print(f"\nProcessing book folder: {os.path.basename(book_path)}")
    
    # Define paths
    json_path = os.path.join(book_path, "metadata.json")
    cover_path = os.path.join(book_path, "cover.jpg")
    
    # --- 1. Validations ---
    if not os.path.exists(json_path):
        print("  - ERROR: metadata.json not found. Cannot proceed.", file=sys.stderr)
        return
    if not os.path.exists(cover_path):
        print("  - WARNING: cover.jpg not found. The M4B file will not have a cover.", file=sys.stderr)

    # --- 2. Load Metadata ---
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        print("  - Loaded metadata.json")
    except Exception as e:
        print(f"  - ERROR: Could not read or parse metadata.json: {e}", file=sys.stderr)
        return

    # --- 3. Find and Sort Audio Files ---
    audio_extensions = ('.mp3', '.m4a', '.wav', '.flac', '.m4b')
    audio_files = [f for f in os.listdir(book_path) if f.lower().endswith(audio_extensions)]
    if not audio_files:
        print("  - ERROR: No audio files found in this folder.", file=sys.stderr)
        return
    
    sorted_audio_files = sort_audio_files(audio_files)
    print(f"  - Found and sorted {len(sorted_audio_files)} audio files.")

    # --- 4. Generate FFmpeg Chapter Metadata File ---
    ffmpeg_meta_path = os.path.join(book_path, "ffmpeg_metadata.txt")
    files_list_path = os.path.join(book_path, "files_for_ffmpeg.txt")
    total_duration_ms = 0
    chapters_generated = False
    
    try:
        with open(ffmpeg_meta_path, 'w', encoding='utf-8') as meta_file, \
             open(files_list_path, 'w', encoding='utf-8') as list_file:
            
            title = metadata.get('title', 'Unknown Title')
            author = (metadata.get('authors') or ['Unknown Author'])[0]
            genre = (metadata.get('genres') or [''])[0]
            year = metadata.get('publishedYear')
            description = metadata.get('description', '')

            meta_file.write(";FFMETADATA1\n")
            meta_file.write(f"title={title}\n")
            meta_file.write(f"artist={author}\n")
            if genre:
                 meta_file.write(f"genre={genre}\n")
            if year:
                 meta_file.write(f"date={year}\n")
            if description:
                 meta_file.write(f"description={description}\n")
            
            for i, filename in enumerate(sorted_audio_files):
                file_path = os.path.join(book_path, filename)
                escaped_filename = filename.replace("'", "'\\''")
                list_file.write(f"file '{escaped_filename}'\n")
                
                try:
                    # Use ffprobe to get duration, which is more robust than mutagen
                    cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', file_path]
                    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                    duration_s = float(result.stdout.strip())
                    duration_ms = int(duration_s * 1000)
                except (subprocess.CalledProcessError, ValueError, FileNotFoundError) as e:
                    print(f"    - WARNING: Could not get duration for '{filename}' using ffprobe: {e}. Skipping chapter mark.", file=sys.stderr)
                    continue

                start_time = total_duration_ms
                end_time = total_duration_ms + duration_ms
                
                meta_file.write("\n[CHAPTER]\n")
                meta_file.write("TIMEBASE=1/1000\n")
                meta_file.write(f"START={start_time}\n")
                meta_file.write(f"END={end_time}\n")
                
                chapter_title = os.path.splitext(filename)[0]
                if "chapter" not in chapter_title.lower() and "capitulo" not in chapter_title.lower():
                    chapter_title = f"Chapter {i+1}"
                meta_file.write(f"title={chapter_title}\n")
                
                total_duration_ms = end_time
        
        if total_duration_ms > 0:
            chapters_generated = True

        print("  - Generated FFmpeg metadata and file list.")

        # --- 5. Build and Execute FFmpeg Command ---
        output_filename = f"{sanitize_filename(metadata.get('title', 'output'))}.m4b"
        output_path = os.path.join(os.path.dirname(book_path), output_filename)
        
        print(f"  - Target output file: {output_path}")

        command = [
            'ffmpeg',
            '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', files_list_path,
            '-i', ffmpeg_meta_path,
        ]
        
        if os.path.exists(cover_path):
            command.extend(['-i', cover_path])
            # Map streams: 0:audio, 1:metadata(optional), 2:video(cover)
            command.extend(['-map', '0:a', '-map', '1?', '-map', '2:v'])
            command.extend(['-disposition:v:0', 'attached_pic'])
        else:
            # Map streams without cover: 0:audio, 1:metadata(optional)
            command.extend(['-map', '0:a', '-map', '1?'])

        command.extend([
            '-c:a', 'aac',
            '-b:a', '128k',
            '-c:v', 'copy',
            output_path
        ])
        
        if dry_run:
            print("  - DRY RUN: The following FFmpeg command would be executed:")
            # Pretty print the command for readability
            print("    " + " ".join([f'\"{c}\"' if " " in c else c for c in command]))
        else:
            print("  - Executing FFmpeg command... (This may take a moment)")
            result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='ignore')

            if result.returncode == 0:
                print("  - SUCCESS: M4B file created successfully.")
            else:
                print("  - ERROR: FFmpeg failed.", file=sys.stderr)
                print("--- FFmpeg stdout: ---", file=sys.stderr)
                print(result.stdout, file=sys.stderr)
                print("--- FFmpeg stderr: ---", file=sys.stderr)
                print(result.stderr, file=sys.stderr)

    finally:
        # --- 6. Cleanup ---
        if os.path.exists(ffmpeg_meta_path):
            os.remove(ffmpeg_meta_path)
        if os.path.exists(files_list_path):
            os.remove(files_list_path)
        print("  - Cleaned up temporary files.")

def sanitize_filename(name):
    """
    Cleans a string to be used as a valid filename.
    """
    import re
    clean_name = re.sub(r'[\\/*?<>|\":]', "", name)
    clean_name = clean_name.strip()
    return clean_name if clean_name else "Untitled"

def main():
    parser = argparse.ArgumentParser(
        description="Combines all audio files in a processed book folder into a single M4B audiobook file with chapters.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "book_folder_path",
        help="The path to the book's folder (e.g., 'C:\\...\\Author Name\\Book Title')."
    )
    parser.add_argument("--dry-run", action="store_true", help="Perform a simulation without creating the M4B file.")
    args = parser.parse_args()

    if args.dry_run:
        print("\n--- PERFORMING A DRY RUN ---")
        print("The M4B file will not be created.\n")

    if not check_dependencies():
        sys.exit(1)

    book_path_abs = os.path.abspath(args.book_folder_path)

    if not os.path.isdir(book_path_abs):
        print(f"Error: The specified path '{book_path_abs}' is not a valid directory.", file=sys.stderr)
        sys.exit(1)
        
    process_book_folder(book_path_abs, dry_run=args.dry_run)
    print("\n--- M4B Creation Process Finished ---")

if __name__ == "__main__":
    main()
