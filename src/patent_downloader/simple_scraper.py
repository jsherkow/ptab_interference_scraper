"""Simple script to scrape Papers and Exhibits tables from USPTO case viewer."""

import asyncio
import sys
from pyppeteer import launch
from pyppeteer.page import Page

async def get_papers(page: Page) -> list:
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

async def get_paper_urls(page: Page, papers_data: list):
    papers_with_urls = []

    for paper in papers_data:  # Process all papers
        try:
            if not paper['hasLink']:
                print(f"[{paper['index']+1}] {paper['documentName'][:50]} - No link found")
                papers_with_urls.append({**paper, 'downloadUrl': 'N/A - No link'})
                continue

            print(f"[{paper['index']+1}] {paper['documentName'][:50]}...", end=" ", flush=True)

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
                papers_with_urls.append({**paper, 'downloadUrl': 'N/A - Click failed'})
                continue

            # Give the click a moment to trigger window.open
            await asyncio.sleep(0.3)
            
            # Check if window.open was called and captured the URL
            captured = await page.evaluate('window.capturedUrls')
            
            if captured and len(captured) > 0:
                download_url = captured[0]
                papers_with_urls.append({**paper, 'downloadUrl': download_url})
                print(f"✓")
            else:
                print(f"✗ No URL captured")
                papers_with_urls.append({**paper, 'downloadUrl': 'N/A - No URL captured'})

        except Exception as e:
            print(f"✗ Error: {e}")
            papers_with_urls.append({**paper, 'downloadUrl': f'Error: {str(e)[:50]}'})

    return papers_with_urls



async def scrape_tables(case_number: str) -> None:
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
        
        # Inject window.open interceptor BEFORE page loads
        await page.evaluateOnNewDocument('''() => {
            window.capturedUrls = [];
            const originalOpen = window.open;
            window.open = function(...args) {
                console.log('window.open called with URL:', args[0]);
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

        # Extract all paper data first
        print("=" * 120)
        print("EXTRACTING PAPERS DATA")
        print("=" * 120)

        papers_data = await get_papers(page)
        print(type(papers_data))

        print(f"Found {len(papers_data)} papers\n")

        if not papers_data:
            print("No papers found. Exiting.")
            return

        # Now click each link to get download URLs
        print("=" * 120)
        print("EXTRACTING DOWNLOAD URLs")
        print("=" * 120)


        papers_with_urls = await get_paper_urls(page, papers_data)

        # Print results
        print("\n" + "=" * 120)
        print("PAPERS TABLE WITH DOWNLOAD URLs")
        print("=" * 120)
        
        for paper in papers_with_urls:
            print(f"{paper['paperNumber']:<10} | {paper['documentName'][:50]:<52} | {paper['downloadUrl']}")

        print("\n" + "=" * 120)
        success_count = len([p for p in papers_with_urls if p.get('downloadUrl', '').startswith('http')])
        print(f"Successfully extracted {success_count}/{len(papers_with_urls)} download URLs")
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
    await scrape_tables(case_number)


if __name__ == "__main__":
    asyncio.run(main())
