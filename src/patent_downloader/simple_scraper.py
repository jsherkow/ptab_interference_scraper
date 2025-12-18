"""Simple script to scrape Papers and Exhibits tables from USPTO case viewer."""

import asyncio
import sys
from pyppeteer import launch
from pyppeteer.page import Page
from pathlib import Path
import re
import aiohttp
import logging

async def get_papers(page: Page) -> list:
    """Extracts paper information from the Papers table in the USPTO case viewer.
    
    This function uses JavaScript evaluation to extract data from the AG Grid table
    in the 'papersSection' of the webpage. It retrieves information for each paper 
    including paper number, filing date, document name, and link availability.
    
    Args:
        page (Page): The pyppeteer Page object representing the browser page.
        
    Returns:
        list: List of dictionaries containing paper information with the following fields:
            - index: Row index within the current page view
            - paperNumber: The paper's identification number
            - filingDate: The date when the paper was filed
            - documentName: The name/title of the paper document
            - hasLink: Boolean indicating if the paper has a downloadable link
    """
    papers_data = await page.evaluate('''() => {
        const results = [];
        const papersSection = document.getElementById('papersSection');
        if (!papersSection) return results;
        
        const rows = papersSection.querySelectorAll('.ag-row');
        
        for (let i = 0; i < rows.length; i++) {
            const row = rows[i];
            const cells = row.querySelectorAll('.ag-cell');
            
            if (cells.length >= 4) {
                results.push({
                    index: i,
                    paperNumber: cells[0]?.textContent.trim() || 'N/A',
                    filingDate: cells[1]?.textContent.trim() || 'N/A',
                    documentName: cells[3]?.textContent.trim() || 'N/A',
                    hasLink: !!row.querySelector('app-open-document a')
                });
            }
        }
        
        return results;
    }'''
    )

    return papers_data

async def get_paper_urls(page: Page, papers_data: list, page_num: int, global_index_offset: int):
    """Extracts download URLs for papers by clicking their links in the USPTO case viewer.
    
    This function processes each paper in the provided list, clicks any available
    download links, captures the resulting URLs, and adds them to the paper data.
    
    Args:
        page (Page): The pyppeteer Page object representing the browser page.
        papers_data (list): List of dictionaries containing paper information.
        page_num (int): Current page number being processed (for logging).
        global_index_offset (int): Offset to calculate global indices across multiple pages.
        
    Returns:
        list: Enhanced list of paper dictionaries with added 'downloadUrl' and 'globalIndex' fields.
            Papers with no links or failed clicks will have appropriate error messages in their
            'downloadUrl' field.
    """
    papers_with_urls = []

    for paper in papers_data:  # Process all papers
        try:
            global_index = global_index_offset + paper['index']
            if not paper['hasLink']:
                print(f"[Page {page_num}][{global_index+1}] {paper['documentName'][:50]} - No link found")
                papers_with_urls.append({**paper, 'downloadUrl': 'N/A - No link', 'globalIndex': global_index})
                continue

            print(f"[Page {page_num}][{global_index+1}] {paper['documentName'][:50]}...", end=" ", flush=True)

            # Clear captured URLs and click the link
            await page.evaluate('window.capturedUrls = []')
            
            # Click the link for this specific row
            clicked = await page.evaluate(f'''() => {{
                const papersSection = document.getElementById('papersSection');
                const rows = papersSection.querySelectorAll('.ag-row');
                const row = rows[{paper['index']}];
                const link = row.querySelector('app-open-document a');
                if (link) {{
                    link.click();
                    return true;
                }}
                return false;
            }}''')

            if not clicked:
                print("✗ Click failed")
                papers_with_urls.append({**paper, 'downloadUrl': 'N/A - Click failed', 'globalIndex': global_index})
                continue

            # Give the click a moment to trigger window.open
            await asyncio.sleep(0.3)
            
            # Check if window.open was called and captured the URL
            captured = await page.evaluate('window.capturedUrls')
            
            if captured and len(captured) > 0:
                download_url = captured[0]
                papers_with_urls.append({**paper, 'downloadUrl': download_url, 'globalIndex': global_index})
                print(f"✓")
            else:
                print(f"✗ No URL captured")
                papers_with_urls.append({**paper, 'downloadUrl': 'N/A - No URL captured', 'globalIndex': global_index})

        except Exception as e:
            print(f"✗ Error: {e}")
            papers_with_urls.append({**paper, 'downloadUrl': f'Error: {str(e)[:50]}', 'globalIndex': global_index})

    return papers_with_urls


async def scroll_to_next_page(page: Page) -> bool:
    """Scroll the AG Grid table down to load a new page of content. 
    Returns True if new content loaded, False if no more content."""
    
    # Get current state before scrolling
    before_scroll_info = await page.evaluate('''() => {
        const papersSection = document.getElementById('papersSection');
        if (!papersSection) return null;
        
        const gridViewport = papersSection.querySelector('.ag-body-viewport');
        if (!gridViewport) return null;
        
        const rows = papersSection.querySelectorAll('.ag-row');
        const lastRow = rows[rows.length - 1];
        
        return {
            scrollTop: gridViewport.scrollTop,
            scrollHeight: gridViewport.scrollHeight,
            clientHeight: gridViewport.clientHeight,
            rowCount: rows.length,
            lastRowText: lastRow ? lastRow.textContent.trim() : null,
            // Track first visible row for better detection of new content
            firstVisibleRow: papersSection.querySelector('.ag-row:first-child')?.textContent.trim() || null
        };
    }''')
    
    if not before_scroll_info:
        print("Could not find scrollable grid viewport")
        return False
    
    print(f"Before scroll - Rows: {before_scroll_info['rowCount']}, ScrollTop: {before_scroll_info['scrollTop']}")
    print(f"scrollHeight {before_scroll_info['scrollHeight']}, firstVisibleRow {before_scroll_info['firstVisibleRow']}")
    
    # Check if we're already at the bottom
    if before_scroll_info['scrollTop'] + before_scroll_info['clientHeight'] >= before_scroll_info['scrollHeight']:
        print("Already at bottom of scrollable content")
        return False
    
    # Scroll down by a significant amount to ensure we see new rows
    # Instead of just the viewport height, we'll use a multiplier to move further
    scrolled = await page.evaluate('''() => {
        const papersSection = document.getElementById('papersSection');
        if (!papersSection) return false;
        
        const gridViewport = papersSection.querySelector('.ag-body-viewport');
        if (!gridViewport) return false;
        
        // Get the height of a typical row
        const rowHeight = papersSection.querySelector('.ag-row')?.clientHeight || 50;
        
        // Use a more conservative scroll amount to ensure we don't miss rows
        // Original was 20 rows or 3x viewport, now reduced to ensure more overlap
        const rowsToScroll = 15; // Scroll fewer rows to create more overlap
        const scrollAmount = rowHeight * rowsToScroll;
        
        console.log(`Using conservative scroll of ${rowsToScroll} rows to avoid missing content`);
        
        // Apply the scroll
        gridViewport.scrollTop += scrollAmount;
        
        console.log(`Scrolled down by ${scrollAmount}px (${rowsToScroll} rows)`);
        return true;
    }''')
    
    if not scrolled:
        return False
    
    # Wait longer for new content to load, especially if it's being fetched from server
    await asyncio.sleep(3)
    
    # Check if new content loaded
    after_scroll_info = await page.evaluate('''() => {
        const papersSection = document.getElementById('papersSection');
        if (!papersSection) return null;
        
        const gridViewport = papersSection.querySelector('.ag-body-viewport');
        if (!gridViewport) return null;
        
        const rows = papersSection.querySelectorAll('.ag-row');
        const lastRow = rows[rows.length - 1];
        
        // Collect row IDs or content to better detect new rows
        const rowContents = Array.from(rows).map(row => row.textContent.trim());
        
        return {
            scrollTop: gridViewport.scrollTop,
            scrollHeight: gridViewport.scrollHeight,
            clientHeight: gridViewport.clientHeight,
            rowCount: rows.length,
            lastRowText: lastRow ? lastRow.textContent.trim() : null,
            firstVisibleRow: papersSection.querySelector('.ag-row:first-child')?.textContent.trim() || null,
            rowContents: rowContents
        };
    }''')
    
    if not after_scroll_info:
        return False
    
    print(f"After scroll - Rows: {after_scroll_info['rowCount']}, ScrollTop: {after_scroll_info['scrollTop']}")
    
    # Check if we've actually moved in the grid
    if after_scroll_info['scrollTop'] <= before_scroll_info['scrollTop']:
        print("Warning: Scroll didn't move down - may be at the end of content")
        return False
    
    # Check for new content in multiple ways
    # 1. Check if the total row count has increased
    row_count_increased = after_scroll_info['rowCount'] > before_scroll_info['rowCount']
    
    # 2. Check if the visible content has changed
    content_changed = after_scroll_info['firstVisibleRow'] != before_scroll_info['firstVisibleRow']
    
    # 3. Check if we have rows that weren't in the previous view
    new_rows_found = False
    if 'rowContents' in after_scroll_info:
        for row_content in after_scroll_info['rowContents']:
            if row_content and row_content not in str(before_scroll_info.get('rowContents', [])):
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
    s = s.replace(' ', '_')
    
    # Remove any character that isn't alphanumeric, underscore, hyphen, or period
    s = re.sub(r'[^\w\-.]', '', s)
    
    # Remove leading/trailing periods and underscores
    s = s.strip('._')
    
    # Ensure it's not empty
    if not s:
        s = 'unnamed'
    
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
    if not download_url or not download_url.startswith('http'):
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
                content_type = response.headers.get('Content-Type', '').lower()
                if 'application/pdf' not in content_type and 'application/octet-stream' not in content_type:
                    print(f"Warning: Content might not be a PDF. Content-Type: {content_type}")
                
                # Read the content and save it
                content = await response.read()
                
                # Make sure parent directory exists
                output_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Write the PDF to the file
                with open(output_path, 'wb') as f:
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
    """
    url = f"https://ptacts.uspto.gov/interferences/public-informations/case-viewer/{case_number}"

    print(f"Launching browser and navigating to: {url}\n")

    # Launch browser with popup blocking disabled
    browser = await launch(
        headless=True,
        args=[
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-popup-blocking',  # Allow popups
            '--disable-features=site-per-process'  # Help with new window detection
        ]
    )

    try:
        page = await browser.newPage()
        await page.setViewport({'width': 1920, 'height': 1080})
        
        # Set up console log listener to forward browser console messages to stdout
        # page.on('console', lambda msg: print(f"Browser console: {msg.text}"))
        
        # Inject window.open interceptor BEFORE page loads
        await page.evaluateOnNewDocument('''() => {
            window.capturedUrls = [];
            const originalOpen = window.open;
            window.open = function(...args) {
                window.capturedUrls.push(args[0]);
                return originalOpen.apply(this, args);
            };
        }''')

        # Navigate to the page
        print("Loading page...")
        await page.goto(url, {'waitUntil': 'networkidle2', 'timeout': 60000})

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

        # Initialize variables for pagination
        all_papers_with_urls = []
        page_num = 1
        global_index_offset = 0
        
        print("=" * 120)
        print("STARTING PAGINATION LOOP")
        print("=" * 120)

        # Loop through all pages
        while True:
            print(f"\n--- Processing Page {page_num} ---")
            
            # Extract paper data from current page
            papers_data = await get_papers(page)
            
            if not papers_data:
                print(f"No papers found on page {page_num}. Stopping pagination.")
                break
            
            print(f"Found {len(papers_data)} papers on page {page_num}")

            # Extract download URLs for papers on current page
            print("=" * 120)
            print(f"EXTRACTING DOWNLOAD URLs - PAGE {page_num}")
            print("=" * 120)

            papers_with_urls = await get_paper_urls(page, papers_data, page_num, global_index_offset)
            all_papers_with_urls.extend(papers_with_urls)
            
            # Update global index offset for next page
            global_index_offset += len(papers_data)
            
            print(f"\nPage {page_num} complete. Processed {len(papers_data)} papers.")
            print(f"Total papers processed so far: {len(all_papers_with_urls)}")
            
            # Try to scroll to next page
            print(f"\nAttempting to scroll to page {page_num + 1}...")
            
            if not await scroll_to_next_page(page):
                print("No more pages available. Pagination complete.")
                break
                
            print(f"Successfully scrolled to page {page_num + 1}")
            page_num += 1
x
        print("\n" + "=" * 120)
        # Create a dictionary with downloadUrl as the key, which automatically removes duplicates
        unique_papers_dict = {paper['downloadUrl']: paper for paper in all_papers_with_urls}
        print(f"Full list contains {len(all_papers_with_urls)}")

        # Convert the dictionary values back to a list
        all_papers_with_urls = list(unique_papers_dict.values())
        print(f"Of which {len(all_papers_with_urls)} are unique")

        # Print final results
        print("\n" + "=" * 120)
        print("FINAL RESULTS - ALL PAGES")
        print("=" * 120)
        
        # Download PDFs for papers with valid URLs
        print("\n" + "=" * 120)
        print("DOWNLOADING PDFs")
        print("=" * 120)
        
        download_count = 0
        
        for paper in all_papers_with_urls:
            global_idx = paper.get('globalIndex', 0)
            output_path = download_path / safe_filename(f"{paper['paperNumber']}-{paper['documentName']}.pdf")
            
            print(f"{paper['paperNumber']:<10} | {paper['documentName'][:50]:<52} | ", end="", flush=True)
            
            # Download the PDF if a valid URL is available
            if paper.get('downloadUrl', '').startswith('http'):
                success = await download_pdf(paper['downloadUrl'], output_path)
                if success:
                    download_count += 1
                    print(f"✓ Downloaded to {output_path}")
                else:
                    print(f"✗ Download failed")
            else:
                print(f"✗ No valid URL ({paper.get('downloadUrl', 'N/A')})")

        print("\n" + "=" * 120)
        success_count = len([p for p in all_papers_with_urls if p.get('downloadUrl', '').startswith('http')])

        print(f"PAGINATION COMPLETE")
        print(f"Total pages processed: {page_num}")
        print(f"Total papers found: {len(all_papers_with_urls)}")
        print(f"Successfully extracted {success_count}/{len(all_papers_with_urls)} download URLs")
        print(f"Successfully downloaded {download_count}/{success_count} PDFs")
        print("=" * 120)

    finally:
        await browser.close()


async def main() -> None:
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python -m src.patent_downloader.simple_scraper <case_number>")
        print("Example: python -m src.patent_downloader.simple_scraper 106048")
        sys.exit(1)

    case_number = sys.argv[1]

    if len(sys.argv) == 3:
        download_path = Path(sys.argv[2])
    else:
        download_path = Path.cwd()

    download_path = download_path / case_number

    # Create the directory and all parent directories if they don't exist
    download_path.mkdir(parents=True, exist_ok=True)
    
    print(f"Downloading case {case_number} to {download_path}")

    await scrape_tables(case_number, download_path)


if __name__ == "__main__":
    asyncio.run(main())
