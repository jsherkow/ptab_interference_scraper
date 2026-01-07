"""Simple script to scrape Papers and Exhibits tables from USPTO case viewer."""

import asyncio
import re
import sys
from pathlib import Path

import aiohttp
from pyppeteer import launch
from pyppeteer.page import Page


async def get_papers(page: Page, section_id: str = "papersSection") -> list:
    """Extracts document information from the specified section in the USPTO case viewer.

    This function uses JavaScript evaluation to extract data from the AG Grid table
    in the specified section (either 'papersSection' or 'exhibitsSection') of the webpage.
    It retrieves information for each document including number, filing date, name,
    and link availability.

    Args:
        page (Page): The pyppeteer Page object representing the browser page.
        section_id (str): The ID of the section to process ('papersSection' or 'exhibitsSection').
            Defaults to 'papersSection'.

    Returns:
        list: List of dictionaries containing document information with the following fields:
            - index: Row index within the current page view
            - paperNumber: The document's identification number
            - filingDate: The date when the document was filed
            - documentName: The name/title of the document
            - hasLink: Boolean indicating if the document has a downloadable link
    """
    document_name_col = 3 if section_id == "papersSection" else 2
    paper_number_col = 0
    filing_date_col = 1
    papers_data = await page.evaluate(f"""() => {{
        const results = [];
        const section = document.getElementById('{section_id}');
        if (!section) return results;

        const rows = section.querySelectorAll('.ag-row');

        for (let i = 0; i < rows.length; i++) {{
            const row = rows[i];
            const cells = row.querySelectorAll('.ag-cell');

            if (cells.length >= 4) {{
                results.push({{
                    index: i,
                    paperNumber: cells[{paper_number_col}]?.textContent.trim() || 'N/A',
                    filingDate: cells[{filing_date_col}]?.textContent.trim() || 'N/A',
                    documentName: cells[{document_name_col}]?.textContent.trim() || 'N/A',
                    hasLink: !!row.querySelector('app-open-document a')
                }});
            }}
        }}

        return results;
    }}""")

    return papers_data


async def get_paper_urls(page: Page, papers_data: list, page_num: int, global_index_offset: int, section_id: str = "papersSection"):
    """Extracts download URLs for documents by clicking their links in the USPTO case viewer.

    This function processes each document in the provided list, clicks any available
    download links, captures the resulting URLs, and adds them to the document data.

    Args:
        page (Page): The pyppeteer Page object representing the browser page.
        papers_data (list): List of dictionaries containing document information.
        page_num (int): Current page number being processed (for logging).
        global_index_offset (int): Offset to calculate global indices across multiple pages.
        section_id (str): The ID of the section to process ('papersSection' or 'exhibitsSection').
            Defaults to 'papersSection'.

    Returns:
        list: Enhanced list of document dictionaries with added 'downloadUrl' and 'globalIndex' fields.
            Documents with no links or failed clicks will have appropriate error messages in their
            'downloadUrl' field.
    """
    papers_with_urls = []

    for paper in papers_data:  # Process all papers
        try:
            global_index = global_index_offset + paper["index"]
            if not paper["hasLink"]:
                print(f"[Page {page_num}][{global_index + 1}] {paper['documentName'][:50]} - No link found")
                papers_with_urls.append({**paper, "downloadUrl": "N/A - No link", "globalIndex": global_index})
                continue

            print(f"[Page {page_num}][{global_index + 1}] {paper['documentName'][:50]}...", end=" ", flush=True)

            # Clear captured URLs and click the link
            await page.evaluate("window.capturedUrls = []")

            # Click the link for this specific row
            clicked = await page.evaluate(f"""() => {{
                const section = document.getElementById('{section_id}');
                const rows = section.querySelectorAll('.ag-row');
                const row = rows[{paper["index"]}];
                const link = row.querySelector('app-open-document a');
                if (link) {{
                    link.click();
                    return true;
                }}
                return false;
            }}""")

            if not clicked:
                print("✗ Click failed")
                papers_with_urls.append({**paper, "downloadUrl": "N/A - Click failed", "globalIndex": global_index})
                continue

            # Give the click a moment to trigger window.open
            await asyncio.sleep(0.3)

            # Check if window.open was called and captured the URL
            captured = await page.evaluate("window.capturedUrls")

            if captured and len(captured) > 0:
                download_url = captured[0]
                papers_with_urls.append({**paper, "downloadUrl": download_url, "globalIndex": global_index})
                print("✓")
            else:
                print("✗ No URL captured")
                papers_with_urls.append({**paper, "downloadUrl": "N/A - No URL captured", "globalIndex": global_index})

        except Exception as e:
            print(f"✗ Error: {e}")
            papers_with_urls.append({**paper, "downloadUrl": f"Error: {str(e)[:50]}", "globalIndex": global_index})

    return papers_with_urls


async def scroll_to_next_page(page: Page, section_id: str = "papersSection") -> bool:
    """Scroll the AG Grid table down to load a new page of content.

    Args:
        page (Page): The pyppeteer Page object representing the browser page.
        section_id (str): The ID of the section to scroll ('papersSection' or 'exhibitsSection').
            Defaults to 'papersSection'.

    Returns:
        bool: True if new content loaded, False if no more content.
    """

    # Get current state before scrolling
    before_scroll_info = await page.evaluate(f"""() => {{
        const section = document.getElementById('{section_id}');
        if (!section) return null;

        const gridViewport = section.querySelector('.ag-body-viewport');
        if (!gridViewport) return null;

        const rows = section.querySelectorAll('.ag-row');
        const lastRow = rows[rows.length - 1];

        return {{
            scrollTop: gridViewport.scrollTop,
            scrollHeight: gridViewport.scrollHeight,
            clientHeight: gridViewport.clientHeight,
            rowCount: rows.length,
            lastRowText: lastRow ? lastRow.textContent.trim() : null,
            // Track first visible row for better detection of new content
            firstVisibleRow: section.querySelector('.ag-row:first-child')?.textContent.trim() || null
        }};
    }}""")

    if not before_scroll_info:
        print("Could not find scrollable grid viewport")
        return False

    print(f"Before scroll - Rows: {before_scroll_info['rowCount']}, ScrollTop: {before_scroll_info['scrollTop']}")
    print(f"scrollHeight {before_scroll_info['scrollHeight']}, firstVisibleRow {before_scroll_info['firstVisibleRow']}")

    # Check if we're already at the bottom
    if before_scroll_info["scrollTop"] + before_scroll_info["clientHeight"] >= before_scroll_info["scrollHeight"]:
        print("Already at bottom of scrollable content")
        return False

    # Scroll down by a significant amount to ensure we see new rows
    # Instead of just the viewport height, we'll use a multiplier to move further
    scrolled = await page.evaluate(f"""() => {{
        const section = document.getElementById('{section_id}');
        if (!section) return false;

        const gridViewport = section.querySelector('.ag-body-viewport');
        if (!gridViewport) return false;

        // Get the height of a typical row
        const rowHeight = section.querySelector('.ag-row')?.clientHeight || 50;

        // Use a more conservative scroll amount to ensure we don't miss rows
        // Original was 20 rows or 3x viewport, now reduced to ensure more overlap
        const rowsToScroll = 15; // Scroll fewer rows to create more overlap
        const scrollAmount = rowHeight * rowsToScroll;

        console.log(`Using conservative scroll of ${{rowsToScroll}} rows to avoid missing content`);

        // Apply the scroll
        gridViewport.scrollTop += scrollAmount;

        console.log(`Scrolled down by ${{scrollAmount}}px (${{rowsToScroll}} rows)`);
        return true;
    }}""")

    if not scrolled:
        return False

    # Wait longer for new content to load, especially if it's being fetched from server
    await asyncio.sleep(3)

    # Check if new content loaded
    after_scroll_info = await page.evaluate(f"""() => {{
        const section = document.getElementById('{section_id}');
        if (!section) return null;

        const gridViewport = section.querySelector('.ag-body-viewport');
        if (!gridViewport) return null;

        const rows = section.querySelectorAll('.ag-row');
        const lastRow = rows[rows.length - 1];

        // Collect row IDs or content to better detect new rows
        const rowContents = Array.from(rows).map(row => row.textContent.trim());

        return {{
            scrollTop: gridViewport.scrollTop,
            scrollHeight: gridViewport.scrollHeight,
            clientHeight: gridViewport.clientHeight,
            rowCount: rows.length,
            lastRowText: lastRow ? lastRow.textContent.trim() : null,
            firstVisibleRow: section.querySelector('.ag-row:first-child')?.textContent.trim() || null,
            rowContents: rowContents
        }};
    }}""")

    if not after_scroll_info:
        return False

    print(f"After scroll - Rows: {after_scroll_info['rowCount']}, ScrollTop: {after_scroll_info['scrollTop']}")

    # Check if we've actually moved in the grid
    if after_scroll_info["scrollTop"] <= before_scroll_info["scrollTop"]:
        print("Warning: Scroll didn't move down - may be at the end of content")
        return False

    # Check for new content in multiple ways
    # 1. Check if the total row count has increased
    row_count_increased = after_scroll_info["rowCount"] > before_scroll_info["rowCount"]

    # 2. Check if the visible content has changed
    content_changed = after_scroll_info["firstVisibleRow"] != before_scroll_info["firstVisibleRow"]

    # 3. Check if we have rows that weren't in the previous view
    new_rows_found = False
    if "rowContents" in after_scroll_info:
        for row_content in after_scroll_info["rowContents"]:
            if row_content and row_content not in str(before_scroll_info.get("rowContents", [])):
                new_rows_found = True
                break

    has_new_content = row_count_increased or content_changed or new_rows_found

    if not has_new_content:
        print("No new content loaded after scrolling")
        return False

    if row_count_increased:
        print(f"New content detected! Row count changed from {before_scroll_info['rowCount']} to {after_scroll_info['rowCount']}")
    elif content_changed:
        print("New content detected! Visible rows have changed.")
    elif new_rows_found:
        print("New content detected! Found rows that weren't visible before.")

    return True


def safe_filename(s, max_length=255) -> Path:
    # Replace spaces with underscores
    s = s.replace(" ", "_")

    # Remove any character that isn't alphanumeric, underscore, hyphen, or period
    s = re.sub(r"[^\w\-.]", "", s)

    # Remove leading/trailing periods and underscores
    s = s.strip("._")

    # Ensure it's not empty
    if not s:
        s = "unnamed"

    # Truncate to max length
    return Path(s[:max_length])


async def download_pdf(download_url: str, output_path: Path) -> bool:
    """Downloads a PDF file from the given URL and saves it to the specified path.

    Args:
        download_url (str): The URL to download the PDF from.
        output_path (Path): The file path where the PDF should be saved.

    Returns:
        bool: True if the download was successful, False otherwise.
    """
    if not download_url or not download_url.startswith("http"):
        print(f"Cannot download from invalid URL: {download_url}")
        return False

    try:
        print(f"Downloading PDF from: {download_url}")
        print(f"Saving to: {output_path}")

        async with aiohttp.ClientSession() as session:
            async with session.get(download_url) as response:
                if response.status != 200:
                    print(f"Failed to download PDF: HTTP {response.status}")
                    return False

                # Check if the content is a PDF (by checking content-type or first few bytes)
                content_type = response.headers.get("Content-Type", "").lower()
                if "application/pdf" not in content_type and "application/octet-stream" not in content_type:
                    print(f"Warning: Content might not be a PDF. Content-Type: {content_type}")

                # Read the content and save it
                content = await response.read()

                # Make sure parent directory exists
                output_path.parent.mkdir(parents=True, exist_ok=True)

                # Write the PDF to the file
                with open(output_path, "wb") as f:
                    f.write(content)

                print(f"Successfully downloaded PDF ({len(content) // 1024} KB)")
                return True

    except Exception as e:
        print(f"Error downloading PDF: {str(e)}")
        return False


async def scrape_tables(case_number: str, download_path: Path) -> None:
    """Scrape and print Papers and Exhibits tables from USPTO case viewer.

    Args:
        case_number: The USPTO case number to scrape.
        download_path: The path where downloaded files will be saved.
    """
    url = f"https://ptacts.uspto.gov/interferences/public-informations/case-viewer/{case_number}"

    print(f"Launching browser and navigating to: {url}\n")

    # Launch browser with popup blocking disabled
    browser = await launch(
        headless=True,
        args=[
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-popup-blocking",  # Allow popups
            "--disable-features=site-per-process",  # Help with new window detection
        ],
    )

    try:
        page = await browser.newPage()
        await page.setViewport({"width": 1920, "height": 1080})

        # Set up console log listener to forward browser console messages to stdout
        # page.on('console', lambda msg: print(f"Browser console: {msg.text}"))

        # Inject window.open interceptor BEFORE page loads
        await page.evaluateOnNewDocument("""() => {
            window.capturedUrls = [];
            const originalOpen = window.open;
            window.open = function(...args) {
                window.capturedUrls.push(args[0]);
                return originalOpen.apply(this, args);
            };
        }""")

        # Navigate to the page
        print("Loading page...")
        await page.goto(url, {"waitUntil": "networkidle2", "timeout": 60000})

        # Wait for the Angular app and AG Grid to load
        print("Waiting for Angular content to load...")

        # Poll for AG Grid to appear (Angular takes time to render)
        max_attempts = 20
        for attempt in range(max_attempts):
            grid_count = await page.evaluate('document.querySelectorAll("ag-grid-angular").length')
            if grid_count > 0:
                print(f"AG Grid found after {attempt + 1} attempts ({(attempt + 1) * 1} seconds)")
                break
            await asyncio.sleep(1)
        else:
            print(f"Warning: No AG Grid found after {max_attempts} seconds")

        # Give AG Grid more time to fully populate with data
        print("Waiting for grid data to load...\n")
        await asyncio.sleep(3)

        # Process both the Papers and Exhibits sections
        sections = ["papersSection", "exhibitsSection"]
        all_documents_with_urls = []

        for section_id in sections:
            print("\n" + "=" * 120)
            print(f"PROCESSING {section_id.upper().replace('SECTION', '')}")
            print("=" * 120)

            # Initialize variables for pagination
            page_num = 1
            global_index_offset = 0
            section_documents_with_urls = []

            print("=" * 120)
            print(f"STARTING PAGINATION LOOP FOR {section_id.upper().replace('SECTION', '')}")
            print("=" * 120)

            # Loop through all pages for this section
            while True:
                print(f"\n--- Processing Page {page_num} ---")

                # Extract document data from current page
                documents_data = await get_papers(page, section_id)

                if not documents_data:
                    print(f"No documents found on page {page_num} for {section_id}. Stopping pagination.")
                    break

                print(f"Found {len(documents_data)} documents on page {page_num}")

                # Extract download URLs for documents on current page
                print("=" * 120)
                print(f"EXTRACTING DOWNLOAD URLs - PAGE {page_num}")
                print("=" * 120)

                documents_with_urls = await get_paper_urls(page, documents_data, page_num, global_index_offset, section_id)
                section_documents_with_urls.extend(documents_with_urls)

                # Update global index offset for next page
                global_index_offset += len(documents_data)

                print(f"\nPage {page_num} complete. Processed {len(documents_data)} documents.")
                print(f"Total documents processed so far in {section_id}: {len(section_documents_with_urls)}")

                # Try to scroll to next page
                print(f"\nAttempting to scroll to page {page_num + 1}...")

                if not await scroll_to_next_page(page, section_id):
                    print(f"No more pages available in {section_id}. Pagination complete.")
                    break

                print(f"Successfully scrolled to page {page_num + 1}")
                page_num += 1

            print("\n" + "=" * 120)
            print(f"COMPLETED {section_id.upper().replace('SECTION', '')} SECTION")
            print(f"Total documents found in {section_id}: {len(section_documents_with_urls)}")
            print("=" * 120)

            # Add section type to each document
            for doc in section_documents_with_urls:
                doc["sectionType"] = section_id

            # Add documents from this section to the overall list
            all_documents_with_urls.extend(section_documents_with_urls)

        # Create a dictionary with downloadUrl as the key, which automatically removes duplicates
        unique_documents_dict = {doc["downloadUrl"]: doc for doc in all_documents_with_urls}
        print(f"Full list contains {len(all_documents_with_urls)} documents")

        # Convert the dictionary values back to a list
        all_documents_with_urls = list(unique_documents_dict.values())
        print(f"Of which {len(all_documents_with_urls)} are unique")

        # Print final results
        print("\n" + "=" * 120)
        print("FINAL RESULTS - ALL SECTIONS")
        print("=" * 120)

        # Download PDFs for documents with valid URLs
        print("\n" + "=" * 120)
        print("DOWNLOADING PDFs")
        print("=" * 120)

        download_count = 0

        for doc in all_documents_with_urls:
            doc.get("globalIndex", 0)
            section_type = doc.get("sectionType", "unknown").replace("Section", "")

            # Include section type in the filename
            section_id.removesuffix("Section")  # "papers" or "exhibits"

            output_path = download_path / section_type / safe_filename(f"{doc['paperNumber']}-{doc['documentName']}.pdf")

            print(f"[{section_type}] {doc['paperNumber']:<10} | {doc['documentName'][:50]:<52} | ", end="", flush=True)

            # Download the PDF if a valid URL is available
            if doc.get("downloadUrl", "").startswith("http"):
                success = await download_pdf(doc["downloadUrl"], output_path)
                if success:
                    download_count += 1
                    print(f"✓ Downloaded to {output_path}")
                else:
                    print("✗ Download failed")
            else:
                print(f"✗ No valid URL ({doc.get('downloadUrl', 'N/A')})")

        print("\n" + "=" * 120)
        success_count = len([d for d in all_documents_with_urls if d.get("downloadUrl", "").startswith("http")])

        print("SCRAPING COMPLETE")
        print(f"Total documents found: {len(all_documents_with_urls)}")
        print(f"Successfully extracted {success_count}/{len(all_documents_with_urls)} download URLs")
        print(f"Successfully downloaded {download_count}/{success_count} PDFs")
        print("=" * 120)

    finally:
        await browser.close()


async def main() -> None:
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: uv run ptab_downloader <case_number> [download_path]")
        print("Example: uv run ptab_downloader 106048")
        sys.exit(1)

    case_number = sys.argv[1]

    if len(sys.argv) == 3:
        download_path = Path(sys.argv[2])
    else:
        download_path = Path.cwd()

    download_path = download_path / case_number

    # Create the directory and all parent directories if they don't exist
    download_path.mkdir(parents=True, exist_ok=True)

    # Create directories for papers and exhibits
    (download_path / Path("papers")).mkdir(parents=True, exist_ok=True)
    (download_path / Path("exhibits")).mkdir(parents=True, exist_ok=True)

    print(f"Downloading case {case_number} to {download_path}")

    await scrape_tables(case_number, download_path)


def cli() -> None:
    """CLI entry point for ptab_downloader."""
    asyncio.run(main())


if __name__ == "__main__":
    cli()
