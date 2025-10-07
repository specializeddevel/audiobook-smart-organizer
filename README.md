# EbookSort - AI-Powered Audiobook Management Suite

EbookSort is a suite of Python scripts designed to automatically organize, tag, and manage your audiobook library. It transforms a folder of unorganized audio files into a clean, portable, and beautifully tagged collection.

## Core Features

- **Automatic Organization**: Intelligently groups loose audio files into book folders, named and structured by `Author/Title`.
- **AI-Powered Metadata**: Uses the Google Gemini API to fetch rich metadata for your audiobooks, including title, author, genre, series, year, and a full synopsis.
- **Rich Metadata Files**: For each book, it creates a `metadata.json` file with all fetched info and a `cover.jpg` file extracted from the audio.
- **Embedded Tags & Cover Art**: Embeds all metadata and the cover image directly into each audio file (`.mp3`, `.m4a`, `.m4b`, `.flac`), ensuring your library is portable and looks great on any device.
- **Master Inventory**: Generates and maintains a master `inventory.csv` file, perfect for viewing your library in a spreadsheet.
- **Efficient & Smart**: Avoids re-processing books that have already been tagged, making updates fast.

---

## Recommended Workflow

1.  **Organize**: Run `ebooksort.py` on your messy folder to classify and sort your books into a new, clean library directory.
2.  **Tag**: Run `write_tags.py` on the new library directory to embed all the metadata and cover art into the audio files. On subsequent runs, this will only tag new books you've added.
3.  **Inventory (Optional)**: Run `generate_inventory.py` whenever you want an up-to-date spreadsheet of your entire collection.

---

## The Scripts

This project includes three main scripts that form a complete workflow.

### 1. `ebooksort.py` - The Organizer

This is the first script you should run. It takes a source directory of unorganized audio files, groups them into books, fetches their metadata via the Gemini API, and sorts them into a clean `Author/Title` directory structure.

**Usage:**
```bash
# Basic usage (outputs to a new 'ebooks' folder)
python ebooksort.py "C:\Path\To\Your\Unorganized\Audiobooks"

# Specify a destination for the organized library
python ebooksort.py "C:\Path\To\Audiobooks" -d "D:\My Organized Library"
```

### 2. `write_tags.py` - The Tagger

This script reads the `metadata.json` and `cover.jpg` from each book folder and writes that information directly into the metadata tags of the audio files themselves.

**Usage:**
```bash
# Run on your organized library to tag all new books
python write_tags.py "D:\My Organized Library"

# Force a re-tag of the entire library
python write_tags.py "D:\My Organized Library" --force
```

### 3. `generate_inventory.py` - The Inventory Manager

This script allows you to generate or regenerate the `inventory.csv` file for your library at any time. It scans all the `metadata.json` files in your organized library and creates a fresh, pipe-delimited (`|`) CSV file.

**Usage:**
```bash
# Generate a new inventory.csv inside your library folder
python generate_inventory.py "D:\My Organized Library"
```

---

## Setup

### Requirements
- Python 3.x
- A Google Gemini API Key

### Installation
1.  **Download the project files.**
2.  **Install Dependencies:** Open a terminal in the project's directory and run:
    ```bash
    pip install -r requirements.txt
    ```
3.  **Set Up Your API Key:** The scripts require a Google Gemini API key to be set as an environment variable.

    **Windows:**
    ```cmd
    setx GOOGLE_API_KEY "YOUR_API_KEY_HERE"
    ```
    *(You may need to restart your terminal for this to take effect.)*

    **Linux/macOS:**
    ```bash
    export GOOGLE_API_KEY="YOUR_API_KEY_HERE"
    ```
    *(To make this permanent, add the line to your `.bashrc` or `.zshrc` file.)*

---

## Technologies Used

*   **Python 3**: The core language for all scripts.
*   **Google Gemini API**: Used for its powerful natural language processing to extract structured book metadata from simple filenames.
*   **`mutagen`**: A robust Python library used for reading and writing audio metadata tags across multiple formats (ID3 for MP3, MP4 atoms for M4A/M4B, and Vorbis comments for FLAC).
*   **`google-generativeai`**: The official Google client library for interacting with the Gemini API.

## Learning & Key Takeaways

This project served as a practical exercise in several key areas:

*   **API Integration**: Interacting with a powerful third-party AI service to enrich local data.
*   **File I/O and Management**: Systematically scanning, moving, and organizing files and directories.
*   **Metadata Handling**: Deep-diving into the complexities and differences between audio tagging standards (ID3 vs. MP4 vs. Vorbis). The iterative process of fixing compatibility issues (e.g., the comment tag in AIMP) highlighted the importance of understanding how different applications interpret metadata.
*   **Workflow Optimization**: Devising an efficient method (the `.tags_written` marker file) to prevent redundant processing in a large dataset, moving from a brute-force to a smart, incremental update strategy.
*   **Modular Tooling**: Building a suite of small, focused scripts that work together, rather than a single monolithic application. This provides greater flexibility and maintainability.

---

## Contributing

Contributions are welcome! If you have ideas for new features, find a bug, or see an opportunity to improve the code or documentation, please feel free to open an issue or submit a pull request.

## License

This project is licensed under the **MIT License**.

This means you are free to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the software. The only requirement is to include the original copyright and permission notice in any substantial portions of the software.