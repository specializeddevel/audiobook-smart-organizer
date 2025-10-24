# EbookSort: AI-Powered Audiobook Management Suite

EbookSort is a suite of Python scripts designed to automatically organize, tag, and manage your audiobook library. It transforms a messy folder of audio files into a clean, organized, and perfectly tagged collection.

## Key Features

- **Automatic Organization**: Intelligently groups loose audio files into book folders, creating a clean `Author/Title` structure.
- **Multi-Source Metadata**: Fetches rich metadata (title, author, series, synopsis, genre, etc.) for your audiobooks by querying Google Books and using the Google Gemini API for more complex cases.
- **Intelligent Cover Art Search**: Automatically finds the best available cover art. The script prioritizes high-resolution, square images by searching multiple sources:
    1.  Detects existing local image files.
    2.  Extracts cover art embedded in the audio files' metadata.
    3.  Searches the **iTunes Store** for a high-quality cover.
    4.  If the iTunes cover isn't ideal (e.g., not square), it searches for a better alternative online.
    5.  All downloaded covers are validated for quality based on configurable resolution settings.
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
*(This will install `google-generativeai`, `mutagen`, `requests`, `ddgs`, `Pillow`, and other dependencies).*

### 2. Configure the API Key

The scripts require a Google Gemini API key. The recommended way to configure it is by using the configuration file.

1.  **Create your configuration file**: In the project folder, make a copy of `config.ini.example` and rename it to `config.ini`.
2.  **Edit `config.ini`**: Open the `config.ini` file in a text editor.
3.  **Add your key**: Find the `[Gemini]` section and replace `"YOUR_API_KEY_HERE"` with your actual Google Gemini API key.

```ini
[Gemini]
api_key = YOUR_ACTUAL_API_KEY_GOES_HERE
...
```

**Important**: The `config.ini` file is included in `.gitignore` to prevent you from accidentally committing your secret key to version control.

### 3. Review and Customize Configuration (Optional)

This project uses a central configuration file, `config.ini`, to control the behavior of the scripts. Before running, you can open this file and customize settings like the AI model, supported file types, and validation rules.

See the **Configuration** section below for more details.

---

## Configuration

A major feature of this suite is that its core behavior can be customized without editing any Python code. This is all handled through the `config.ini` file.

Here are some of the key settings you can change:

- **`[General]`**: Define which audio and image file extensions the scripts should recognize.
- **`[Gemini]`**: Change the AI model (`gemini-1.5-flash` by default) or even modify the prompt sent to the AI to better suit your needs or language preferences.
- **`[Validation]`**: Adjust the rules for the `validate_names.py` script, such as adding new "junk words" to ignore or changing word count thresholds for flagging names.
- **`[Tagging]`**: Control how metadata is written, including the format for album and track titles.
- **`[M4B]`**: Set the audio bitrate for `.m4b` files created by `create_m4b.py`.
- **`[Covers]`**: Define the minimum quality standards for cover art.

To make a change, simply open `config.ini` in a text editor, modify the value, and save the file. The scripts will use your new settings the next time they are run.

---

## Recommended Workflow

The main script for this suite is `ebooksort.py`. It is designed to be an all-in-one tool that handles the entire organization and tagging process from start to finish. For most use cases, this is the only script you will need to run.

1.  **Organize and Tag**: Simply run `ebooksort.py` on your folder of unorganized audiobooks. It will handle everything: grouping files, fetching metadata from Google Books and Gemini, downloading a high-quality cover, and writing all the tags to the audio files.

    ```bash
    python ebooksort.py "C:\Path\To\Your\Audiobooks"
    ```

The other scripts included in this project are powerful tools for maintenance, bulk editing, and other specific tasks. While not needed for the primary workflow, they are available for users who need more granular control over their library.

---

## Scripts and Usage

Here is a detailed breakdown of each script and its available command-line arguments.

### 1. `ebooksort.py` - The All-in-One Organizer

This is the main script. It takes a source directory, groups files, fetches metadata, finds the best possible cover art, and sorts everything into a clean library, writing all metadata tags to the files in the process. By default, it first queries Google Books for metadata and then falls back to the Gemini AI if needed.

**Usage:**

```bash
# Organize and tag in the same directory
python ebooksort.py "C:\Path\To\Your\Audiobooks"

# Organize to a different destination, skipping the tagging step
python ebooksort.py "C:\Source" -d "D:\Organized Library" --no-tagging

# Organize and force Gemini to be the only metadata source
python ebooksort.py "C:\Path\To\Your\Audiobooks" --force-gemini
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
    *   **Description**: Performs a simulation of the process. It prints all the actions that would be taken but does not execute any real action. Ideal for safely previewing changes.

*   **`--no-tagging`** (Optional, Flag)
    *   **Description**: Disables the automatic writing of metadata tags to the audio files. Use this if you prefer to run `write_tags.py` separately.

*   **`--force-gemini`** (Optional, Flag)
    *   **Description**: Forces the script to use only the Google Gemini API for fetching book metadata, skipping the initial check against Google Books.

### 2. `validate_names.py` - The Validator

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

### 3. `write_tags.py` - The Library Maintenance Tool

While `ebooksort.py` handles the initial tagging, `write_tags.py` remains a powerful tool for library maintenance and bulk editing.

**Why use it?**
- To fix covers for multiple books at once if they are missing or low-quality (`--mode fix-covers`).
- To perform bulk edits on metadata, such as correcting a misspelled author name across all their books (`--mode edit`).
- To re-tag a library if you have made manual changes to the `metadata.json` files.

**Usage:**
```bash
# Tag only new books (recommended)
python write_tags.py "D:\Organized Library" --mode smart

# Correct a misspelled author name across all their books
python write_tags.py "D:\Organized Library\Artur C Klark\*" --mode edit --field author --from "Artur C Klark" --to "Arthur C. Clarke"

# Find and fix missing covers across the entire library
python write_tags.py "D:\Organized Library" --mode fix-covers
```

**Arguments:**

*   **`target_path`** (Positional, Required)
    *   **Description**: The path to process. For most modes, this is a library directory or a single audio file. For `edit` mode, this is a **glob pattern** that selects the book folders to modify (e.g., `D:\Library\Author\*`).
    *   **Example (Directory)**: `D:\AudiobookLibrary`
    *   **Example (File)**: `D:\AudiobookLibrary\Author\Title\Chapter1.mp3`
    *   **Example (Edit Pattern)**: `D:\AudiobookLibrary\Some Author\*`

*   **`--mode`** (Optional)
    *   **Description**: Controls the script's behavior.
    *   **Default**: `smart`.
    *   **Options**:
        *   `smart`: (Recommended) Only processes books that have not been tagged before.
        *   `all`: Forcibly re-tags all books, overwriting existing metadata and covers.
        *   `tags-only`: Re-writes only the text metadata, leaving the cover art untouched.
        *   `cover-only`: Updates only the cover art, leaving other metadata intact.
        *   `fix-covers`: Scans for books that are missing a `cover.jpg` or have a low-quality one (non-square or below `min_resolution` in `config.ini`). It then downloads a high-quality replacement and embeds it.
        *   `fix-comments`: Copies the description tag to the comment tag if the comment is empty.
        *   `edit`: A powerful bulk-editing mode. Requires `--field`, `--from`, and `--to`. It modifies the `metadata.json` and then automatically re-tags the audio files.

*   **`--field`** (Edit Mode)
    *   **Description**: The metadata field to edit (e.g., `author`, `genre`, `series`, `title`).
    *   **Required for**: `--mode edit`.

*   **`--from`** (Edit Mode)
    *   **Description**: The existing (incorrect) value to search for within the specified field.
    *   **Required for**: `--mode edit`.

*   **`--to`** (Edit Mode)
    *   **Description**: The new (correct) value to replace the old value with.
    *   **Required for**: `--mode edit`.

*   **`--dry-run`** (Optional, Flag)
    *   **Description**: Performs a simulation. It prints all actions and file modifications that would occur but does not actually save any changes. Essential for safely previewing `edit` mode changes.

### 4. `update_covers.py` - The Cover Quality Manager

This powerful script scans your entire library to audit and upgrade your cover art based on quality rules you define in `config.ini`.

**Why use it?** It's the best way to ensure all books in your library have high-resolution, square cover art, replacing any that are low-quality or have incorrect dimensions.

**Usage:**
```bash
# Run in "smart" mode: only replaces covers that are missing, non-square, or low-resolution.
python update_covers.py "D:\Organized Library"

# Force replacement of ALL covers, regardless of current quality.
python update_covers.py "D:\Organized Library" --force

# Run in "audit" mode to generate an HTML report without changing any files.
python update_covers.py "D:\Organized Library" --mode audit
```

**Arguments:**

*   **`library_directory`** (Positional, Required)
    *   **Description**: The path to the root directory of your organized audiobook library.
    *   **Example**: `D:\AudiobookLibrary`

*   **`--mode`** (Optional)
    *   **Description**: Controls the script's execution mode.
    *   **Default**: `smart`.
    *   **Options**:
        *   `smart`: (Recommended) The default mode. It intelligently replaces a cover only if the existing one is missing, not square, or below the `min_resolution` defined in `config.ini`.
        *   `audit`: This mode does not change any files. Instead, it generates a `cover_audit.html` report in your library folder. This report details the quality of each existing cover and provides a preview link for the new cover the script would download, helping you decide whether to run the update.

*   **`--force`** (Optional, Flag)
    *   **Description**: Used with `smart` mode to force the replacement of **all** existing covers, ignoring their current quality.

### 5. `create_m4b.py` - The M4B Creator

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

### 6. `generate_inventory.py` - The Inventory Generator

This script regenerates the `inventory.csv` file from the metadata in your library. It's useful if you have manually moved or deleted books and want the inventory to reflect the current state.

**Usage:**
```bash
python generate_inventory.py "D:\Organized Library"
```

**Arguments:**

*   **`library_directory`** (Positional, Required)
    *   **Description**: The path to the root directory of your organized audiobook library.
    *   **Example**: `D:\AudiobookLibrary`

### 7. `populate_authors.py` - The Author Populator

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

### 8. `extract_covers.py` - The Cover Extractor

A simple utility that scans a directory, finds cover art embedded in audio files, and saves it as a `.jpg` file next to the original file.

**Usage:**
```bash
python extract_covers.py "C:\Path\To\Your\Audiobooks"
```

**Arguments:**

*   **`source_directory`** (Positional, Required)
    *   **Description**: The path to the directory (and subdirectories) containing the audio files from which you want to extract the cover art.
    *   **Example**: `C:\Audio\Temp`

### 9. `find_duplicates.py` - The Duplicate Finder

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
- **`Pillow`**: A powerful image processing library used for validating cover art dimensions and quality.

---

## License

This project is licensed under the **MIT License**.

This means you are free to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the software. The only requirement is to include the original copyright and permission notice in any substantial portions of the software. It is provided "as is", without warranty of any kind.