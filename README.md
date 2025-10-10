# EbookSort: AI-Powered Audiobook Management Suite

EbookSort is a suite of Python scripts designed to automatically organize, tag, and manage your audiobook library. It transforms a messy folder of audio files into a clean, organized, and perfectly tagged collection.

## Key Features

- **Automatic Organization**: Intelligently groups loose audio files into book folders, creating a clean `Author/Title` structure.
- **AI-Powered Metadata**: Uses the Google Gemini API to fetch rich metadata (title, author, series, synopsis, genre, etc.) for your audiobooks.
- **Multi-Source Cover Art**: Automatically finds the best available cover art through a 3-step process:
    1.  Detects existing local image files.
    2.  Extracts cover art embedded in the audio files' metadata.
    3.  Searches the internet for a high-quality cover if no local art is found.
- **Advanced Tagging**: Embeds all metadata and cover art directly into each audio file (`.mp3`, `.m4a`, `.m4b`, `.flac`).
- **Robust and Safe**: The process uses a staging area to prevent file loss if the script is interrupted. It's also fault-tolerant, skipping individual books that cause errors without stopping the entire process.
- **Library Maintenance**: Includes tools to validate filenames, fix missing covers, and regenerate the library inventory.
- **Centralized Inventory**: Generates and maintains a master `inventory.csv` file, which you can open in any spreadsheet program to view your entire collection.

---

## Requirements

- Python 3.7+
- A Google Gemini API Key.
- The Python dependencies listed in `requirements.txt`.

---

## Installation & Setup

### 1. Install Dependencies

Open a terminal in the project folder and run the following command to install the required libraries:

```bash
pip install -r requirements.txt
```
*(This will install `google-generativeai`, `mutagen`, `requests`, `ddgs`, and other dependencies).*

### 2. Set Up Your API Key

The main script (`ebooksort.py`) requires a Google Gemini API key. You must set it up as an environment variable named `GOOGLE_API_KEY`.

**On Windows:**
```cmd
setx GOOGLE_API_KEY "YOUR_API_KEY_HERE"
```
*(You may need to restart your terminal or system for the change to take effect).*

**On Linux/macOS:**
```bash
export GOOGLE_API_KEY="YOUR_API_KEY_HERE"
```
*(To make this permanent, add this line to your `~/.bashrc` or `~/.zshrc` file).*

---

## Recommended Workflow

1.  **Validate Names (Recommended)**: Use `validate_names.py` on your folder of unorganized audiobooks to find files or folders with problematic names that might not be classified correctly. Rename the flagged items for best results.
2.  **Organize the Library**: Run `ebooksort.py` to group, classify, and organize the audiobooks into a clean `Author/Title` folder structure.
3.  **Write Metadata**: Once organized, use `write_tags.py` on the clean library to embed all the information (title, author, cover, etc.) into the audio files.

---

## Scripts and Usage

### 1. `validate_names.py` - The Validator

This script is a diagnostic tool. It analyzes the names of folders and audio files in a directory to identify those that likely do not contain enough information (title and author) to be classified correctly.

**Why use it?** It helps you fix names *before* starting the main process, saving time and preventing books from ending up in the "unclassified" folder.

**Usage:**
```bash
python validate_names.py "C:\Path\To\Your\Audiobooks"
```

### 2. `ebooksort.py` - The Organizer

This is the main script. It takes a source directory, groups files, uses the Gemini AI to fetch metadata, finds a cover, and sorts everything into a clean library.

**New in this version:**
- At the end of the process, it will **display a list of books that were processed but for which no cover art could be found**.

**Usage:**
```bash
# Organize in the same directory
python ebooksort.py "C:\Path\To\Your\Audiobooks"

# Organize from a source to a different destination
python ebooksort.py "C:\Source" -d "D:\Organized Library"
```

### 3. `write_tags.py` - The Tagger

This script reads the metadata (`metadata.json`) and cover art (`cover.jpg`) for each book in your organized library and writes that information into the audio files' tags.

**Execution Modes (`--mode`):**
- `smart` (default): Only processes new books that haven't been tagged before.
- `all`: Forces a re-tag of all metadata and covers for all books.
- `tags-only`: Re-tags only the text metadata (title, author, etc.).
- `cover-only`: Updates only the cover art in the files.
- `fix-covers`: Scans the library, finds books missing a cover, downloads it, and embeds it.

**Usage:**
```bash
# Tag only new books (recommended)
python write_tags.py "D:\Organized Library" --mode smart

# Find and fix missing covers across the entire library
python write_tags.py "D:\Organized Library" --mode fix-covers
```

### 4. `generate_inventory.py` - The Inventory Generator

This script regenerates the `inventory.csv` file from the metadata in your library. It's useful if you have manually moved or deleted books and want the inventory to reflect the current state.

**Usage:**
```bash
python generate_inventory.py "D:\Organized Library"
```

### 5. `extract_covers.py` - The Cover Extractor

A simple utility that scans a directory, finds cover art embedded in audio files, and saves it as a `.jpg` file next to the original file.

**Usage:**
```bash
python extract_covers.py "C:\Path\To\Your\Audiobooks"
```

---

## Technologies Used

- **Python 3**: The core language for all scripts.
- **Google Gemini API**: Used for its powerful natural language processing to extract structured book metadata from filenames.
- **`mutagen`**: A robust Python library for reading and writing audio metadata tags (ID3, MP4, FLAC, etc.).
- **`ddgs`**: A lightweight library to search for cover art on DuckDuckGo without requiring an additional API key.
- **`requests`**: The standard library for making HTTP requests to download cover images.
- **`google-generativeai`**: The official Google client library for interacting with the Gemini API.

---

## License

This project is licensed under the **MIT License**.

This means you are free to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the software. The only requirement is to include the original copyright and permission notice in any substantial portions of the software. It is provided "as is", without warranty of any kind.
