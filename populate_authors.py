# populate_authors.py
import os
import json
import argparse
import sys
from logging_config import get_logger, close_logger
from config_manager import config

# Initialize logger
logger = get_logger(__file__)

# Exit if the configuration failed to load
if not config:
    logger.error("Configuration could not be loaded. Please check for a valid config.ini file.")
    sys.exit(1)

def add_author_to_known_list(author_name, filepath, existing_authors_set):
    """
    Adds a new author to the known authors file if not already present.
    The check is case-insensitive, and authors are stored in Title Case.
    Returns True if a new author was added, False otherwise.
    """
    if not author_name or author_name == "Unknown":
        return False

    author_to_add = author_name.strip().title()
    
    # If author is not already in the set, append to the file and update the set
    if author_to_add.lower() not in existing_authors_set:
        try:
            with open(filepath, 'a', encoding='utf-8') as f:
                f.write(author_to_add + '\n')
            existing_authors_set.add(author_to_add.lower())
            return True
        except IOError as e:
            logger.warning(f"Could not write to authors file '{filepath}': {e}")
            return False
    return False

def scan_library_for_authors(library_path, authors_filepath):
    """
    Scans a library for metadata.json files and populates the known authors file.
    """
    logger.info(f"Scanning library at: {library_path}")
    logger.info(f"Authors will be saved to: {authors_filepath}\n")

    # Load existing authors into a set for efficient, case-insensitive lookup
    try:
        if os.path.exists(authors_filepath):
            with open(authors_filepath, 'r', encoding='utf-8') as f:
                existing_authors = {line.strip().lower() for line in f}
        else:
            existing_authors = set()
        logger.info(f"Found {len(existing_authors)} existing authors in the list.")
    except IOError as e:
        logger.error(f"Could not read authors file '{authors_filepath}': {e}")
        return

    new_authors_count = 0
    processed_books_count = 0

    # Walk through the directory structure
    for root, _, files in os.walk(library_path):
        if "metadata.json" in files:
            json_path = os.path.join(root, "metadata.json")
            processed_books_count += 1
            
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Handle both old and new metadata formats
                authors = data.get("authors", [])
                if not authors:
                    author = data.get("author")
                    if author: authors = [author]

                for author_name in authors:
                    if add_author_to_known_list(author_name, authors_filepath, existing_authors):
                        new_authors_count += 1
                        logger.info(f"  - Found new author: '{author_name.strip().title()}' in '{os.path.basename(root)}'")

            except json.JSONDecodeError:
                logger.warning(f"Could not decode JSON from '{json_path}'. Skipping.")
            except Exception as e:
                logger.warning(f"An unexpected error occurred while processing '{json_path}': {e}")

    logger.info("\n--- Scan Complete ---")
    logger.info(f"Processed {processed_books_count} books with metadata.")
    logger.info(f"Added {new_authors_count} new authors to '{os.path.basename(authors_filepath)}'.")
    logger.info(f"Total authors in the list: {len(existing_authors)}.")

def main():
    try:
        parser = argparse.ArgumentParser(
            description="Scans an organized audiobook library to populate the known_authors.txt file.",
            formatter_class=argparse.RawTextHelpFormatter
        )
        parser.add_argument(
            "library_directory", 
            help="The root directory of your organized audiobook library."
        )
        parser.add_argument(
            "-f", "--file",
            default=None,
            help=f"The path to the authors file to populate. Defaults to '{config.general['authors_filename']}' from config."
        )
        args = parser.parse_args()

        library_path_abs = os.path.abspath(args.library_directory)
        
        # Use the argument if provided, otherwise fall back to the config default
        authors_filepath_abs = os.path.abspath(args.file) if args.file else os.path.abspath(config.general['authors_filename'])

        if not os.path.isdir(library_path_abs):
            logger.error(f"The specified library directory '{library_path_abs}' does not exist.")
            sys.exit(1)
            
        scan_library_for_authors(library_path_abs, authors_filepath_abs)
    finally:
        close_logger(logger)

if __name__ == "__main__":
    main()
