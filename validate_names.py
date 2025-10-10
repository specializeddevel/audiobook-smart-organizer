# validate_names.py
import os
import argparse
import re
import sys
from collections import defaultdict

# Words that are common in audiobook folders but don't add value for identification.
COMMON_JUNK_WORDS = [
    'audiobook', 'audiolibro', 'unabridged', 'completo', 'full', 'original',
    'dramatizado', 'libro', 'book', 'audible', 'version', 'edicion', 'unknown',
    'official', 'oficial', 'retail'
]

# Supported audio extensions to check for loose files.
AUDIO_EXTENSIONS = ('.mp3', '.m4a', '.wav', '.flac', '.m4b')

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
        print(f"Warning: Could not read authors file at '{filepath}'. Proceeding without it. Error: {e}")
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
    Cleans a name for analysis by removing junk words.
    """
    junk_pattern = r'\b(' + '|'.join(re.escape(word) for word in COMMON_JUNK_WORDS) + r')\b'
    cleaned = re.sub(junk_pattern, '', name, flags=re.IGNORECASE)
    return ' '.join(cleaned.split())

def validate_item_names(source_dir, authors_filepath):
    """
    Scans a directory and identifies items with potentially invalid names.
    """
    if not os.path.isdir(source_dir):
        print(f"Error: The directory '{source_dir}' does not exist.", file=sys.stderr)
        return

    print(f"Scanning directory: {source_dir}")
    known_authors = load_known_authors(authors_filepath)
    if known_authors:
        print(f"Successfully loaded {len(known_authors)} known authors.")

    names_to_check = defaultdict(list)
    for item in os.listdir(source_dir):
        full_path = os.path.join(source_dir, item)
        if os.path.isdir(full_path):
            names_to_check[item].append(item + "/ (directory)")
        elif item.lower().endswith(AUDIO_EXTENSIONS):
            base_name = get_base_name(item)
            names_to_check[base_name].append(item + " (file)")

    if not names_to_check:
        print("No subdirectories or audio files found to analyze.")
        return

    problematic_items = []
    print(f"\nFound {len(names_to_check)} unique items/groups to analyze. Analyzing names...")

    for name, sources in names_to_check.items():
        level, reason, found_author = None, None, None
        original_name_lower = name.lower()

        if 'unknown' in original_name_lower:
            level, reason = "ERROR", "Name contains the word 'unknown'."
        elif ' by ' in original_name_lower or ' por ' in original_name_lower or ' - ' in name:
            parts = re.split(r' by | por | - ', name, maxsplit=1)
            if not parts[0].strip() or not parts[1].strip():
                level, reason = "ERROR", "Name has a separator but one side is empty."
        else:
            # If no separator, check for a known author in the name
            # Sort by length to match longer names first (e.g., "Stephen King" before "King")
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
                elif word_count <= 2:
                    level, reason = "ERROR", f"Name is too short ({word_count} words) and lacks a separator or known author."
                elif word_count <= 4:
                    level, reason = "WARNING", f"Name is ambiguous ({word_count} words) and lacks a separator or known author. Please review."

        if level and reason:
            problematic_items.append({"name": name, "level": level, "reason": reason, "sources": sources})

    print("\n--- Validation Complete ---")
    if problematic_items:
        problematic_items.sort(key=lambda x: (x['level'], x['name']))
        error_count = sum(1 for item in problematic_items if item['level'] == 'ERROR')
        warning_count = sum(1 for item in problematic_items if item['level'] == 'WARNING')
        print(f"Found {error_count} ERROR(s) and {warning_count} WARNING(s).")

        for item in problematic_items:
            print(f"\n  - Level: {item['level']}")
            print(f"    Name/Group: '{item['name']}'")
            print(f"    Reason: {item['reason']}")
            source_preview = ", ".join(item['sources'][:3])
            if len(item['sources']) > 3:
                source_preview += f", and {len(item['sources']) - 3} more"
            print(f"    Sources: [ {source_preview} ]")
        
        print("\n--- Recommendations ---")
        print(" - For ERRORS: These names are very likely to fail classification. Rename them to a 'Title - Author' format.")
        print(" - For WARNINGS: These names are ambiguous. Manually check if they contain both a title and an author.")
    else:
        print("All item and folder names seem to be suitable for processing.")

def main():
    parser = argparse.ArgumentParser(
        description="Scans a directory to find items with names that might be unsuitable for automatic audiobook classification, using a list of known authors to improve accuracy.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("source_directory", help="The directory containing the items to analyze.")
    parser.add_argument("--authors-file", default="known_authors.txt", help="Path to the file containing known author names (one per line). Defaults to 'known_authors.txt'.")
    args = parser.parse_args()

    source_dir_abs = os.path.abspath(args.source_directory)
    authors_filepath_abs = os.path.abspath(args.authors_file)

    validate_item_names(source_dir_abs, authors_filepath_abs)

if __name__ == "__main__":
    main()
