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
- **FFmpeg**: Required by the `create_m4b.py` script. You must install it separately and ensure it is available in your system's PATH.

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

Here is a detailed breakdown of each script and its available command-line arguments.

### 1. `validate_names.py` - The Validator

This script is a diagnostic tool. It analyzes the names of folders and audio files in a directory to identify those that likely do not contain enough information (title and author) to be classified correctly.

**Why use it?** It helps you fix names *before* starting the main process, saving time and preventing books from ending up in the "unclassified" folder.

**Usage:**
```bash
python validate_names.py "C:\Path\To\Your\Audiobooks"
```

**Arguments:**

*   **`source_directory`** (Positional, Required)
    *   **Description**: The path to the directory you want to analyze for problematic names.
    *   **Example**: `C:\MyAudiobooks\ToCheck`

*   **`--authors-file`** (Optional)
    *   **Description**: The path to the text file containing the list of known authors. Using this list helps the script more accurately identify if a filename contains an author.
    *   **Default**: `known_authors.txt` in the current directory.
    *   **Example**: `--authors-file "C:\Config\authors.txt"`

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

**Arguments:**

*   **`source_directory`** (Positional, Required)
    *   **Description**: The path to the directory containing the unorganized audiobooks (loose files or folders).
    *   **Example**: `C:\MyAudiobooks\New`

*   **`-d` / `--destination_directory`** (Optional)
    *   **Description**: Specifies the path to the final organized library. If not provided, the script will perform the organization "in-place," meaning the `source_directory` will become the organized library.
    *   **Default**: The same as `source_directory`.
    *   **Example**: `-d "D:\AudiobookLibrary"`

*   **`--dry-run`** (Optional, Flag)
    *   **Description**: Performs a simulation of the process. It prints all the actions that would be taken (moving files, calling APIs, writing metadata) but does not execute any real action. Ideal for safely previewing changes.

### 3. `write_tags.py` - The Tagger

This script reads the metadata (`metadata.json`) and cover art (`cover.jpg`) for each book in your organized library and writes that information into the audio files' tags.

**Usage:**
```bash
# Tag only new books (recommended)
python write_tags.py "D:\Organized Library" --mode smart

# Find and fix missing covers across the entire library
python write_tags.py "D:\Organized Library" --mode fix-covers
```

**Arguments:**

*   **`target_path`** (Positional, Required)
    *   **Description**: Can be the path to the already organized audiobook library or the path to a single audio file you want to tag.
    *   **Example (Directory)**: `D:\AudiobookLibrary`
    *   **Example (File)**: `D:\AudiobookLibrary\Author\Title\Chapter1.mp3`

*   **`--mode`** (Optional)
    *   **Description**: Controls the tagging behavior.
    *   **Default**: `smart`.
    *   **Options**:
        *   `smart`: (Recommended) Only processes books that have not been tagged before. It looks for a marker file (`.tags_written`) to skip already processed folders.
        *   `all`: Forcibly re-tags all books in the library, overwriting existing metadata and covers.
        *   `tags-only`: Re-writes only the text metadata (title, author, etc.), but does not touch the cover art.
        *   `cover-only`: Updates only the cover art in the audio files, leaving other metadata intact.
        *   `fix-covers`: A special maintenance mode. It scans the library for books that do not have a `cover.jpg` file, tries to download it, and then embeds it into the corresponding audio files.

*   **`--dry-run`** (Optional, Flag)
    *   **Description**: Performs a simulation of the tagging process. It prints the files that would be modified but does not save any changes to the audio files.

### 4. `create_m4b.py` - The M4B Creator

Combines a folder of audio files (chapters) into a single `.m4b` audiobook file, complete with chapters, metadata, and cover art. **Requires FFmpeg to be installed** and accessible in the system's PATH.

**Usage:**
```bash
# Create an M4B file from a book folder
python create_m4b.py "D:\Organized Library\Author Name\Book Title"
```

**Arguments:**

*   **`book_folder_path`** (Positional, Required)
    *   **Description**: The path to the book's folder, which contains the audio files and `metadata.json`.
    *   **Example**: `D:\AudiobookLibrary\Morgan Rice\Arena Dos Supervivencia`

*   **`--dry-run`** (Optional, Flag)
    *   **Description**: Displays the FFmpeg command that would be executed to create the `.m4b` file, but does not run it. Useful for debugging.

### 5. `generate_inventory.py` - The Inventory Generator

This script regenerates the `inventory.csv` file from the metadata in your library. It's useful if you have manually moved or deleted books and want the inventory to reflect the current state.

**Usage:**
```bash
python generate_inventory.py "D:\Organized Library"
```

**Arguments:**

*   **`library_directory`** (Positional, Required)
    *   **Description**: The path to the root directory of your organized audiobook library.
    *   **Example**: `D:\AudiobookLibrary`

### 6. `populate_authors.py` - The Author Populator

Scans the library to find authors in the metadata and add them to your `known_authors.txt` list. This script was not previously documented in this section.

**Usage:**
```bash
python populate_authors.py "D:\Organized Library"
```

**Arguments:**

*   **`library_directory`** (Positional, Required)
    *   **Description**: The path to the root directory of your organized audiobook library.
    *   **Example**: `D:\AudiobookLibrary`

*   **`-f` / `--file`** (Optional)
    *   **Description**: Specifies the path of the text file where the authors will be saved.
    *   **Default**: `known_authors.txt` in the current directory.
    *   **Example**: `-f "master_authors.txt"`

### 7. `extract_covers.py` - The Cover Extractor

A simple utility that scans a directory, finds cover art embedded in audio files, and saves it as a `.jpg` file next to the original file.

**Usage:**
```bash
python extract_covers.py "C:\Path\To\Your\Audiobooks"
```

**Arguments:**

*   **`source_directory`** (Positional, Required)
    *   **Description**: The path to the directory (and subdirectories) containing the audio files from which you want to extract the cover art.
    *   **Example**: `C:\Audio\Temp`

### 8. `find_duplicates.py` - The Duplicate Finder

A powerful utility to scan your music library and find potential duplicate audio files. It offers multiple analysis modes, from a simple file count to a deep metadata scan.

**Usage:**
```bash
# Run a deep scan based on Artist/Title tags
python find_duplicates.py "C:\Path\To\Your\Music" --mode metadata

# Run a fast scan based on similar filenames
python find_duplicates.py "C:\Path\To\Your\Music" --mode filesystem

# Quickly list folders with more than one audio file
python find_duplicates.py "C:\Path\To\Your\Music" --mode count
```

**Arguments:**

*   **`directory`** (Positional, Required)
    *   **Description**: The path to the root directory of your music collection to scan.
    *   **Example**: `C:\MyMusic`

*   **`--mode`** (Optional)
    *   **Description**: Specifies the analysis mode.
    *   **Default**: `metadata`.
    *   **Options**:
        *   `metadata`: (Slow but accurate) Scans Artist and Title tags to find duplicates. Recommended for a thorough check.
        *   `filesystem`: (Fast) Scans for files with similar names, ignoring track numbers and other variations.
        *   `count`: (Very Fast) Simply lists any folder containing more than one audio file.

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
