"""Simple script to scrape Papers and Exhibits tables from USPTO case viewer."""

import asyncio
import sys
from pyppeteer import launch


async def scrape_tables(case_number: str) -> None:
    """Scrape and print Papers and Exhibits tables from USPTO case viewer.
    
    Args:
        case_number: The USPTO case number to scrape.
    """
    url = f"https://ptacts.uspto.gov/interferences/public-informations/case-viewer/{case_number}"
    
    print(f"Launching browser and navigating to: {url}\n")
    
    # Launch browser
    browser = await launch(
        headless=True,
        args=['--no-sandbox', '--disable-setuid-sandbox']
    )
    
    try:
        page = await browser.newPage()
        await page.setViewport({'width': 1920, 'height': 1080})
        
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
        
        # Extract and print Papers grid
        print("=" * 80)
        print("PAPERS TABLE")
        print("=" * 80)
        
        papers_data = await page.evaluate('''() => {
            const results = [];
            
            // Find the Papers section by ID
            const papersSection = document.getElementById('papersSection');
            if (!papersSection) return results;
            
            // Get all rows from the AG Grid
            const rows = papersSection.querySelectorAll('.ag-row');
            
            // Extract header information
            const headers = [];
            const headerCells = papersSection.querySelectorAll('.ag-header-cell-text');
            headerCells.forEach(cell => headers.push(cell.textContent.trim()));
            
            if (headers.length > 0) {
                results.push(headers);
            }
            
            // Extract row data
            for (let row of rows) {
                const cells = row.querySelectorAll('.ag-cell');
                if (cells.length > 0) {
                    const rowData = [];
                    for (let cell of cells) {
                        rowData.push(cell.textContent.trim());
                    }
                    results.push(rowData);
                }
            }
            
            return results;
        }''')
        
        if papers_data and len(papers_data) > 0:
            for i, row in enumerate(papers_data):
                if i == 0:
                    # Print header
                    print(" | ".join(row))
                    print("-" * 80)
                else:
                    # Print data rows (limit to first 10 for readability)
                    if i <= 10:
                        print(" | ".join(row))
            
            if len(papers_data) > 11:
                print(f"... ({len(papers_data) - 1} total rows)")
        else:
            print("No Papers data found")
        
        print()
        
        # Extract and print Exhibits grid
        print("=" * 80)
        print("EXHIBITS TABLE")
        print("=" * 80)
        
        exhibits_data = await page.evaluate('''() => {
            const results = [];
            
            // Find the Exhibits section by ID
            const exhibitsSection = document.getElementById('exhibitsSection');
            if (!exhibitsSection) return results;
            
            // Get all rows from the AG Grid
            const rows = exhibitsSection.querySelectorAll('.ag-row');
            
            // Extract header information
            const headers = [];
            const headerCells = exhibitsSection.querySelectorAll('.ag-header-cell-text');
            headerCells.forEach(cell => headers.push(cell.textContent.trim()));
            
            if (headers.length > 0) {
                results.push(headers);
            }
            
            // Extract row data
            for (let row of rows) {
                const cells = row.querySelectorAll('.ag-cell');
                if (cells.length > 0) {
                    const rowData = [];
                    for (let cell of cells) {
                        rowData.push(cell.textContent.trim());
                    }
                    results.push(rowData);
                }
            }
            
            return results;
        }''')
        
        if exhibits_data and len(exhibits_data) > 0:
            for i, row in enumerate(exhibits_data):
                if i == 0:
                    # Print header
                    print(" | ".join(row))
                    print("-" * 80)
                else:
                    # Print data rows (limit to first 10 for readability)
                    if i <= 10:
                        print(" | ".join(row))
            
            if len(exhibits_data) > 11:
                print(f"... ({len(exhibits_data) - 1} total rows)")
        else:
            print("No Exhibits data found")
        
        print("\n" + "=" * 80)
        
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
