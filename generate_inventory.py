import os
import json
import csv
import argparse
import sys

def generate_inventory(library_path):
    """
    Scans a directory for metadata.json files and generates a master inventory.csv file.
    """
    inventory_path = os.path.join(library_path, "inventory.csv")
    print(f"The inventory will be generated at: {inventory_path}")

    header = [
        "Title", "Author", "Genre", "Series", "Year", "Synopsis", "Path",
        "ProcessingDate", "FileCount", "TotalSizeMB", "CoverArtFound"
    ]
    
    # A list to hold all the book data dictionaries
    all_books_data = []

    print("Starting scan for metadata files...")
    # Walk through the directory structure
    for root, dirs, files in os.walk(library_path):
        # We are looking for metadata.json files
        if "metadata.json" in files:
            json_path = os.path.join(root, "metadata.json")
            
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # The relative path should be from the library path
                relative_path = os.path.relpath(root, library_path)
                
                # Prepare a dictionary for the row
                row_data = {
                    "Title": data.get("title", "Unknown"),
                    "Author": data.get("author", "Unknown"),
                    "Genre": data.get("genre", "Unknown"),
                    "Series": data.get("series", "Unknown"),
                    "Year": data.get("year", "Unknown"),
                    "Synopsis": data.get("synopsis", "Unknown"),
                    "Path": relative_path.replace('\\', '/'), # Use forward slashes for consistency
                    "ProcessingDate": data.get("processing_date", ""),
                    "FileCount": data.get("file_count", 0),
                    "TotalSizeMB": data.get("total_size_mb", 0.0),
                    "CoverArtFound": data.get("cover_art_found", False)
                }
                all_books_data.append(row_data)
                print(f"Found and processed: {relative_path}")

            except json.JSONDecodeError:
                print(f"Warning: Could not decode JSON from '{json_path}'. Skipping.")
            except Exception as e:
                print(f"Warning: An unexpected error occurred while processing '{json_path}': {e}")

    if not all_books_data:
        print("No metadata.json files were found. The inventory file will not be created.")
        return

    # Write all collected data to the CSV file at once
    try:
        with open(inventory_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=header, delimiter='|')
            writer.writeheader()
            writer.writerows(all_books_data)
        print(f"\nSuccessfully generated inventory with {len(all_books_data)} books.")
    except IOError as e:
        print(f"Error: Could not write to CSV file at '{inventory_path}': {e}")

def main():
    parser = argparse.ArgumentParser(
        description="Generates a CSV inventory from metadata.json files in an organized audiobook library.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "library_directory", 
        help="The root directory of your organized audiobook library (e.g., 'C:\\Users\\YourUser\\Ebooks')."
    )
    args = parser.parse_args()

    library_path_abs = os.path.abspath(args.library_directory)

    if not os.path.isdir(library_path_abs):
        print(f"Error: The specified directory '{library_path_abs}' does not exist or is not a directory.", file=sys.stderr)
        sys.exit(1)
        
    generate_inventory(library_path_abs)

if __name__ == "__main__":
    main()
