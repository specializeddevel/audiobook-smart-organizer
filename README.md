# EbookSort - AI-Powered Audiobook Sorter

EbookSort is a Python script that automatically organizes your audiobook library. It takes a directory of unorganized audio files, intelligently groups them, fetches rich metadata using the Google Gemini API, and then sorts them into a clean, consistently-named `Author/Title` directory structure.

## Key Features

- **Automatic Grouping**: Intelligently groups loose audio files (e.g., `Book-Part1.mp3`, `Book-Part2.mp3`) into a single book entity for processing.
- **AI-Powered Metadata**: Uses Google's Gemini API to fetch rich metadata for your audiobooks, including title, author, genre, series, year, and synopsis.
- **Robust Cover Art Extraction**: Employs the powerful `mutagen` library to find and extract embedded cover art from a wide variety of formats (MP3, M4A, M4B, FLAC).
- **Consistent Naming**: Automatically formats all generated author and title folders into `Title Case` for a clean and uniform library appearance.
- **Rich Metadata Files**: For each book, it creates:
    - A detailed `metadata.json` file containing all fetched info, plus processing date, file count, total size, and a list of original files.
    - An extracted `cover.jpg` file if cover art is found.
- **Master Inventory**: Generates and maintains a master `inventory.csv` file in your destination folder. This file is pipe-delimited for maximum compatibility and contains a full overview of your library.
- **Smart Error Handling**:
    - Moves unclassifiable books into an `unclassified` folder without crashing.
    - Prevents errors from duplicate unclassified books by renaming new additions with a numerical suffix (e.g., `Book Title (2)`).

## How It Works

The script operates in two main phases:

1.  **Phase 1: Grouping**: The script scans the source directory and uses file names to guess which files belong to the same book. It moves these groups into temporary subfolders with standardized Title Case names.
2.  **Phase 2: Classification**: It then processes each temporary folder, makes a single API call to Gemini to get the book's information, and moves the folder to its final, organized location (`Author/Title`), also in Title Case.

## Requirements

- Python 3.x
- A Google Gemini API Key

## Setup

1.  **Download the script and `requirements.txt` file.**

2.  **Install Dependencies:**
    The script relies on a few external libraries. Install them by opening a terminal in the project's directory and running:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Set Up Your API Key:**
    The script requires a Google Gemini API key to be set as an environment variable.

    **Windows:**
    ```cmd
    setx GOOGLE_API_KEY "YOUR_API_KEY_HERE"
    ```
    (You may need to restart your terminal for this to take effect.)

    **Linux/macOS:**
    ```bash
    export GOOGLE_API_KEY="YOUR_API_KEY_HERE"
    ```
    (To make this permanent, add the line to your `.bashrc` or `.zshrc` file.)

## Usage

Run the script from your terminal, providing the path to your folder of unorganized audiobooks.

**Basic Usage:**
```bash
python ebooksort.py "C:\\Path\\To\\Your\\Audiobooks"
```
This will process the audiobooks and place them in a default folder named `ebooks` inside the current directory.

**Specifying a Destination:**
Use the `-d` or `--destination_directory` flag to specify a different output folder.
```bash
python ebooksort.py "C:\\Path\\To\\Your\\Audiobooks" -d "D:\\My Organized Library"
```

## The `inventory.csv` File

In the root of your destination directory, the script creates and maintains an `inventory.csv` file. This file provides a complete, spreadsheet-friendly overview of your entire sorted library.

**Important:** This file uses a **pipe (`|`)** as a separator to avoid conflicts with commas in titles or synopses.

**How to Import into Google Sheets/Excel:**
1.  Go to `File -> Import` or `Data -> From Text/CSV`.
2.  Upload the `inventory.csv` file.
3.  When prompted for a delimiter, choose **"Custom"** or **"Other"**.
4.  Enter the pipe character (`|`) in the custom delimiter field.
5.  Your data will now be correctly organized into columns.

The columns included are: `Title`, `Author`, `Genre`, `Series`, `Year`, `Synopsis`, `Path`, `ProcessingDate`, `FileCount`, `TotalSizeMB`, and `CoverArtFound`.
