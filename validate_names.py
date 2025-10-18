# validate_names.py
import os
import argparse
import re
import sys
from collections import defaultdict
from logging_config import get_logger, close_logger
from config_manager import config

# Initialize logger
logger = get_logger(__file__)

# Exit if the configuration failed to load
if not config:
    logger.error("Configuration could not be loaded. Please check for a valid config.ini file.")
    sys.exit(1)

def load_known_authors(filepath):
    """
    Loads the known authors from the specified file into a set for fast, case-insensitive lookup.
    """
    if not os.path.exists(filepath):
        return set()
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            # Store authors in lowercase for case-insensitive matching
            return {line.strip().lower() for line in f if line.strip()}
    except IOError as e:
        logger.warning(f"Could not read authors file at '{filepath}'. Proceeding without it. Error: {e}")
        return set()

def get_base_name(filename):
    """
    Extracts a base name from a file to group audiobooks, removing chapter/part numbers.
    """
    name_without_extension = os.path.splitext(filename)[0]
    patterns = [
        r'[\s_-]+(part|parte)e?s?\s*\d+',
        r'[\s_-]+(chapter|capitulo|cap)s?\s*\d+',
        r'[\s_-]+(cd|disc|disco)s?\s*\d+',
        r'[\s_-]+\d+$',
        r'\s*\(\d+\)$'
    ]
    base_name = name_without_extension
    for pattern in patterns:
        base_name = re.sub(pattern, '', base_name, flags=re.IGNORECASE).strip()
    base_name = re.sub(r'\s+', ' ', base_name).strip()
    return base_name if base_name else name_without_extension

def clean_name_for_validation(name):
    """
    Cleans a name for analysis by removing junk words from the config.
    """
    junk_words = config.validation['junk_words']
    junk_pattern = r'\b(' + '|'.join(re.escape(word) for word in junk_words) + r')\b'
    cleaned = re.sub(junk_pattern, '', name, flags=re.IGNORECASE)
    return ' '.join(cleaned.split())

def has_separator(name):
    """Checks if the name contains any of the configured separators."""
    return any(sep in name for sep in config.validation['name_separators'])

def validate_item_names(source_dir, authors_filepath):
    """
    Scans a directory and identifies items with potentially invalid names.
    """
    if not os.path.isdir(source_dir):
        logger.error(f"The directory '{source_dir}' does not exist.")
        return

    logger.info(f"Scanning directory: {source_dir}")
    known_authors = load_known_authors(authors_filepath)
    if known_authors:
        logger.info(f"Successfully loaded {len(known_authors)} known authors.")

    audio_extensions = config.general['audio_extensions']
    names_to_check = defaultdict(list)
    for item in os.listdir(source_dir):
        full_path = os.path.join(source_dir, item)
        if os.path.isdir(full_path):
            names_to_check[item].append(item + "/ (directory)")
        elif item.lower().endswith(audio_extensions):
            base_name = get_base_name(item)
            names_to_check[base_name].append(item + " (file)")

    if not names_to_check:
        logger.info("No subdirectories or audio files found to analyze.")
        return

    problematic_items = []
    logger.info(f"\nFound {len(names_to_check)} unique items/groups to analyze. Analyzing names...")

    # Get thresholds from config
    short_word_count = config.validation['short_name_word_count']
    ambiguous_word_count = config.validation['ambiguous_name_word_count']

    for name, sources in names_to_check.items():
        level, reason, found_author = None, None, None
        original_name_lower = name.lower()

        if 'unknown' in original_name_lower:
            level, reason = "ERROR", "Name contains the word 'unknown'."
        elif has_separator(name):
            # Use a regex to split by any of the separators
            separator_pattern = '|'.join(re.escape(sep) for sep in config.validation['name_separators'])
            parts = re.split(separator_pattern, name, maxsplit=1)
            if not parts[0].strip() or not parts[1].strip():
                level, reason = "ERROR", "Name has a separator but one side is empty."
        else:
            # If no separator, check for a known author in the name
            for author in sorted(known_authors, key=len, reverse=True):
                if author in original_name_lower:
                    found_author = author
                    break
            
            if not found_author:
                # Only if no separator AND no known author, fall back to word count
                cleaned = clean_name_for_validation(name)
                words = cleaned.split()
                word_count = len(words)

                if not cleaned or all(word.isdigit() for word in words):
                    level, reason = "ERROR", "Name is empty, junk, or consists only of numbers."
                elif word_count <= short_word_count:
                    level, reason = "ERROR", f"Name is too short ({word_count} words) and lacks a separator or known author."
                elif word_count <= ambiguous_word_count:
                    level, reason = "WARNING", f"Name is ambiguous ({word_count} words) and lacks a separator or known author. Please review."

        if level and reason:
            problematic_items.append({"name": name, "level": level, "reason": reason, "sources": sources})

    logger.info("\n--- Validation Complete ---")
    if problematic_items:
        problematic_items.sort(key=lambda x: (x['level'], x['name']))
        error_count = sum(1 for item in problematic_items if item['level'] == 'ERROR')
        warning_count = sum(1 for item in problematic_items if item['level'] == 'WARNING')
        logger.info(f"Found {error_count} ERROR(s) and {warning_count} WARNING(s).")

        for item in problematic_items:
            logger.info(f"\n  - Level: {item['level']}")
            logger.info(f"    Name/Group: '{item['name']}'")
            logger.info(f"    Reason: {item['reason']}")
            source_preview = ", ".join(item['sources'][:3])
            if len(item['sources']) > 3:
                source_preview += f", and {len(item['sources']) - 3} more"
            logger.info(f"    Sources: [ {source_preview} ]")
        
        logger.info("\n--- Recommendations ---")
        logger.info(" - For ERRORS: These names are very likely to fail classification. Rename them to a 'Title - Author' format.")
        logger.info(" - For WARNINGS: These names are ambiguous. Manually check if they contain both a title and an author.")
    else:
        logger.info("All item and folder names seem to be suitable for processing.")

def main():
    try:
        parser = argparse.ArgumentParser(
            description="Scans a directory to find items with names that might be unsuitable for automatic audiobook classification, using a list of known authors to improve accuracy.",
            formatter_class=argparse.RawTextHelpFormatter
        )
        parser.add_argument("source_directory", help="The directory containing the items to analyze.")
        parser.add_argument("--authors-file", default=None, help=f"Path to the authors file. Defaults to '{config.general['authors_filename']}' from config.")
        args = parser.parse_args()

        source_dir_abs = os.path.abspath(args.source_directory)
        
        # Use the argument if provided, otherwise fall back to the config default
        authors_filepath_abs = os.path.abspath(args.authors_file) if args.authors_file else os.path.abspath(config.general['authors_filename'])

        validate_item_names(source_dir_abs, authors_filepath_abs)
    finally:
        close_logger(logger)

if __name__ == "__main__":
    main()
