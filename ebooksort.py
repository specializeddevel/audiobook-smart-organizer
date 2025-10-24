# ebooksort.py
import os
import sys
import shutil
import google.generativeai as genai
from PIL import Image
import re
import time
import json
import mutagen
import argparse
import datetime
from collections import defaultdict
import requests
from ddgs import DDGS
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC, TPE1, TALB, TIT2, TCON, TDRC, TRCK, COMM
from mutagen.mp4 import MP4, MP4Cover
from mutagen.flac import FLAC, Picture
from logging_config import get_logger, close_logger
from config_manager import config

# Initialize logger
logger = get_logger(__file__)

# Exit if the configuration failed to load
if not config:
    logger.error("Configuration could not be loaded. Please check for a valid config.ini file.")
    sys.exit(1)

# Configure the Gemini API using the key from config.ini
try:
    api_key = config.gemini['api_key']
    if not api_key or api_key == "YOUR_API_KEY_HERE":
        logger.error("Gemini API key is not set in config.ini. Please add it to the [Gemini] section.")
        sys.exit(1)
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(config.gemini['model_name'])
    logger.info("Gemini API configured successfully.")
except (KeyError, AttributeError):
    logger.error("Failed to configure Gemini API. Make sure the api_key is set in config.ini.")
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

def get_book_info_from_google_books(info_string, dry_run=False):
    if dry_run:
        logger.info(f"DRY RUN: Would search Google Books for: '{info_string}'")
        return None
    try:
        search_url = f"https://www.googleapis.com/books/v1/volumes?q={info_string}"
        response = requests.get(search_url)
        response.raise_for_status()
        data = response.json()
        if "items" not in data or not data["items"]:
            logger.info("No results found on Google Books.")
            return None
        
        book_info = data["items"][0]["volumeInfo"]
        title = book_info.get("title", "Unknown")
        authors = book_info.get("authors", ["Unknown"])
        author = authors[0]
        synopsis = book_info.get("description", "Unknown")
        published_date = book_info.get("publishedDate", "Unknown")
        year = published_date.split('-')[0] if published_date != "Unknown" else "Unknown"
        categories = book_info.get("categories", ["Unknown"])
        genre = categories[0]
        
        logger.info(f"Found on Google Books: Title: {title}, Author: {author}")
        return {"title": title, "author": author, "synopsis": synopsis, "genre": genre, "series": "Unknown", "year": year}

    except Exception as e:
        logger.error(f"Error searching Google Books: {e}")
        return None


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
    if not dry_run:
        os.makedirs(staging_dir, exist_ok=True)

    logger.info("Standardizing filenames by replacing '_' and '-' with spaces...")
    # We need to list items before iterating to avoid issues with renaming
    items_to_process = os.listdir(source_dir)
    for item in items_to_process:
        source_path = os.path.join(source_dir, item)
        
        # Check if the path still exists, as it might have been renamed if it was part of a directory that got renamed
        if not os.path.exists(source_path):
            continue

        # Don't touch the staging directory if it's inside the source
        if os.path.abspath(source_path) == os.path.abspath(staging_dir):
            continue

        # Standardize name by replacing separators and collapsing spaces
        new_item_name = item.replace('_', ' ').replace('-', ' ')
        new_item_name = re.sub(r'\s+', ' ', new_item_name).strip()

        if new_item_name != item:
            new_path = os.path.join(source_dir, new_item_name)
            
            if os.path.exists(new_path):
                logger.warning(f"  - Cannot rename '{item}' to '{new_item_name}' because the destination already exists. Skipping.")
                continue
            
            if not dry_run:
                try:
                    os.rename(source_path, new_path)
                    logger.info(f"  - Renamed '{item}' to '{new_item_name}'")
                except OSError as e:
                    logger.error(f"  - Error renaming '{item}' to '{new_item_name}': {e}")
            else:
                logger.info(f"  - DRY RUN: Would rename '{item}' to '{new_item_name}'")
    logger.info("Filename standardization complete.")

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

def analyze_cover(image_path):
    """Analyzes a cover image for its dimensions and quality."""
    min_resolution = config.covers['min_resolution']
    if not os.path.exists(image_path):
        return {"exists": False}
    try:
        with Image.open(image_path) as img:
            width, height = img.size
            is_square = (width == height)
            is_low_quality = (width < min_resolution or height < min_resolution)
            return {
                "exists": True,
                "is_square": is_square,
                "is_low_quality": is_low_quality,
                "dimensions": f"{width}x{height}"
            }
    except Exception as e:
        logger.error(f"  - Could not analyze image {os.path.basename(image_path)}: {e}")
        return {"exists": True, "error": str(e)}

def download_cover_from_itunes(book_data, destination_path, dry_run=False):
    """
    Searches iTunes for a book cover and downloads it.
    """
    if dry_run:
        logger.info(f"  - DRY RUN: Would search iTunes for cover for title: '{book_data.get('title')}'")
        logger.info(f"  - DRY RUN: Would save cover to: {destination_path}")
        return True
    try:
        title = book_data.get("title", "")
        author = book_data.get("author", "")
        if not title or title == "Unknown" or not author or author == "Unknown":
            return False

        search_term = f"{title} {author}"
        logger.info(f"  - Searching for cover on iTunes with term: \"{search_term}\"")

        params = {
            "term": search_term,
            "media": "ebook",
            "entity": "ebook",
            "limit": 1,
            "country": "US"
        }
        response = requests.get("https://itunes.apple.com/search", params=params, timeout=15)
        response.raise_for_status()
        results = response.json()

        if results["resultCount"] > 0:
            artwork_url = results["results"][0].get("artworkUrl100")
            if artwork_url:
                high_res_url = artwork_url.replace("100x100bb.jpg", "1000x1000bb.jpg")
                logger.info(f"    - Found artwork URL: {high_res_url}")

                image_response = requests.get(high_res_url, stream=True, timeout=15)
                image_response.raise_for_status()

                with open(destination_path, 'wb') as f:
                    for chunk in image_response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                logger.info(f"    - Successfully downloaded and saved cover to {os.path.basename(destination_path)} from iTunes.")
                return True
        
        logger.info("    - No cover found on iTunes.")
        return False
    except Exception as e:
        logger.error(f"    - Error searching or downloading cover from iTunes: {e}")
        return False

def download_cover_from_internet(book_data, destination_path, dry_run=False):
    if dry_run:
        logger.info(f"  - DRY RUN: Would search online for cover for title: '{book_data.get('title')}'")
        return True
    try:
        title = book_data.get("title", "")
        author = book_data.get("author", "")
        if not title or title == "Unknown" or not author or author == "Unknown": return False
        
        keywords = f'{title} {author} book cover'
        logger.info(f"  - Searching for cover online with keywords: \"{keywords}\"")

        logger.info("    - Prioritizing square images...")
        with DDGS() as ddgs:
            square_results = list(ddgs.images(keywords, layout='Square', max_results=10))

        for result in square_results:
            if result.get('width') == result.get('height'):
                logger.info(f"    - Found square image: {result['image']}")
                try:
                    response = requests.get(result["image"], stream=True, timeout=15)
                    response.raise_for_status()
                    with open(destination_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192): f.write(chunk)
                    logger.info(f"    - Successfully downloaded and saved square cover to {os.path.basename(destination_path)}.")
                    return True
                except Exception as e:
                    logger.warning(f"    - Failed to download square image candidate: {e}. Trying next...")
        
        logger.info("    - No suitable square image found. Performing general search...")
        with DDGS() as ddgs:
            general_results = list(ddgs.images(keywords, max_results=5))

        if not general_results:
            logger.info("    - General search returned no results.")
            return False

        response = requests.get(general_results[0]["image"], stream=True, timeout=15)
        response.raise_for_status()
        with open(destination_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192): f.write(chunk)
        logger.info(f"    - Successfully downloaded and saved cover to {os.path.basename(destination_path)} from general search.")
        return True

    except Exception as e:
        logger.error(f"  - An error occurred during cover download: {e}")
        return False

def tag_audio_file(file_path, metadata, cover_image_data, track_num, total_tracks, dry_run=False):
    """
    Applies metadata tags to a single audio file.
    """
    try:
        audio = mutagen.File(file_path, easy=False)
        if audio is None:
            raise ValueError("Could not load file.")

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
            album_title = config.tagging['album_title_format'].format(title=title, series_name=series_name)

        track_title = album_title
        if total_tracks > 1:
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            if base_name.lower().startswith(("chapter", "capitulo", "part", "parte")):
                 track_title = base_name.replace('_', ' ').title()
            else:
                 track_title = config.tagging['track_title_format'].format(track_num=track_num, base_name=base_name)

        if isinstance(audio, MP3):
            audio.tags = ID3()
            audio.tags.add(TPE1(encoding=3, text=author))
            audio.tags.add(TALB(encoding=3, text=album_title))
            audio.tags.add(TIT2(encoding=3, text=track_title))
            audio.tags.add(TCON(encoding=3, text=genre))
            audio.tags.add(TRCK(encoding=3, text=f"{track_num}/{total_tracks}"))
            if year: audio.tags.add(TDRC(encoding=3, text=str(year)))
            if synopsis: 
                audio.tags.add(COMM(encoding=3, lang='eng', desc='Synopsis', text=synopsis))
                audio.tags.add(COMM(encoding=3, lang='eng', desc='', text=synopsis))
            if cover_image_data:
                audio.tags.add(APIC(encoding=3, mime='image/jpeg', type=3, desc='Cover', data=cover_image_data))
        
        elif isinstance(audio, MP4):
            audio.tags["\xa9ART"] = author
            audio.tags["\xa9alb"] = album_title
            audio.tags["\xa9nam"] = track_title
            audio.tags["\xa9gen"] = genre
            audio.tags["trkn"] = [(track_num, total_tracks)]
            if year: audio.tags["\xa9day"] = str(year)
            if synopsis: 
                audio.tags["ldes"] = synopsis
                audio.tags["\xa9cmt"] = synopsis
            if cover_image_data:
                audio.tags["covr"] = [MP4Cover(cover_image_data, imageformat=MP4Cover.FORMAT_JPEG)]

        elif isinstance(audio, mutagen.flac.FLAC):
            audio["ARTIST"] = author
            audio["ALBUM"] = album_title
            audio["TITLE"] = track_title
            audio["GENRE"] = genre
            audio["TRACKNUMBER"] = str(track_num)
            audio["TRACKTOTAL"] = str(total_tracks)
            if year: audio["DATE"] = str(year)
            if synopsis: 
                audio["DESCRIPTION"] = synopsis
                audio["COMMENT"] = synopsis
            if cover_image_data:
                pic = Picture()
                pic.type = 3
                pic.mime = "image/jpeg"
                pic.desc = "Cover"
                pic.data = cover_image_data
                audio.add_picture(pic)
        else:
            logger.warning(f"      - Unsupported file type for tagging: {type(audio)}. Skipping.")
            return

        if not dry_run:
            audio.save()
        
        logger.info(f"      - {'DRY RUN: Would tag' if dry_run else 'Successfully tagged'}: {os.path.basename(file_path)}")

    except Exception as e:
        logger.error(f"      - ERROR: Failed to tag {os.path.basename(file_path)}: {e}")

def organize_audio_files(base_dir, dest_dir, dry_run=False, no_tagging=False, force_gemini=False):
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
            info_string = os.path.basename(root)
            
            book_data = None
            if not force_gemini:
                # First, try to get info from Google Books
                logger.info(f"Searching Google Books for '{info_string}'...")
                book_data = get_book_info_from_google_books(info_string, dry_run=dry_run)

            # If not found on Google Books, or if the result is incomplete, or if Gemini is forced, try Gemini
            if force_gemini or not book_data or book_data["title"] == "Unknown":
                if force_gemini:
                    logger.info("Forcing Gemini lookup as per user request.")
                else:
                    logger.info("Not found on Google Books or result was incomplete. Falling back to Gemini.")
                
                logger.info(f"Using '{info_string}' to get book information from Gemini...")
                book_data = get_book_info_from_gemini(info_string, dry_run=dry_run)

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
                if not cover_art_found:
                    cover_art_found = extract_cover_art(os.path.join(title_dir, audio_files[0]), title_dir, dry_run=dry_run)
                
                if not cover_art_found:
                    itunes_temp_path = os.path.join(title_dir, "itunes_cover.tmp")
                    destination_path = os.path.join(title_dir, "cover.jpg")
                    
                    itunes_success = download_cover_from_itunes(book_data, itunes_temp_path, dry_run)
                    
                    if itunes_success:
                        analysis = analyze_cover(itunes_temp_path)
                        # A good cover is square and not low quality
                        is_good_cover = analysis.get("is_square") and not analysis.get("is_low_quality")

                        if dry_run or is_good_cover:
                            logger.info(f"  - iTunes cover is good quality (or dry run). Using it. ({analysis.get('dimensions', 'N/A')})")
                            if not dry_run: shutil.move(itunes_temp_path, destination_path)
                            else: logger.info(f"  - DRY RUN: Would move iTunes temp cover to cover.jpg")
                            cover_art_found = True
                        else:
                            logger.warning(f"  - iTunes cover is not ideal ({analysis.get('dimensions', 'N/A')}). Trying DDGS for a better one...")
                            if download_cover_from_internet(book_data, destination_path, dry_run):
                                logger.info("  - Found a better cover on DDGS. Using it instead.")
                                cover_art_found = True
                            else:
                                logger.warning("  - No better cover found on DDGS. Falling back to original iTunes cover.")
                                if not dry_run: shutil.move(itunes_temp_path, destination_path)
                                else: logger.info(f"  - DRY RUN: Would move non-ideal iTunes temp cover to cover.jpg")
                                cover_art_found = True
                    else:
                        logger.info("  - No cover from iTunes. Trying DDGS...")
                        if download_cover_from_internet(book_data, destination_path, dry_run):
                            cover_art_found = True

                    # Cleanup temp file if it still exists
                    if os.path.exists(itunes_temp_path):
                        os.remove(itunes_temp_path)

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

                # --- Write Tags ---
                if not no_tagging:
                    logger.info("Writing metadata tags to audio files...")
                    cover_image_data = None
                    if cover_art_found and not dry_run:
                        try:
                            with open(os.path.join(title_dir, "cover.jpg"), 'rb') as f:
                                cover_image_data = f.read()
                        except Exception as e:
                            logger.warning(f"Could not read cover image for tagging: {e}")

                    # The audio files are already in title_dir
                    sorted_audio_files = sorted([f for f in os.listdir(title_dir) if f.lower().endswith(audio_extensions)])
                    total_tracks = len(sorted_audio_files)
                    for i, filename in enumerate(sorted_audio_files):
                        file_path = os.path.join(title_dir, filename)
                        tag_audio_file(file_path, audiobookshelf_data, cover_image_data, i + 1, total_tracks, dry_run)

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
    parser.add_argument("--no-tagging", action="store_true", help="Disable writing metadata tags to audio files.")
    parser.add_argument("--force-gemini", action="store_true", help="Force the use of Gemini for fetching book data, skipping other sources.")
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
        books_without_cover = organize_audio_files(staging_dir, dest_dir_abs, dry_run=args.dry_run, no_tagging=args.no_tagging, force_gemini=args.force_gemini)
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