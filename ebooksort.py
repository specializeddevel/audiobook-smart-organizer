# ebooksort.py
import os
import sys
import shutil
import google.generativeai as genai
import re
import time
import json
import mutagen
import argparse
import datetime
from collections import defaultdict
import requests
from ddgs import DDGS
from logging_config import get_logger, close_logger
from config_manager import config

# Initialize logger
logger = get_logger(__file__)

# Exit if the configuration failed to load
if not config:
    logger.error("Configuration could not be loaded. Please check for a valid config.ini file.")
    sys.exit(1)

# Configure the Gemini API using an environment variable
try:
    GOOGLE_API_KEY = os.environ["GOOGLE_API_KEY"]
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel(config.gemini['model_name'])
    logger.info("Gemini API configured successfully.")
except KeyError:
    logger.error("The GOOGLE_API_KEY environment variable is not set.")
    sys.exit(1)

def add_author_to_known_list(author_name, filepath=None, dry_run=False):
    if filepath is None:
        filepath = config.general['authors_filename']
    if not author_name or author_name == "Unknown":
        return
    author_to_add = author_name.strip().title()
    try:
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                existing_authors = {line.strip().lower() for line in f}
        else:
            existing_authors = set()
        if author_to_add.lower() not in existing_authors:
            if not dry_run:
                with open(filepath, 'a', encoding='utf-8') as f:
                    f.write(author_to_add + '\n')
                logger.info(f"  - Author '{author_to_add}' added to known authors list.")
            else:
                logger.info(f"  - DRY RUN: Would add author '{author_to_add}' to known authors list.")
    except IOError as e:
        logger.warning(f"Could not read or write to authors file '{filepath}': {e}")

def get_book_info_from_gemini(info_string, dry_run=False):
    if dry_run:
        logger.info(f"DRY RUN: Would call Gemini API for info string: '{info_string}'")
        return {"title": f"Title for {info_string}", "author": "Mock Author", "genre": "Mock Genre", "series": "Mock Series", "year": "2023", "synopsis": "This is a mock synopsis from a dry run."}
    
    prompt = config.gemini['prompt'].format(info_string=info_string)
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
        logger.info(f"Title: {title}\nAuthor: {author}\nGenre: {genre}\nSeries: {series}\nYear: {year}\nSynopsis: {synopsis}")
        return {"title": title, "author": author, "genre": genre, "series": series, "year": year, "synopsis": synopsis}
    except Exception as e:
        logger.error(f"Error contacting Gemini: {e}")
        return None
    finally:
        time.sleep(config.gemini['api_cooldown'])

def sanitize_filename(name):
    clean_name = re.sub(r'[\\/*?<>|":]', "", name)
    clean_name = clean_name.strip()
    clean_name = re.sub(r'\s+', ' ', clean_name)
    return clean_name

def extract_cover_art(file_path, title_dir, dry_run=False):
    try:
        audio = mutagen.File(file_path, easy=False)
        if not audio: return False
        artwork = None
        if 'covr' in audio and audio['covr']: artwork = audio['covr'][0]
        elif 'APIC:' in audio and audio['APIC:']: artwork = audio['APIC:'].data
        elif audio.pictures: artwork = audio.pictures[0].data
        if artwork:
            if not dry_run:
                with open(os.path.join(title_dir, "cover.jpg"), "wb") as img_file:
                    img_file.write(artwork)
                logger.info("  - Cover art extracted and saved.")
            else:
                logger.info("  - DRY RUN: Would extract and save cover art as cover.jpg")
            return True
        return False
    except Exception as e:
        logger.warning(f"Could not process file for cover art: {e}")
        return False

def handle_existing_cover_file(source_folder, destination_folder, dry_run=False):
    supported_images = config.general['image_extensions']
    for file in os.listdir(source_folder):
        if file.lower().endswith(supported_images):
            source_image_path = os.path.join(source_folder, file)
            destination_image_path = os.path.join(destination_folder, "cover.jpg")
            if os.path.exists(destination_image_path):
                logger.info(f"  - A 'cover.jpg' already exists. Skipping move of '{file}'.")
                if not dry_run: os.remove(source_image_path)
                else: logger.info(f"  - DRY RUN: Would remove redundant source image: '{source_image_path}'")
                return True
            if not dry_run: shutil.move(source_image_path, destination_image_path)
            logger.info(f"  - {'DRY RUN: Would move' if dry_run else 'Found and moved'} existing cover file: '{file}'")
            return True
    return False

def get_base_name(filename):
    name_without_extension = os.path.splitext(filename)[0]
    patterns = [r'[\s_-]+part?\s*\d+', r'[\s_-]+chapter?\s*\d+', r'[\s_-]+cap\s*\d+', r'[\s_-]+cd\s*\d+', r'[\s_-]+\d+$', r'\s*\(\d+\)$' ]
    base_name = name_without_extension
    for pattern in patterns:
        base_name = re.sub(pattern, '', base_name, flags=re.IGNORECASE).strip()
    base_name = re.sub(r'\s+', ' ', base_name).strip()
    return base_name if base_name else name_without_extension

def find_unique_foldername(path):
    if not os.path.exists(path): return path
    base, name = os.path.split(path)
    counter = 2
    while True:
        new_name = f"{name} ({counter})"
        new_path = os.path.join(base, new_name)
        if not os.path.exists(new_path): return new_path
        counter += 1

def pre_organize_into_folders(source_dir, staging_dir, dry_run=False):
    if not dry_run: os.makedirs(staging_dir, exist_ok=True)
    supported_images = config.general['image_extensions']
    audio_extensions = config.general['audio_extensions']
    base_name_map = defaultdict(list)
    logger.info("Scanning and grouping source directory...")
    for item in os.listdir(source_dir):
        source_path = os.path.join(source_dir, item)
        if os.path.abspath(source_path) == os.path.abspath(staging_dir): continue
        if os.path.isdir(source_path):
            if not dry_run: shutil.move(source_path, os.path.join(staging_dir, item))
            logger.info(f"{ 'DRY RUN: Would move' if dry_run else 'Moving'} existing folder '{item}' to staging area.")
            continue
        if item.lower().endswith(audio_extensions) or item.lower().endswith(supported_images):
            base_name = get_base_name(item)
            if base_name: base_name_map[base_name].append(item)
    logger.info(f"Found {len(base_name_map)} potential groups among loose files.")
    for base_name, file_list in base_name_map.items():
        if not any(f.lower().endswith(audio_extensions) for f in file_list): continue
        folder_name = sanitize_filename(base_name.title())
        dest_folder = os.path.join(staging_dir, folder_name)
        if not dry_run: os.makedirs(dest_folder, exist_ok=True)
        logger.info(f"\nCreating group '{folder_name}' with {len(file_list)} file(s).")
        for file in file_list:
            source_file_path = os.path.join(source_dir, file)
            if os.path.exists(source_file_path):
                if not dry_run: shutil.move(source_file_path, os.path.join(dest_folder, file))
                logger.info(f"  - {'DRY RUN: Would move' if dry_run else 'Moved'} '{file}' to folder '{folder_name}'")

def download_cover_from_internet(book_data, title_dir, dry_run=False):
    if dry_run:
        logger.info(f"  - DRY RUN: Would search online for cover for title: '{book_data.get('title')}'")
        return False
    try:
        title = book_data.get("title", "")
        author = book_data.get("author", "")
        if not title or title == "Unknown" or not author or author == "Unknown": return False
        keywords = f'{title} {author} book cover'
        logger.info(f"  - Searching for cover online with keywords: \"{keywords}\"")
        with DDGS() as ddgs:
            results = list(ddgs.images(keywords, max_results=5))
        if not results: return False
        response = requests.get(results[0]["image"], stream=True, timeout=15)
        response.raise_for_status()
        with open(os.path.join(title_dir, "cover.jpg"), 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192): f.write(chunk)
        logger.info("  - Successfully downloaded and saved cover.jpg.")
        return True
    except Exception as e:
        logger.error(f"Failed to download cover: {e}")
        return False

def organize_audio_files(base_dir, dest_dir, dry_run=False):
    unclassified_dir = os.path.join(dest_dir, "unclassified")
    no_cover_dir = os.path.join(dest_dir, config.general['no_cover_folder'])
    audio_extensions = config.general['audio_extensions']
    
    if not dry_run:
        os.makedirs(dest_dir, exist_ok=True)
        os.makedirs(unclassified_dir, exist_ok=True)
        os.makedirs(no_cover_dir, exist_ok=True)
    else:
        logger.info(f"DRY RUN: Would ensure destination directory exists: {dest_dir}")
        logger.info(f"DRY RUN: Would ensure unclassified directory exists: {unclassified_dir}")
        logger.info(f"DRY RUN: Would ensure 'no cover' directory exists: {no_cover_dir}")
        
    books_without_cover = []
    if dry_run and not os.path.exists(base_dir): return books_without_cover

    for root, _, files in os.walk(base_dir):
        if os.path.abspath(root) == os.path.abspath(base_dir): continue
        try:
            audio_files = [f for f in files if f.lower().endswith(audio_extensions)]
            if not audio_files: continue

            logger.info(f"\nProcessing group from folder: {os.path.basename(root)}")
            gemini_info_string = os.path.basename(root)
            logger.info(f"Using '{gemini_info_string}' to get book information...")
            book_data = get_book_info_from_gemini(gemini_info_string, dry_run=dry_run)

            if book_data and book_data["title"] != "Unknown":
                author_folder_name = sanitize_filename(book_data["author"].title())
                title_folder_name = sanitize_filename(book_data["title"].title())
                
                # Create the final book directory in the main library first
                author_dir = os.path.join(dest_dir, author_folder_name)
                title_dir = os.path.join(author_dir, title_folder_name)
                if not dry_run: os.makedirs(title_dir, exist_ok=True)
                else: logger.info(f"DRY RUN: Would ensure book directory exists: {title_dir}")

                add_author_to_known_list(book_data["author"], dry_run=dry_run)

                # --- Move files and handle covers ---
                for file in audio_files:
                    if not dry_run: shutil.move(os.path.join(root, file), os.path.join(title_dir, file))
                    logger.info(f"{ 'DRY RUN: Would move' if dry_run else 'Moved'} file '{file}' to '{title_dir}'")

                logger.info("Searching for cover art...")
                cover_art_found = handle_existing_cover_file(root, title_dir, dry_run=dry_run)
                if not cover_art_found: cover_art_found = extract_cover_art(os.path.join(title_dir, audio_files[0]), title_dir, dry_run=dry_run)
                if not cover_art_found: cover_art_found = download_cover_from_internet(book_data, title_dir, dry_run=dry_run)

                # --- Create metadata.json ---
                logger.info("Analyzing audio files for chapter generation...")
                chapters = []
                current_time_s = 0.0
                # Analyze files from their new location in title_dir
                sorted_audio_files_for_chapters = sorted([f for f in os.listdir(title_dir) if f.lower().endswith(audio_extensions)])
                for i, filename in enumerate(sorted_audio_files_for_chapters):
                    try:
                        audio_path = os.path.join(title_dir, filename)
                        audio_info = mutagen.File(audio_path)
                        if audio_info: 
                            duration_s = audio_info.info.length
                            chapters.append({"id": i, "start": current_time_s, "end": current_time_s + duration_s, "title": os.path.splitext(filename)[0].replace('_', ' ').title()})
                            current_time_s += duration_s
                    except Exception as e: 
                        logger.warning(f"Error processing '{filename}' for duration: {e}")
                
                author = book_data.get("author", "Unknown")
                series = book_data.get("series", "Unknown")
                genre = book_data.get("genre", "Unknown")
                audiobookshelf_data = {"tags": [], "chapters": chapters, "title": book_data.get("title", "Unknown"), "subtitle": None, "authors": [] if author == "Unknown" else [author], "narrators": [], "series": [] if series == "Unknown" else [{"name": series}], "genres": [] if genre == "Unknown" else [genre], "publishedYear": book_data.get("year", None), "publishedDate": None, "publisher": None, "description": book_data.get("synopsis", None), "isbn": None, "asin": None, "language": None, "explicit": False, "abridged": False}
                
                if not dry_run:
                    with open(os.path.join(title_dir, "metadata.json"), "w", encoding="utf-8") as f: 
                        json.dump(audiobookshelf_data, f, ensure_ascii=False, indent=2)
                    logger.info("Metadata saved to metadata.json in audiobookshelf format.")
                else: 
                    logger.info(f"DRY RUN: Would save metadata.json to: {title_dir}")

                # --- Final Placement --- 
                if cover_art_found:
                    logger.info("Cover art processing complete. Book is fully organized.")
                else:
                    logger.warning(f"  - No cover found for '{title_folder_name}'. Moving to '{no_cover_dir}'.")
                    final_destination = find_unique_foldername(os.path.join(no_cover_dir, author_folder_name, title_folder_name))
                    books_without_cover.append(final_destination)
                    if not dry_run:
                        os.makedirs(os.path.dirname(final_destination), exist_ok=True)
                        shutil.move(title_dir, final_destination)
                    else:
                        logger.info(f"  - DRY RUN: Would move '{title_dir}' to '{final_destination}'")

                if not dry_run:
                    try: os.rmdir(root)
                    except OSError as e: logger.warning(f"Could not delete temporary folder '{root}': {e}")
                else: logger.info(f"DRY RUN: Would delete temporary book folder: {root}")

            else:
                logger.info(f"Could not classify group '{os.path.basename(root)}'. Moving to 'unclassified'.")
                if not dry_run: shutil.move(root, find_unique_foldername(os.path.join(unclassified_dir, os.path.basename(root))))
                else: logger.info(f"DRY RUN: Would move group '{os.path.basename(root)}' to 'unclassified'.")
        except Exception as e: 
            logger.error(f"--- ERROR processing folder: {os.path.basename(root)} ---\nAn unexpected error occurred: {e}\nThis folder will be skipped and will remain in the staging directory for manual review.")
        finally:
            if not dry_run: time.sleep(config.gemini['api_cooldown'])
    return books_without_cover

def main():
    parser = argparse.ArgumentParser(description="Audiobook Sorter. Groups, classifies, and organizes audiobook files.", formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("source_directory", help="The directory containing the audiobooks to organize.")
    parser.add_argument("-d", "--destination_directory", default=None, help="The directory where organized audiobooks will be saved. Defaults to the source directory (in-place sort).")
    parser.add_argument("--dry-run", action="store_true", help="Perform a simulation without moving files or calling APIs.")
    args = parser.parse_args()
    source_dir_abs = os.path.abspath(args.source_directory)
    if args.destination_directory: dest_dir_abs = os.path.abspath(args.destination_directory)
    else: dest_dir_abs = source_dir_abs
    if not os.path.isdir(source_dir_abs): logger.error(f"The source directory '{source_dir_abs}' does not exist or is not a directory."); return
    if args.dry_run: logger.info("\n--- PERFORMING A DRY RUN ---\nNo files will be moved, deleted, or modified. No APIs will be called.\n")
    parent_dir = os.path.dirname(source_dir_abs)
    staging_dir = os.path.join(parent_dir, f"_ebooksort_staging_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}")
    try:
        if not args.dry_run: os.makedirs(staging_dir, exist_ok=True)
        else: logger.info(f"DRY RUN: Would create staging directory: {staging_dir}")
        logger.info(f"Source Directory: {source_dir_abs}\nDestination Directory: {dest_dir_abs}\nUsing safe staging directory: {staging_dir}")
        logger.info("\n--- Phase 1: Grouping files into staging area ---")
        pre_organize_into_folders(source_dir_abs, staging_dir, dry_run=args.dry_run)
        logger.info("\n--- Phase 2: Classifying and organizing folders ---")
        books_without_cover = organize_audio_files(staging_dir, dest_dir_abs, dry_run=args.dry_run)
        logger.info(f"\nProcess finished. Checking for unprocessed items in staging area...")
        if args.dry_run and not os.path.exists(staging_dir): remaining_items = []
        else: remaining_items = os.listdir(staging_dir)
        if not remaining_items:
            logger.info("Staging directory is empty. Cleaning up.")
            if not args.dry_run: shutil.rmtree(staging_dir)
            else: logger.info(f"DRY RUN: Would delete staging directory: {staging_dir}")
        else:
            logger.warning("--- Items remain in the staging directory ---")
            for item in remaining_items: logger.info(f"  - {item}")
            logger.info(f"Staging directory location: {staging_dir}")
        if books_without_cover:
            no_cover_folder_name = config.general['no_cover_folder']
            logger.info(f"\n--- Books Missing Covers (Moved to '{no_cover_folder_name}') ---")
            for book_path in sorted(books_without_cover):
                logger.info(f"  - {book_path}")
    except (KeyboardInterrupt, Exception) as e:
        logger.critical(f"--- A CRITICAL ERROR OCCURRED ---\nThe script was interrupted by: {type(e).__name__}")
        if os.path.exists(staging_dir): logger.info(f"\nYour files are safe in the staging directory:\n  -> {staging_dir}")
        logger.info("Please review the folder and the error messages before running the script again.")
    finally:
        close_logger(logger)

if __name__ == "__main__":
    main()