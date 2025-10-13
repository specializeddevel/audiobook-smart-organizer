import os
import json
import csv
import argparse
import sys

def generate_inventory(library_path):
    """
    Scans a directory for metadata.json files (in audiobookshelf format)
    and generates a master inventory.csv file.
    """
    inventory_path = os.path.join(library_path, "inventory.csv")
    print(f"The inventory will be generated at: {inventory_path}")

    # New header reflecting the audiobookshelf format
    header = [
        "Title", "Authors", "Series", "Genres", "PublishedYear", "Description", "Path"
    ]
    
    all_books_data = []

    print("Starting scan for metadata files...")
    for root, dirs, files in os.walk(library_path):
        if "metadata.json" in files:
            json_path = os.path.join(root, "metadata.json")
            
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                relative_path = os.path.relpath(root, library_path).replace('\\', '/')
                
                # Process list-based fields for clean CSV output
                authors_str = ", ".join(data.get("authors", []))
                genres_str = ", ".join(data.get("genres", []))
                series_list = data.get("series", [])
                series_str = ""
                if series_list and isinstance(series_list[0], dict):
                    series_str = series_list[0].get("name", "")

                row_data = {
                    "Title": data.get("title", "Unknown"),
                    "Authors": authors_str,
                    "Series": series_str,
                    "Genres": genres_str,
                    "PublishedYear": data.get("publishedYear", ""),
                    "Description": data.get("description", ""),
                    "Path": relative_path
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
