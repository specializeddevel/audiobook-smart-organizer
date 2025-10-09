# validate_names.py
import os
import argparse
import re
import sys
from collections import defaultdict

# Words that are common in audiobook folders but don't add value for identification.
# This list includes terms in both English and Spanish.
COMMON_JUNK_WORDS = [
    'audiobook', 'audiolibro', 'unabridged', 'completo', 'full', 'original',
    'dramatizado', 'libro', 'book', 'audible', 'version', 'edicion', 'unknown',
    'official', 'oficial', 'retail'
]

# Supported audio extensions to check for loose files.
AUDIO_EXTENSIONS = ('.mp3', '.m4a', '.wav', '.flac', '.m4b')

# Minimum number of words a name should have if no other separators are found.
MIN_WORD_COUNT = 2

def get_base_name(filename):
    """
    Extracts a base name from a file to group audiobooks, removing chapter/part numbers.
    This logic is bilingual (English/Spanish).
    """
    name_without_extension = os.path.splitext(filename)[0]
    # Patterns to remove parts, chapters, discs, etc., in English and Spanish.
    patterns = [
        r'[\s_-]+(part|parte)e?s?\s*\d+',      # part, parts, parte, partes
        r'[\s_-]+(chapter|capitulo|cap)s?\s*\d+', # chapter, cap, capitulo
        r'[\s_-]+(cd|disc|disco)s?\s*\d+',       # cd, disc, disco
        r'[\s_-]+\d+$',                         # a trailing number
        r'\s*\(\d+\)$'                          # a number in parentheses at the end
    ]
    
    base_name = name_without_extension
    for pattern in patterns:
        base_name = re.sub(pattern, '', base_name, flags=re.IGNORECASE).strip()
        
    # Final cleanup of extra spaces
    base_name = re.sub(r'\s+', ' ', base_name).strip()
    return base_name if base_name else name_without_extension

def clean_name_for_validation(name):
    """
    Cleans a name for analysis by removing junk words and common separators.
    """
    # Create a regex pattern to find any of the junk words as whole words, case-insensitively.
    junk_pattern = r'\b(' + '|'.join(re.escape(word) for word in COMMON_JUNK_WORDS) + r')\b'
    
    # Remove the junk words
    cleaned = re.sub(junk_pattern, '', name, flags=re.IGNORECASE)
        
    # Remove extra whitespace that might have been left
    cleaned = ' '.join(cleaned.split())
    
    return cleaned.strip()

def validate_item_names(source_dir):
    """
    Scans a directory for subdirectories and loose audio files, identifying those
    with potentially invalid names for classification.
    """
    if not os.path.isdir(source_dir):
        print(f"Error: The directory '{source_dir}' does not exist.", file=sys.stderr)
        return

    print(f"Scanning directory: {source_dir}\n")
    
    try:
        items = os.listdir(source_dir)
    except OSError as e:
        print(f"Error: Could not read directory '{source_dir}': {e}", file=sys.stderr)
        return

    # Use a dictionary to store unique names to check and their original sources
    names_to_check = defaultdict(list)
    for item in items:
        full_path = os.path.join(source_dir, item)
        if os.path.isdir(full_path):
            # For directories, the name to check is the directory name itself
            names_to_check[item].append(item + "/ (directory)")
        elif item.lower().endswith(AUDIO_EXTENSIONS):
            # For audio files, we check their base name
            base_name = get_base_name(item)
            names_to_check[base_name].append(base_name + " (file)")

    if not names_to_check:
        print("No subdirectories or audio files found to analyze.")
        return

    problematic_items = []

    print(f"Found {len(names_to_check)} unique items/groups to analyze. Analyzing names...")
    for name, sources in names_to_check.items():
        reason = ""
        # Use the original name for checking separators, as cleaning might remove them
        original_name_lower = name.lower()

        # 1. Check for 'unknown'
        if 'unknown' in original_name_lower:
            reason = "Name contains the word 'unknown'."
        
        # 2. If no issue yet, check for common valid separators (English and Spanish). If found, assume it's OK.
        elif ' by ' in original_name_lower or ' por ' in original_name_lower or ' - ' in name:
            pass # This name looks promising, so we don't flag it.

        # 3. If no separators, fall back to heuristic checks on the cleaned name.
        else:
            cleaned = clean_name_for_validation(name)
            words = cleaned.split()
            if not cleaned:
                reason = "Name is empty after removing common junk words."
            elif len(words) < MIN_WORD_COUNT:
                reason = f"Contains too few words ({len(words)}) after cleaning and lacks common separators (like '-', 'by', or 'por')."
            elif all(word.isdigit() for word in words):
                reason = "Name consists only of numbers."
        
        if reason:
            problematic_items.append({
                "name": name,
                "reason": reason,
                "sources": sources
            })

    print("\n--- Validation Complete ---")
    if problematic_items:
        print(f"Found {len(problematic_items)} items/groups with potentially problematic names:")
        problematic_items.sort(key=lambda x: x['name'])
        for item in problematic_items:
            print(f"\n  - Name/Group: '{item['name']}'")
            print(f"    Reason: {item['reason']}")
            # Show the first few source files/folders for context
            source_preview = ", ".join(item['sources'][:3])
            if len(item['sources']) > 3:
                source_preview += f", and {len(item['sources']) - 3} more"
            print(f"    Sources: [ {source_preview} ]")
    else:
        print("All item and folder names seem to be suitable for processing.")

def main():
    parser = argparse.ArgumentParser(
        description="Scans a directory to find subfolders and audio files with names that might be unsuitable for automatic audiobook classification.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "source_directory",
        help="The directory containing the items to analyze (in English or Spanish)."
    )
    args = parser.parse_args()

    source_dir_abs = os.path.abspath(args.source_directory)
    
    validate_item_names(source_dir_abs)

if __name__ == "__main__":
    main()
