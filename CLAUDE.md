# Patent Document Downloader

## Project Overview

This project provides a Python script to download patent documents from the US Patent Office website. The application uses Pyppeteer to manage a headless Chromium browser to interact with the USPTO's Angular-based patent case viewer application.

### Example Target URL
```
https://ptacts.uspto.gov/interferences/public-informations/case-viewer/106048
```

This page displays all documents associated with a specific patent case number.

## Technical Stack

- **Python Version**: 3.12
- **Package Manager**: uv
- **Browser Automation**: Pyppeteer (headless Chromium)
- **Target**: Angular-based USPTO patent case viewer

## Project Structure

```
.
├── CLAUDE.md                 # This file - project documentation
├── README.md                 # User-facing documentation
├── pyproject.toml            # Project configuration and dependencies
├── uv.lock                   # Locked dependencies
├── src/
│   └── patent_downloader/
│       ├── __init__.py
│       ├── main.py           # Entry point
│       ├── scraper.py        # Pyppeteer browser automation
│       ├── parser.py         # Document parsing logic
│       └── downloader.py     # File download handling
├── tests/
│   ├── __init__.py
│   ├── test_scraper.py
│   ├── test_parser.py
│   └── test_downloader.py
└── .gitignore
```

## Development Setup

### Prerequisites

1. Python 3.12 installed
2. uv package manager installed:
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

### Initial Setup

```bash
# Create virtual environment and install dependencies
uv sync

# Install Chromium for Pyppeteer (first run)
uv run python -m pyppeteer install
```

### Running the Application

```bash
# Run the main script
uv run python -m src.patent_downloader.main <case_number>

# Example
uv run python -m src.patent_downloader.main 106048
```

## Python Best Practices

### Code Style

- **Formatter**: ruff format
- **Linter**: ruff check
- **Type Checker**: mypy
- **Line Length**: 100 characters max
- **Import Sorting**: ruff (compatible with isort)

### Code Quality Standards

1. **Type Hints**: Use type hints for all function signatures
   ```python
   def download_document(case_number: str, output_dir: Path) -> list[Path]:
       ...
   ```

2. **Docstrings**: Use Google-style docstrings for all public functions and classes
   ```python
   def scrape_case_documents(case_number: str) -> list[dict[str, str]]:
       """Scrape all documents for a given patent case number.
       
       Args:
           case_number: The USPTO case number to scrape.
           
       Returns:
           A list of document metadata dictionaries containing URLs and titles.
           
       Raises:
           ValueError: If case_number is invalid.
           NetworkError: If the USPTO website is unreachable.
       """
   ```

3. **Error Handling**: Use specific exceptions and proper error messages
   ```python
   try:
       await page.goto(url)
   except Exception as e:
       raise NetworkError(f"Failed to load case {case_number}: {e}") from e
   ```

4. **Logging**: Use structured logging instead of print statements
   ```python
   import logging
   
   logger = logging.getLogger(__name__)
   logger.info("Downloading document", extra={"case_number": case_number})
   ```

### Testing

```bash
# Run tests with pytest
uv run pytest

# Run with coverage
uv run pytest --cov=src --cov-report=html

# Run specific test file
uv run pytest tests/test_scraper.py
```

### Code Quality Checks

```bash
# Format code
uv run ruff format .

# Lint code
uv run ruff check . --fix

# Type check
uv run mypy src/

# Run all checks before committing
uv run ruff format . && uv run ruff check . && uv run mypy src/ && uv run pytest
```

## Dependencies Management

### Adding Dependencies

```bash
# Add a runtime dependency
uv add <package-name>

# Add a development dependency
uv add --dev <package-name>

# Example: Add a new library
uv add httpx
uv add --dev pytest-asyncio
```

### Updating Dependencies

```bash
# Update all dependencies
uv lock --upgrade

# Update specific package
uv lock --upgrade-package <package-name>
```

## Configuration Files

### pyproject.toml

The `pyproject.toml` file should include:

- Project metadata (name, version, description, authors)
- Dependencies and dev-dependencies
- Build system configuration
- Tool configurations (ruff, mypy, pytest)

### Recommended Tools Configuration

```toml
[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "B", "C4", "UP"]
ignore = []

[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true
warn_unused_configs = true

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = "test_*.py"
python_functions = "test_*"
asyncio_mode = "auto"
```

## Git Workflow

### .gitignore Essentials

```
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
.venv/

# uv
.uv/

# Testing
.pytest_cache/
.coverage
htmlcov/

# Type checking
.mypy_cache/

# IDEs
.vscode/
.idea/
*.swp

# Project specific
downloads/
*.pdf
*.log

# Pyppeteer
.local-chromium/
```

## Architecture Considerations

### Async/Await Pattern

Since Pyppeteer is async-based, use async/await throughout:

```python
import asyncio
from pyppeteer import launch

async def main():
    browser = await launch(headless=True)
    page = await browser.newPage()
    # ... scraping logic
    await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
```

### Error Handling for Browser Automation

- Handle timeouts gracefully
- Implement retry logic for network failures
- Clean up browser resources in finally blocks
- Use context managers when possible

### Performance Considerations

- Reuse browser instances when downloading multiple cases
- Implement concurrent downloads with asyncio.gather()
- Add rate limiting to avoid overwhelming the USPTO server
- Cache results when appropriate

## Security Considerations

- Validate all input case numbers
- Sanitize filenames before saving
- Don't expose sensitive credentials if authentication is added
- Respect robots.txt and terms of service
- Implement user-agent headers appropriately

## Future Enhancements

- [ ] CLI with argparse or typer for better UX
- [ ] Configuration file support (YAML/TOML)
- [ ] Progress bars for downloads (tqdm)
- [ ] Database storage for metadata
- [ ] Batch processing support
- [ ] Resume capability for interrupted downloads
- [ ] PDF validation after download

## Troubleshooting

### Chromium Installation Issues

If Pyppeteer can't find Chromium:
```bash
uv run python -m pyppeteer install
```

### Timeout Errors

Increase timeout values in scraper configuration:
```python
await page.goto(url, {'timeout': 60000})  # 60 seconds
```

## Contributing

1. Create a feature branch from main
2. Make changes following the code style guide
3. Add tests for new functionality
4. Run all quality checks
5. Submit a pull request

## License

[Specify your license here]

## Support

For issues or questions, please [specify contact method or issue tracker].
