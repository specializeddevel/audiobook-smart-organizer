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
import requests
from ddgs import DDGS

# Configure the Gemini API using an environment variable
try:
    GOOGLE_API_KEY = os.environ["GOOGLE_API_KEY"]
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash')
    print("Gemini API configured successfully.")
except KeyError:
    print("Error: The GOOGLE_API_KEY environment variable is not set.")
    exit()

# Supported audio extensions
AUDIO_EXTENSIONS = ('.mp3', '.m4a', '.wav', '.flac', '.m4b')


def add_author_to_known_list(author_name, filepath="known_authors.txt"):
    """
    Adds a new author to the known authors file if not already present.
    The check is case-insensitive, and authors are stored in Title Case.
    """
    if not author_name or author_name == "Unknown":
        return

    author_to_add = author_name.strip().title()
    
    try:
        # Read existing authors into a case-insensitive set for efficient lookup
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                existing_authors = {line.strip().lower() for line in f}
        else:
            existing_authors = set()

        # If author is not already in the set, append to the file
        if author_to_add.lower() not in existing_authors:
            with open(filepath, 'a', encoding='utf-8') as f:
                f.write(author_to_add + '\n')
            print(f"  - Author '{author_to_add}' added to known authors list.")

    except IOError as e:
        print(f"  - WARNING: Could not read or write to authors file '{filepath}': {e}")


def get_book_info_from_gemini(info_string):
    """
    Tries to get the book's title, author, series, publication year, and synopsis using Gemini.
    """
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

    If you cannot determine some data, return "Unknown" instead of the data, except for the Title. Synopsis data should by in Spanish and English.
    """
    try:
        response = model.generate_content(prompt)
        result = response.text.strip()

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
        time.sleep(4) # Respect API rate limit

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
        if 'covr' in audio and audio['covr']:
            artwork = audio['covr'][0]
        elif 'APIC:' in audio and audio['APIC:']:
            artwork = audio['APIC:'].data
        elif audio.pictures:
            artwork = audio.pictures[0].data
        
        if artwork:
            with open(os.path.join(title_dir, "cover.jpg"), "wb") as img_file:
                img_file.write(artwork)
            print("  - Cover art extracted and saved.")
            return True
        else:
            return False

    except Exception as e:
        print(f"  - Could not process file for cover art: {e}")
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
                print(f"  - A 'cover.jpg' already exists in the destination. Skipping move of '{file}'.")
                os.remove(source_image_path)
                return True

            shutil.move(source_image_path, destination_image_path)
            print(f"  - Found and moved existing cover file: '{file}'")
            return True
    return False

def get_base_name(filename):
    """
    Extracts a base name from a file to group audiobooks.
    """
    name_without_extension = os.path.splitext(filename)[0]
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
    """
    os.makedirs(staging_dir, exist_ok=True)
    supported_images = ('.jpg', '.jpeg', '.png')
    base_name_map = defaultdict(list)
    
    print("Scanning and grouping source directory...")
    for item in os.listdir(source_dir):
        source_path = os.path.join(source_dir, item)
        if os.path.abspath(source_path) == os.path.abspath(staging_dir):
            continue

        if os.path.isdir(source_path):
            print(f"Moving existing folder '{item}' to staging area.")
            shutil.move(source_path, os.path.join(staging_dir, item))
            continue

        if item.lower().endswith(AUDIO_EXTENSIONS) or item.lower().endswith(supported_images):
            base_name = get_base_name(item)
            if base_name:
                base_name_map[base_name].append(item)

    print(f"Found {len(base_name_map)} potential groups among loose files.")
    for base_name, file_list in base_name_map.items():
        if not any(f.lower().endswith(AUDIO_EXTENSIONS) for f in file_list):
            continue

        folder_name = sanitize_filename(base_name.title())
        dest_folder = os.path.join(staging_dir, folder_name)
        os.makedirs(dest_folder, exist_ok=True)
        
        print(f"\nCreating group '{folder_name}' with {len(file_list)} file(s).")
        for file in file_list:
            source_file_path = os.path.join(source_dir, file)
            if os.path.exists(source_file_path):
                shutil.move(source_file_path, os.path.join(dest_folder, file))
                print(f"  - Moved '{file}' to folder '{folder_name}'")

def download_cover_from_internet(book_data, title_dir):
    """
    Searches the internet for a book cover using DuckDuckGo and downloads the first result.
    """
    try:
        title = book_data.get("title", "")
        author = book_data.get("author", "")
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

def organize_audio_files(base_dir, dest_dir):
    """
    Walks the directory, groups audio files by folder, organizes them,
    and maintains an inventory file in CSV format.
    """
    unclassified_dir = os.path.join(dest_dir, "unclassified")
    os.makedirs(dest_dir, exist_ok=True)
    os.makedirs(unclassified_dir, exist_ok=True)
    books_without_cover = []

    csv_path = os.path.join(dest_dir, "inventory.csv")
    if not os.path.isfile(csv_path):
        try:
            with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile, delimiter='|')
                writer.writerow(["Title", "Author", "Genre", "Series", "Year", "Synopsis", "Path", "ProcessingDate", "FileCount", "TotalSizeMB", "CoverArtFound"])
        except IOError as e:
            print(f"Error: Could not write CSV inventory file at '{csv_path}': {e}")
            return []

    for root, _, files in os.walk(base_dir):
        if os.path.abspath(root) == os.path.abspath(base_dir):
            continue

        try:
            audio_files = [f for f in files if f.lower().endswith(AUDIO_EXTENSIONS)]
            if not audio_files:
                continue

            print(f"\nProcessing group from folder: {os.path.basename(root)}")

            processing_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            file_count = len(audio_files)
            try:
                total_size_bytes = sum(os.path.getsize(os.path.join(root, f)) for f in audio_files)
                total_size_mb = round(total_size_bytes / (1024 * 1024), 2)
            except FileNotFoundError:
                total_size_mb = 0

            gemini_info_string = os.path.basename(root)
            print(f"Using '{gemini_info_string}' to get book information...")
            book_data = get_book_info_from_gemini(gemini_info_string)

            if book_data and book_data["title"] != "Unknown":
                # Add author to our knowledge base
                add_author_to_known_list(book_data["author"])
                author_folder_name = sanitize_filename(book_data["author"].title())
                title_folder_name = sanitize_filename(book_data["title"].title())
                relative_path = os.path.join(author_folder_name, title_folder_name)

                author_dir = os.path.join(dest_dir, author_folder_name)
                title_dir = os.path.join(author_dir, title_folder_name)
                os.makedirs(title_dir, exist_ok=True)

                print("Searching for cover art...")
                cover_art_found = handle_existing_cover_file(root, title_dir)
                if not cover_art_found:
                    print("No local image file found, trying to extract embedded cover...")
                    cover_art_found = extract_cover_art(os.path.join(root, audio_files[0]), title_dir)
                if not cover_art_found:
                    print("No embedded cover found.")
                    cover_art_found = download_cover_from_internet(book_data, title_dir)
                
                if cover_art_found:
                    print("Cover art processing complete.")
                else:
                    print("Could not find a cover for this book.")
                    books_without_cover.append(relative_path)

                book_data['processing_date'] = processing_date
                book_data['file_count'] = file_count
                book_data['total_size_mb'] = total_size_mb
                book_data['cover_art_found'] = cover_art_found
                book_data['original_files'] = audio_files

                with open(os.path.join(title_dir, "metadata.json"), "w", encoding="utf-8") as f:
                    json.dump(book_data, f, ensure_ascii=False, indent=4)
                print("Metadata saved to metadata.json")

                try:
                    with open(csv_path, 'a', newline='', encoding='utf-8') as csvfile:
                        writer = csv.writer(csvfile, delimiter='|')
                        writer.writerow([book_data.get("title", ""), book_data.get("author", ""), book_data.get("genre", ""), book_data.get("series", ""), book_data.get("year", ""), book_data.get("synopsis", ""), relative_path, processing_date, file_count, total_size_mb, cover_art_found])
                    print("Book data added to CSV inventory.")
                except IOError as e:
                    print(f"Warning: Could not append entry to CSV inventory: {e}")

                for file in audio_files:
                    shutil.move(os.path.join(root, file), os.path.join(title_dir, file))
                print(f"All files moved to: {title_dir}")

                try:
                    os.rmdir(root)
                    print(f"Temporary book folder deleted: {root}")
                except OSError as e:
                    print(f"Warning: Could not delete temporary folder '{root}': {e}")
            else:
                print(f"Could not classify group '{os.path.basename(root)}'. Moving to 'unclassified'.")
                shutil.move(root, find_unique_foldername(os.path.join(unclassified_dir, os.path.basename(root))))

        except Exception as e:
            print(f"\n--- ERROR processing folder: {os.path.basename(root)} ---")
            print(f"An unexpected error occurred: {e}")
            print("This folder will be skipped and will remain in the staging directory for manual review.")
        
        finally:
            # Add a delay to avoid rate-limiting APIs
            print("Pausing for 2 seconds...")
            time.sleep(2)
    
    return books_without_cover

def main():
    parser = argparse.ArgumentParser(
        description="Audiobook Sorter. Groups, classifies, and organizes audiobook files.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("source_directory", help="The directory containing the audiobooks to organize.")
    parser.add_argument("-d", "--destination_directory", default=None, help="The directory where organized audiobooks will be saved. Defaults to the source directory (in-place sort).")
    args = parser.parse_args()

    source_dir_abs = os.path.abspath(args.source_directory)

    if args.destination_directory:
        dest_dir_abs = os.path.abspath(args.destination_directory)
    else:
        print("No destination directory specified. Defaulting to source directory for in-place sort.")
        dest_dir_abs = source_dir_abs

    if not os.path.isdir(source_dir_abs):
        print(f"\nError: The source directory '{source_dir_abs}' does not exist or is not a directory.")
        return

    parent_dir = os.path.dirname(source_dir_abs)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    staging_dir_name = f"_ebooksort_staging_{timestamp}"
    staging_dir = os.path.join(parent_dir, staging_dir_name)

    try:
        os.makedirs(staging_dir, exist_ok=True)

        print(f"Source Directory: {source_dir_abs}")
        print(f"Destination Directory: {dest_dir_abs}")
        print(f"Using safe staging directory: {staging_dir}")

        print("\n--- Phase 1: Grouping files into staging area ---")
        pre_organize_into_folders(source_dir_abs, staging_dir)

        print("\n--- Phase 2: Classifying and organizing folders ---")
        books_without_cover = organize_audio_files(staging_dir, dest_dir_abs)

        print(f"\nProcess finished. Checking for unprocessed items in staging area...")
        remaining_items = os.listdir(staging_dir)
        if not remaining_items:
            print("Staging directory is empty. Cleaning up.")
            shutil.rmtree(staging_dir)
            print("Staging directory cleanup completed.")
        else:
            print("\n--- WARNING: Items remain in the staging directory ---")
            print("The following items were not processed due to errors and require manual review:")
            for item in remaining_items:
                print(f"  - {item}")
            print(f"Staging directory location: {staging_dir}")

        if books_without_cover:
            print("\n--- Books Missing Covers ---")
            print("The following books were processed but a cover image could not be found:")
            for book_path in sorted(books_without_cover):
                print(f"  - {book_path}")

    except (KeyboardInterrupt, Exception) as e:
        print("\n--- A CRITICAL ERROR OCCURRED ---")
        print(f"The script was interrupted by: {type(e).__name__}")
        if os.path.exists(staging_dir):
            print("\nYour files are safe in the staging directory:")
            print(f"  -> {staging_dir}")
        print("Please review the folder and the error messages before running the script again.")


if __name__ == "__main__":
    main()
