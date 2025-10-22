# update_covers.py
import os
import json
import argparse
import sys
import shutil
import requests
import datetime
from PIL import Image
from ddgs import DDGS
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC
from mutagen.mp4 import MP4, MP4Cover
from mutagen.flac import FLAC, Picture
from mutagen import File
from logging_config import get_logger, close_logger
from config_manager import config

# Initialize logger
logger = get_logger(__file__)

# Exit if the configuration failed to load
if not config:
    logger.error("Configuration could not be loaded. Please check for a valid config.ini file.")
    sys.exit(1)

def analyze_cover(image_path, min_resolution):
    """Analyzes a cover image for its dimensions and quality."""
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
    if dry_run:
        logger.info(f"  - DRY RUN: Would search iTunes for cover for title: '{book_data.get('title')}'")
        logger.info(f"  - DRY RUN: Would save cover to: {destination_path}")
        return True
    try:
        title = book_data.get("title", "")
        authors = book_data.get("authors", [])
        author = authors[0] if authors else ""
        if not title or title == "Unknown" or not author or author == "Unknown":
            return False
        search_term = f"{title} {author}"
        logger.info(f"  - Searching for cover on iTunes with term: \"{search_term}\" ")
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
        authors = book_data.get("authors", [])
        author = authors[0] if authors else ""
        if not title or title == "Unknown" or not author or author == "Unknown": return False
        keywords = f'{title} {author} book cover'
        logger.info(f"  - Searching for cover online with keywords: \"{keywords}\" ")
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

def get_new_cover_url(book_data):
    try:
        title = book_data.get("title", "")
        authors = book_data.get("authors", [])
        author = authors[0] if authors else ""
        if not title or title == "Unknown" or not author or author == "Unknown": return "#"
        search_term = f"{title} {author}"
        params = {"term": search_term, "media": "ebook", "entity": "ebook", "limit": 1, "country": "US"}
        response = requests.get("https://itunes.apple.com/search", params=params, timeout=10)
        response.raise_for_status()
        results = response.json()
        if results["resultCount"] > 0:
            artwork_url = results["results"][0].get("artworkUrl100")
            if artwork_url:
                return artwork_url.replace("100x100bb.jpg", "1000x1000bb.jpg")
        keywords = f'{title} {author} book cover'
        with DDGS() as ddgs:
            results = list(ddgs.images(keywords, max_results=1))
            if results:
                return results[0]["image"]
        return "#"
    except Exception as e:
        logger.warning(f"Could not fetch new cover URL for audit: {e}")
        return "#"

def sort_audio_files(files):
    import re
    def natural_keys(text):
        return [int(c) if c.isdigit() else c for c in re.split('(\d+)', text)]
    files.sort(key=natural_keys)
    return files

def tag_audio_file(file_path, cover_image_data, dry_run=False):
    if dry_run:
        logger.info(f"      - DRY RUN: Would embed cover in: {os.path.basename(file_path)}")
        return
    try:
        audio = File(file_path, easy=False)
        if audio is None: raise ValueError("Could not load file.")
        logger.info(f"      - Updating cover art for: {os.path.basename(file_path)}")
        if isinstance(audio, MP3):
            audio.tags.delall('APIC')
            if cover_image_data: audio.tags.add(APIC(encoding=3, mime='image/jpeg', type=3, desc='Cover', data=cover_image_data))
        elif isinstance(audio, MP4):
            if cover_image_data: audio.tags["covr"] = [MP4Cover(cover_image_data, imageformat=MP4Cover.FORMAT_JPEG)]
            elif "covr" in audio.tags: del audio.tags["covr"]
        elif isinstance(audio, FLAC):
            audio.clear_pictures()
            if cover_image_data:
                pic = Picture()
                pic.type = 3
                pic.mime = "image/jpeg"
                pic.desc = "Cover"
                pic.data = cover_image_data
                audio.add_picture(pic)
        audio.save()
        logger.info(f"      - Successfully embedded cover in: {os.path.basename(file_path)}")
    except Exception as e:
        logger.error(f"      - ERROR: Failed to tag {os.path.basename(file_path)}: {e}")

def generate_html_report(report_data, library_path):
    report_path = os.path.join(library_path, "cover_audit.html")
    logger.info(f"Generating HTML report at: {report_path}")
    html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>Cover Audit Report</title><style>body {{ font-family: sans-serif; margin: 2em; }} table {{ border-collapse: collapse; width: 100%; }} th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }} th {{ background-color: #f2f2f2; }} .status-good {{ color: green; }} .status-bad {{ color: red; font-weight: bold; }} .recommend-replace {{ background-color: #fff0f0; }}</style></head><body><h1>Cover Audit Report</h1><p>Generated on: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p><table><tr><th>Book Title</th><th>Existing Cover</th><th>New Cover Preview</th><th>Recommendation</th></tr>"""
    for item in report_data:
        html += f"""<tr class="{'recommend-replace' if 'REPLACE' in item['recommendation'] or 'DOWNLOAD' in item['recommendation'] else ''}"><td>{item['title']}</td><td>{item['existing_status']}</td><td><a href="{item['new_cover_url']}" target="_blank">Preview Link</a></td><td class="{'status-bad' if 'REPLACE' in item['recommendation'] or 'DOWNLOAD' in item['recommendation'] else 'status-good'}">{item['recommendation']}</td></tr>"""
    html += """</table></body></html>"""
    try:
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(html)
        logger.info("Report generated successfully.")
    except Exception as e:
        logger.error(f"Failed to write HTML report: {e}")

def process_library_audit(library_path, min_resolution):
    logger.info("--- Starting Cover Audit Mode ---")
    report_data = []
    for root, _, files in os.walk(library_path):
        if "metadata.json" in files:
            book_path = root
            logger.info(f"\nAuditing book: {os.path.basename(book_path)}")
            json_path = os.path.join(book_path, "metadata.json")
            cover_path = os.path.join(book_path, "cover.jpg")
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
            except Exception as e:
                logger.error(f"  - Could not read metadata.json: {e}")
                continue
            analysis = analyze_cover(cover_path, min_resolution)
            existing_status = "N/A"
            recommendation = ""
            if analysis.get("exists"):
                if analysis.get("error"):
                    existing_status = f"<span class='status-bad'>ERROR reading file</span>"
                    recommendation = "REPLACE (Error)"
                else:
                    quality = "LOW QUALITY" if analysis['is_low_quality'] else "Good Quality"
                    shape = "Square" if analysis['is_square'] else "Not Square"
                    existing_status = f"{analysis['dimensions']}, {shape}, <span class="{'status-bad' if analysis['is_low_quality'] or not analysis['is_square'] else 'status-good'}">{quality}</span>"
                    if not analysis['is_square'] or analysis['is_low_quality']:
                        recommendation = "REPLACE"
                    else:
                        recommendation = "KEEP"
            else:
                existing_status = "No cover.jpg found."
                recommendation = "DOWNLOAD NEW"
            report_data.append({
                "title": metadata.get("title", "Unknown"),
                "existing_status": existing_status,
                "new_cover_url": get_new_cover_url(metadata),
                "recommendation": recommendation
            })
    generate_html_report(report_data, library_path)

def process_library_smart(library_path, force_update, min_resolution):
    logger.info(f"--- Starting Smart Update Mode (Force: {force_update}) ---")
    books_processed = 0
    covers_updated = 0
    for root, dirs, files in os.walk(library_path):
        if "metadata.json" in files:
            books_processed += 1
            book_path = root
            logger.info(f"\nProcessing book: {os.path.basename(book_path)}")
            json_path = os.path.join(book_path, "metadata.json")
            cover_path = os.path.join(book_path, "cover.jpg")
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
            except Exception as e:
                logger.error(f"  - Could not read metadata.json: {e}")
                continue
            
            should_replace = False
            if force_update:
                should_replace = True
            else:
                analysis = analyze_cover(cover_path, min_resolution)
                if not analysis["exists"]:
                    should_replace = True
                elif analysis.get("error") or not analysis["is_square"] or analysis["is_low_quality"]:
                    should_replace = True
                else:
                    logger.info("  - Existing cover is square and good quality. Skipping.")

            if should_replace:
                itunes_temp_path = os.path.join(book_path, "itunes_cover.tmp")
                itunes_success = download_cover_from_itunes(metadata, itunes_temp_path)
                cover_finalized = False
                if itunes_success:
                    if is_square(itunes_temp_path):
                        shutil.move(itunes_temp_path, cover_path)
                        cover_finalized = True
                    else:
                        if download_cover_from_internet(metadata, cover_path):
                            cover_finalized = True
                        else:
                            shutil.move(itunes_temp_path, cover_path)
                            cover_finalized = True
                else:
                    if download_cover_from_internet(metadata, cover_path):
                        cover_finalized = True
                
                if os.path.exists(itunes_temp_path):
                    os.remove(itunes_temp_path)

                if cover_finalized:
                    covers_updated += 1
                    logger.info("  - Embedding new cover into audio files...")
                    try:
                        with open(cover_path, 'rb') as f:
                            cover_image_data = f.read()
                        audio_files = [f for f in os.listdir(book_path) if f.lower().endswith(config.general['audio_extensions'])]
                        for filename in sort_audio_files(audio_files):
                            tag_audio_file(os.path.join(book_path, filename), cover_image_data)
                    except Exception as e:
                        logger.error(f"  - An unexpected error occurred while embedding the cover: {e}")
            dirs[:] = []
    logger.info(f"\n--- Scan Complete ---\nTotal books processed: {books_processed}\nCovers downloaded/updated: {covers_updated}")

def main():
    parser = argparse.ArgumentParser(
        description="Scans an audiobook library and downloads high-quality covers.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("library_directory", help="The root directory of your organized audiobook library.")
    parser.add_argument("--mode", choices=['smart', 'audit'], default='smart', help="Execution mode.\n'smart': (default) Updates covers if they are missing, not square, or low quality.\n'audit': Generates an HTML report of cover quality without changing files.")
    parser.add_argument("--force", action="store_true", help="Force update of all covers, regardless of quality (only in smart mode).")
    args = parser.parse_args()
    library_path_abs = os.path.abspath(args.library_directory)
    min_resolution = config.covers['min_resolution']
    if not os.path.isdir(library_path_abs):
        logger.error(f"The specified directory '{library_path_abs}' does not exist.")
        sys.exit(1)
    if args.mode == 'audit':
        process_library_audit(library_path_abs, min_resolution)
    else:
        process_library_smart(library_path_abs, args.force, min_resolution)

if __name__ == "__main__":
    try:
        main()
    finally:
        close_logger(logger)