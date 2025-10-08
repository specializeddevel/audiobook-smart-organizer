# extract_covers.py
import os
import argparse
import sys
import mutagen

# Supported audio extensions
AUDIO_EXTENSIONS = ('.mp3', '.m4a', '.m4b', '.flac', '.wav')

def extract_cover(audio_path):
    """
    Tries to extract cover art from a single audio file. If found, saves it as a
    .jpg file with the same base name in the same directory.

    Args:
        audio_path (str): The full path to the audio file.

    Returns:
        bool: True if a new cover was successfully extracted, False otherwise.
    """
    base_name, _ = os.path.splitext(audio_path)
    cover_path = base_name + ".jpg"

    # Skip if a cover image with the same name already exists.
    if os.path.exists(cover_path):
        # Returning False because we didn't extract a *new* cover.
        return False

    try:
        audio = mutagen.File(audio_path, easy=False)
        if not audio:
            # Not a loadable file, or not supported by mutagen
            return False

        artwork = None
        # For MP4 files (m4a, m4b)
        if 'covr' in audio and audio['covr']:
            artwork = audio['covr'][0]
        # For MP3 files (primary method)
        elif 'APIC:' in audio and audio['APIC:']:
            artwork = audio['APIC:'].data
        # For FLAC files
        elif audio.pictures:
            artwork = audio.pictures[0].data
        
        if artwork:
            with open(cover_path, "wb") as img_file:
                img_file.write(artwork)
            print(f"  - SUCCESS: Extracted cover for: {os.path.basename(audio_path)}")
            return True
        else:
            # File is valid, but contains no cover art
            return False

    except mutagen.MutagenError:
        # This can happen for files that look like audio but are corrupt or unsupported
        return False
    except Exception as e:
        print(f"  - ERROR processing {os.path.basename(audio_path)}: {e}")
        return False

def scan_and_extract(source_dir):
    """
    Scans a directory for audio files and attempts to extract embedded cover art.
    """
    print(f"Scanning directory: {source_dir}\n")
    
    audio_files_found = []
    # Find all audio files recursively
    for root, _, files in os.walk(source_dir):
        for file in files:
            if file.lower().endswith(AUDIO_EXTENSIONS):
                audio_files_found.append(os.path.join(root, file))

    if not audio_files_found:
        print("No audio files found in the specified directory.")
        return

    total_files = len(audio_files_found)
    covers_extracted = 0
    files_truly_missing_cover = []

    print(f"Found {total_files} audio file(s). Starting extraction process...")
    for audio_file in audio_files_found:
        if extract_cover(audio_file):
            covers_extracted += 1
        else:
            # If extraction failed, it could be because the cover already exists
            # or because the file has no embedded cover. We check which case it is.
            base_name, _ = os.path.splitext(audio_file)
            if not os.path.exists(base_name + ".jpg"):
                 files_truly_missing_cover.append(os.path.basename(audio_file))

    print("\n--- Extraction Complete ---")
    print(f"Total audio files processed: {total_files}")
    print(f"New covers extracted: {covers_extracted}")
    
    # Report on files that still don't have a cover image file next to them.
    if files_truly_missing_cover:
        print(f"\nFiles that may be missing a cover ({len(files_truly_missing_cover)}):")
        for filename in files_truly_missing_cover:
            print(f"  - {filename}")
    else:
        print("\nIt seems all audio files have a corresponding cover image.")


def main():
    parser = argparse.ArgumentParser(
        description="Extracts embedded cover art from audio files in a directory.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "source_directory",
        help="The directory containing audio files to scan."
    )
    args = parser.parse_args()

    source_dir_abs = os.path.abspath(args.source_directory)

    if not os.path.isdir(source_dir_abs):
        print(f"Error: The specified directory '{source_dir_abs}' does not exist.", file=sys.stderr)
        sys.exit(1)
        
    scan_and_extract(source_dir_abs)

if __name__ == "__main__":
    main()
