# ebooksort.py (Translated to English)
import os
import shutil
import google.generativeai as genai
import re
import time
import json
import mutagen
import argparse
import csv
import datetime
from collections import defaultdict

# Configure the Gemini API using an environment variable
try:
    GOOGLE_API_KEY = os.environ["GOOGLE_API_KEY"]
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash')
except KeyError:
    print("Error: The GOOGLE_API_KEY environment variable is not set.")
    exit()

# Supported audio extensions
AUDIO_EXTENSIONS = ('.mp3', '.m4a', '.wav', '.flac', '.m4b')


def get_book_info_from_gemini(info_string):
    """
    Tries to get the book's title, author, series, publication year, and synopsis using Gemini.
    """
    # Note: The prompt is translated to English. This might cause the Gemini API
    # to return metadata in English.
    prompt = f"""
    Analyze the following name, which could be a directory name containing an audiobook or an audio file name: '{info_string}'.
    This name represents a complete audiobook, which may consist of one or more files.
    The name often contains the title and sometimes the author. Your task is to extract the following information.
    The title must always be present in the response.

    Data to find:
    - Book Title
    - Book Author
    - Series it belongs to (if applicable)
    - Publication Year (if determinable)
    - Book Genre
    - Book Synopsis (brief summary)

    Response Format:
    'Title: <title> / Author: <author> / Genre: <genre> / Series: <series> / Year: <year> / Synopsis: <synopsis>'

    If you cannot determine some data, return "Unknown" instead of the data, except for the Title.
    """
    try:
        response = model.generate_content(prompt)
        result = response.text.strip()

        # Parse the response
        data = {}
        for item in result.split(" / "):
            if ": " in item:
                parts = item.split(": ", 1)
                if len(parts) == 2:
                    key, value = parts
                    data[key.strip()] = value.strip()

        title = data.get("Title", "Unknown")
        author = data.get("Author", "Unknown")
        genre = data.get("Genre", "Unknown")
        series = data.get("Series", "Unknown")
        year = data.get("Year", "Unknown")
        synopsis = data.get("Synopsis", "Unknown")

        print(f"Title: {title}")
        print(f"Author: {author}")
        print(f"Genre: {genre}")
        print(f"Series: {series}")
        print(f"Year: {year}")
        print(f"Synopsis: {synopsis}")

        return {
            "title": title,
            "author": author,
            "genre": genre,
            "series": series,
            "year": year,
            "synopsis": synopsis
        }

    except Exception as e:
        print(f"Error contacting Gemini: {e}")
        return None
    finally:
        # Increased to 5s to respect the API limit (15 req/min)
        time.sleep(5)


def sanitize_filename(name):
    """
    Cleans a file or directory name by removing or replacing invalid characters.
    """
    clean_name = re.sub(r'[\\/*?<>|":]', "", name)
    clean_name = clean_name.strip()
    clean_name = re.sub(r'\s+', ' ', clean_name)
    return clean_name


def extract_cover_art(file_path, title_dir):
    """
    Tries to extract the cover art from various audio formats using mutagen.
    """
    try:
        audio = mutagen.File(file_path, easy=False)
        if not audio:
            raise mutagen.MutagenError("Could not load file.")

        artwork = None
        # For MP4 files (m4a, m4b)
        if 'covr' in audio:
            artwork = audio['covr'][0]
        # For MP3 files (primary method)
        elif 'APIC:' in audio:
            artwork = audio['APIC:'].data
        # For FLAC files
        elif audio.pictures:
            artwork = audio.pictures[0].data
        
        if artwork:
            with open(os.path.join(title_dir, "cover.jpg"), "wb") as img_file:
                img_file.write(artwork)
            print("Cover art extracted and saved.")
            return True
        else:
            print("No cover art found in the file.")
            return False

    except mutagen.MutagenError as e:
        print(f"Could not process file for cover art: {e}")
        return False
    except Exception as e:
        print(f"An unexpected error occurred while extracting cover art: {e}")
        return False

def handle_existing_cover_file(source_folder, destination_folder):
    """
    Checks for existing image files in the source folder, moves the first one found
    to the destination folder as 'cover.jpg', and returns True if successful.
    """
    supported_images = ('.jpg', '.jpeg', '.png')
    for file in os.listdir(source_folder):
        if file.lower().endswith(supported_images):
            source_image_path = os.path.join(source_folder, file)
            destination_image_path = os.path.join(destination_folder, "cover.jpg")
            
            if os.path.exists(destination_image_path):
                print(f"A 'cover.jpg' already exists in the destination. Skipping move of '{file}'.")
                # We still need to remove the source image so the temp dir can be cleaned up
                os.remove(source_image_path)
                return True

            shutil.move(source_image_path, destination_image_path)
            print(f"Found and moved existing cover file: '{file}'")
            return True
    return False

def get_base_name(filename):
    """
    Extracts a base name from a file to group audiobooks.
    """
    name_without_extension = os.path.splitext(filename)[0]
    
    # Regex to remove common numbering patterns
    patterns = [
        r'[\\s_-]+part?\s*\d+',
        r'[\\s_-]+chapter?\s*\d+',
        r'[\\s_-]+cap\s*\d+',
        r'[\\s_-]+cd\s*\d+',
        r'[\\s_-]+\d+$',
        r'\s*\(\d+\)$'
    ]
    
    base_name = name_without_extension
    for pattern in patterns:
        base_name = re.sub(pattern, '', base_name, flags=re.IGNORECASE).strip()
        
    base_name = re.sub(r'\s+', ' ', base_name).strip()
    
    return base_name if base_name else name_without_extension

def find_unique_foldername(path):
    """
    If a folder at `path` exists, find a new path by appending (2), (3), etc.
    """
    if not os.path.exists(path):
        return path
    
    base, name = os.path.split(path)
    counter = 2
    while True:
        new_name = f"{name} ({counter})"
        new_path = os.path.join(base, new_name)
        if not os.path.exists(new_path):
            return new_path
        counter += 1

def pre_organize_into_folders(source_dir, staging_dir):
    """
    Organizes items from a source directory into a staging directory.
    - Pre-existing folders are moved directly.
    - Loose audio files are grouped into new folders.
    """
    os.makedirs(staging_dir, exist_ok=True)
    grouped_files = defaultdict(list)
    loose_audio_files = []

    print("Scanning source directory...")
    for item in os.listdir(source_dir):
        source_path = os.path.join(source_dir, item)
        # If it's a directory, move it wholesale to staging
        if os.path.isdir(source_path):
            # Skip the staging dir itself if it's inside the source
            if os.path.abspath(source_path) == os.path.abspath(staging_dir):
                continue
            print(f"Moving existing folder '{item}' to staging area.")
            shutil.move(source_path, os.path.join(staging_dir, item))
        # If it's a file, check if it's a loose audio file
        elif os.path.isfile(source_path) and item.lower().endswith(AUDIO_EXTENSIONS):
            loose_audio_files.append(item)

    # Group and move the loose audio files found
    if loose_audio_files:
        print("\nGrouping loose audio files...")
        for file in loose_audio_files:
            base_name = get_base_name(file)
            grouped_files[base_name].append(file)
        
        print(f"Found {len(grouped_files)} groups among loose files.")
        for base_name, files in grouped_files.items():
            folder_name = sanitize_filename(base_name.title())
            dest_folder = os.path.join(staging_dir, folder_name)
            os.makedirs(dest_folder, exist_ok=True)
            
            print(f"\nCreating group '{folder_name}' with {len(files)} file(s).")
            
            for file in files:
                source_path = os.path.join(source_dir, file)
                dest_path = os.path.join(dest_folder, file)
                shutil.move(source_path, dest_path)
                print(f"Moving '{file}' to folder '{folder_name}'")

def organize_audio_files(base_dir, dest_dir):
    """
    Walks the directory, groups audio files by folder, organizes them,
    and maintains an inventory file in CSV format.
    """
    unclassified_dir = os.path.join(dest_dir, "unclassified")
    os.makedirs(dest_dir, exist_ok=True)
    os.makedirs(unclassified_dir, exist_ok=True)

    # --- CSV Inventory Logic ---
    csv_path = os.path.join(dest_dir, "inventory.csv")
    file_exists = os.path.isfile(csv_path)

    # Write header if file doesn't exist
    if not file_exists:
        try:
            with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile, delimiter='|')
                header = ["Title", "Author", "Genre", "Series", "Year", "Synopsis", "Path",
                          "ProcessingDate", "FileCount", "TotalSizeMB", "CoverArtFound"]
                writer.writerow(header)
        except IOError as e:
            print(f"Error: Could not write CSV inventory file at '{csv_path}': {e}")
            return

    for root, _, files in os.walk(base_dir):
        # Ignore the staging directory itself, only process its subdirectories
        if os.path.abspath(root) == os.path.abspath(base_dir):
            continue

        audio_files = [f for f in files if f.lower().endswith(AUDIO_EXTENSIONS)]

        if not audio_files:
            continue

        print(f"\nProcessing group from folder: {os.path.basename(root)}")

        # --- Gather Additional Metadata ---
        processing_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        file_count = len(audio_files)
        try:
            total_size_bytes = sum(os.path.getsize(os.path.join(root, f)) for f in audio_files)
            total_size_mb = round(total_size_bytes / (1024 * 1024), 2)
        except FileNotFoundError:
            print(f"Warning: Could not calculate size for files in '{root}'. Skipping size calculation.")
            total_size_mb = 0

        gemini_info_string = os.path.basename(root)
        print(f"Using '{gemini_info_string}' to get book information...")

        book_data = get_book_info_from_gemini(gemini_info_string)

        if book_data and book_data["title"] != "Unknown":
            # Create title-cased and sanitized names for folders
            author_folder_name = sanitize_filename(book_data["author"].title())
            title_folder_name = sanitize_filename(book_data["title"].title())

            author_dir = os.path.join(dest_dir, author_folder_name)
            os.makedirs(author_dir, exist_ok=True)
            title_dir = os.path.join(author_dir, title_folder_name)
            os.makedirs(title_dir, exist_ok=True)

            # --- Handle Cover Art ---
            # First, look for an existing image file in the source folder.
            cover_art_found = handle_existing_cover_file(root, title_dir)
            # If no existing file was found, try to extract from the audio file.
            if not cover_art_found:
                cover_art_found = extract_cover_art(os.path.join(root, audio_files[0]), title_dir)

            # --- Augment book_data for JSON (using original data from Gemini) ---
            book_data['processing_date'] = processing_date
            book_data['file_count'] = file_count
            book_data['total_size_mb'] = total_size_mb
            book_data['cover_art_found'] = cover_art_found
            book_data['original_files'] = audio_files

            with open(os.path.join(title_dir, "metadata.json"), "w", encoding="utf-8") as f:
                json.dump(book_data, f, ensure_ascii=False, indent=4)
            print("Metadata saved to metadata.json")

            # --- Append to CSV inventory ---
            try:
                with open(csv_path, 'a', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile, delimiter='|')
                    # Use the title-cased folder names for the path in the CSV
                    relative_path = os.path.join(author_folder_name, title_folder_name)
                    row_data = [
                        book_data.get("title", ""),
                        book_data.get("author", ""),
                        book_data.get("genre", ""),
                        book_data.get("series", ""),
                        book_data.get("year", ""),
                        book_data.get("synopsis", ""),
                        relative_path,
                        processing_date,
                        file_count,
                        total_size_mb,
                        cover_art_found
                    ]
                    writer.writerow(row_data)
                print("Book data added to CSV inventory.")
            except IOError as e:
                print(f"Warning: Could not append entry to CSV inventory: {e}")

            # Move all audio files to the new directory
            for file in audio_files:
                source_path = os.path.join(root, file)
                dest_path = os.path.join(title_dir, file)
                shutil.move(source_path, dest_path)
                print(f"File moved to: {dest_path}")

            # Now that the book's staging folder is empty, remove it
            try:
                os.rmdir(root)
                print(f"Temporary book folder deleted: {root}")
            except OSError as e:
                print(f"Warning: Could not delete temporary folder '{root}': {e}")
        else:
            print(f"Could not classify group '{os.path.basename(root)}'. Moving to 'unclassified'.")
            
            # Handle potential duplicates in the 'unclassified' folder
            target_path = os.path.join(unclassified_dir, os.path.basename(root))
            final_path = find_unique_foldername(target_path)
            
            # Move the whole folder
            shutil.move(root, final_path)
            
            if final_path != target_path:
                print(f"Warning: A folder named '{os.path.basename(root)}' already existed in 'unclassified'.")
                print(f"Folder moved as '{os.path.basename(final_path)}' instead.")
            else:
                print(f"Folder '{os.path.basename(root)}' moved to '{unclassified_dir}'")


def main():
    parser = argparse.ArgumentParser(
        description="Audiobook Sorter. Groups, classifies, and organizes audiobook files.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("source_directory", help="The directory containing the audiobooks to organize.")
    parser.add_argument("-d", "--destination_directory", default=".\ebooks", help="The directory where the organized audiobooks will be saved. Defaults to '.\ebooks'.")
    args = parser.parse_args()

    # --- Absolute Paths ---
    # Resolve paths to absolute to prevent ambiguity with the current working directory.
    source_dir_abs = os.path.abspath(args.source_directory)
    dest_dir_abs = os.path.abspath(args.destination_directory)

    # The staging directory is created inside the source directory to avoid conflicts
    staging_dir = os.path.join(source_dir_abs, "_staging_temp")

    print(f"Source Directory: {source_dir_abs}")
    print(f"Destination Directory: {dest_dir_abs}")

    # Make sure the source directory exists before starting
    if not os.path.isdir(source_dir_abs):
        print(f"\nError: The source directory '{source_dir_abs}' does not exist or is not a directory.")
        return

    print("\n--- Phase 1: Grouping files into folders ---")
    pre_organize_into_folders(source_dir_abs, staging_dir)
    
    print("\n--- Phase 2: Classifying and organizing folders ---")
    organize_audio_files(staging_dir, dest_dir_abs)
    
    try:
        # Clean up the staging directory if it's empty
        if os.path.exists(staging_dir) and not os.listdir(staging_dir):
            os.rmdir(staging_dir)
            print("\nTemporary directory cleanup completed.")
    except OSError as e:
        print(f"\nWarning: Could not clean up the temporary directory (it might not be empty): {e}")


if __name__ == "__main__":
    main()
