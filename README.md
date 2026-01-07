# USPTO Patent Interference Document Downloader

This tool downloads patent documents from the USPTO Patent Trial and Appeal Case Tracking System (P-TACTS) Interference proceedings.

## Background

### Patent Interference Proceedings

Patent interference proceedings are administrative proceedings conducted by the United States Patent and Trademark Office (USPTO) to determine which party was the first to invent a claimed invention. These proceedings are initiated when two or more patent applications claim the same invention, or when an application claims the same invention as an existing patent.

Interference proceedings are designed to resolve priority disputes by examining evidence of conception and reduction to practice of an invention. While the America Invents Act of 2011 changed the U.S. patent system from "first-to-invent" to "first-inventor-to-file," interference proceedings still exist for certain patent applications filed before March 16, 2013.

### USPTO's Patent Trial and Appeal Case Tracking System (P-TACTS)

The USPTO provides access to interference case information through the [Patent Trial and Appeal Case Tracking System (P-TACTS) Interference](https://ptacts.uspto.gov/interferences/public-informations/case-viewer). This system allows users to view and download documents related to interference proceedings, including:

- **Papers**: Official documents filed with the USPTO during the proceeding
- **Exhibits**: Supporting evidence submitted by the parties involved

## Tool Description

This tool automates the process of downloading all Papers and Exhibits PDF files associated with a specific interference case from the P-TACTS system. It:

1. Accesses the USPTO P-TACTS website with a given case number
2. Navigates through all pages of the Papers and Exhibits sections
3. Extracts download URLs for available documents
4. Downloads all accessible PDF files
5. Organizes downloaded files into appropriate folders

## Installation

### Prerequisites

- Python 3.12 or higher
- `uv` package manager

### Setting up the Environment

1. Install the `uv` package manager (if not already installed):

   ```bash
   curl -sSf https://raw.githubusercontent.com/astral-sh/uv/main/install.sh | bash
   ```

   
2. Clone this repository:

   ```bash
   git clone https://github.com/jsherkow/ptab_interference_scraper.git
   cd ptab_interference_scraper
   ```

That's it! No need to manually create a virtual environment or install dependencies. The `uv run` command will handle all of that automatically when you run the script.

## Usage

Run the tool using `uv run`:

```bash
uv run ptab_downloader <case_number> [output_directory]
```

### Examples

Download documents for case 106048 to the current directory:

```bash
uv run ptab_downloader 106048
```

Download documents for case 106048 to a specific directory:

```bash
uv run ptab_downloader 106048 /path/to/output/directory
```

### Output

The script creates the following directory structure:

```
<case_number>/
├── papers/
│   ├── 1-First_Paper_Title.pdf
│   ├── 2-Second_Paper_Title.pdf
│   └── ...
└── exhibits/
    ├── 1001-First_Exhibit_Title.pdf
    ├── 1002-Second_Exhibit_Title.pdf
    └── ...
```

## Important Notes

- The script uses a headless browser to navigate the website and extract document information.
- Some documents may not be downloadable due to access restrictions.
- The download process may take some time depending on the number and size of documents.

## Troubleshooting

If you encounter issues with the script:

1. Ensure you have a stable internet connection
2. Verify that the case number exists in the P-TACTS system
3. Check that you have sufficient disk space for downloads
4. Run with `uv run` to ensure all dependencies are properly loaded
