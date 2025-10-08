# AudioBookSort - AI-Powered Audiobook Management Suite

AudioBookSort is a suite of Python scripts designed to automatically organize, tag, and manage your audiobook library. It transforms a folder of unorganized audio files into a clean, portable, and beautifully tagged collection.

## Core Features

- **Automatic Organization**: Intelligently groups loose audio files into book folders, named and structured by `Author/Title`.
- **AI-Powered Metadata**: Uses the Google Gemini API to fetch rich metadata (title, author, series, synopsis, etc.) for your audiobooks.
- **Multi-Source Cover Art**: Automatically finds the best available cover art through a 3-step process:
    1.  Detects local image files (e.g., `MyBook.jpg`).
    2.  Extracts embedded cover art from audio files.
    3.  Searches the internet for a high-quality cover if no local art is found.
- **Advanced & Granular Tagging**: Embeds all metadata and cover art directly into each audio file (`.mp3`, `.m4a`, `.m4b`, `.flac`) with multiple modes for precise control.
- **Robust and Safe**: The organization process uses a safe staging area to prevent file loss if the script is interrupted. It's also fault-tolerant, skipping individual books that have errors without stopping the entire process.
- **Library Maintenance**: Includes tools to pre-extract existing covers for review and to find and fix books missing cover art in an already organized library.
- **Master Inventory**: Generates and maintains a master `inventory.csv` file, perfect for viewing your library in a spreadsheet.

---

## Recommended Workflow

The workflow is designed to be flexible, giving you control at each step.

### Step 1: (Optional) Extract Existing Covers
Run `extract_covers.py` on your messy folder. This script finds all audio files with embedded cover art and saves that art as a `.jpg` file next to the original audio file.

**Why do this?** It gives you a clear visual overview of which books already have covers before you start the main organization.

```bash
python extract_covers.py "C:\Path\To\Your\Unorganized\Audiobooks"
```

### Step 2: Organize the Library
Run `ebooksort.py`. This is the main workhorse. It will:
1.  Group your audio files into book folders in a safe staging area.
2.  Get high-quality metadata from the Gemini API.
3.  Find the best cover art by searching local files, embedded tags, and finally the internet.
4.  Move the organized books into a clean `Author/Title` structure.

```bash
python ebooksort.py "C:\Path\To\Your\Unorganized\Audiobooks" -d "D:\My Organized Library"
```

### Step 3: Tag the Files
Run `write_tags.py` on the newly organized library. This embeds all the metadata and the final cover art into each audio file, making your library perfectly portable.

```bash
# Use 'smart' mode to only tag new books
python write_tags.py "D:\My Organized Library" --mode smart
```

### Step 4: (Optional) Maintain and Generate Inventory
- Run `write_tags.py --mode fix-covers` at any time to scan your library and automatically download and embed missing covers for books that were already organized.
- Run `generate_inventory.py` whenever you want an up-to-date spreadsheet of your entire collection.

---

## The Scripts

### 1. `extract_covers.py` - The Cover Extractor
This script is your first step for pre-flight checks. It scans a directory, finds all audio files with embedded art, and extracts it as a `.jpg` file with the same name. This helps you see what you have before you start.

**Usage:**
```bash
python extract_covers.py "C:\Path\To\Audiobooks"
```

### 2. `ebooksort.py` - The Organizer
This is the core script. It takes a source directory, groups files, and uses the Gemini API and web search to classify, enrich, and sort them into a clean `Author/Title` directory structure.

> **New in this version:**
> - **Online Cover Search**: If no local or embedded cover is found, this script will automatically search the internet for a suitable cover.
> - **Safe Staging Area**: All operations are performed in a temporary `_ebooksort_staging_...` folder. If the script fails or is cancelled, your files remain safely in this folder for recovery, preventing data loss.
> - **Fault-Tolerant**: If processing a single book fails, the script will log the error and continue with the rest of the library.

**Usage:**
```bash
python ebooksort.py "C:\Path\To\Audiobooks" -d "D:\My Organized Library"
```

### 3. `write_tags.py` - The Advanced Tagger
This script writes the `metadata.json` and `cover.jpg` information directly into the audio files' metadata tags.

**Tagging Modes**
Includes `smart`, `all`, `tags-only`, `cover-only`, and the new maintenance mode:

*   `--mode fix-covers` (New!)
    *   Scans an entire library for books that are missing a `cover.jpg` file.
    *   For each one it finds, it reads the `metadata.json`, searches for a cover online, downloads it, and embeds it into the audio files. Perfect for repairing an existing library.

**Usage**
```bash
# Find and fix books with missing covers in your library
python write_tags.py "D:\My Organized Library" --mode fix-covers

# Run in default smart mode to tag new additions
python write_tags.py "D:\My Organized Library" --mode smart
```

### 4. `generate_inventory.py` - The Inventory Manager
This script's functionality remains the same. It generates a master `inventory.csv` file for your library.

**Usage:**
```bash
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
    *(This will install `google-generativeai`, `mutagen`, `requests`, and `ddgs`)*.
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
*   **Google Gemini API**: Used for its powerful natural language processing to extract structured book metadata.
*   **`mutagen`**: A robust Python library for reading and writing audio metadata tags.
*   **`ddgs`**: Used to perform web searches for cover art via DuckDuckGo, avoiding the need for an additional API key.
*   **`requests`**: A standard, powerful library for making HTTP requests to download cover images.
*   **`google-generativeai`**: The official Google client library for the Gemini API.

## Learning & Key Takeaways

This project served as a practical exercise in several key areas:

*   **API Integration**: Interacting with third-party AI and search services to enrich local data.
*   **File I/O and Management**: Systematically scanning, moving, and organizing files and directories.
*   **Fault Tolerance**: Implementing robust `try...except` blocks for network requests and file operations makes a script usable for large batches, as a single failure doesn't halt the entire process.
*   **Safe File Operations**: Using a staging area for destructive operations like moving files is critical to prevent data loss if a script is interrupted.
*   **Metadata Handling**: Deep-diving into the complexities of audio tagging standards (ID3 vs. MP4 vs. Vorbis).
*   **Modular Tooling**: Building a suite of small, focused scripts that work together provides greater flexibility and maintainability.

---

## Contributing

Contributions are welcome! If you have ideas for new features, find a bug, or see an opportunity to improve the code or documentation, please feel free to open an issue or submit a pull request.

## License

This project is licensed under the **MIT License**.

This means you are free to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the software. The only requirement is to include the original copyright and permission notice in any substantial portions of the software.