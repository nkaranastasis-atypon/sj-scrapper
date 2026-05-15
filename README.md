# Web Scraper Tool

Python-based web scraping tool for extracting and processing content from multiple URLs.

## Features

- ✅ Batch URL processing from text file
- ✅ **Two scraping modes**: HTML section extraction or direct image download
- ✅ CSS selector-based content extraction
- ✅ Image localization (downloads to assets folder)
- ✅ Cloudflare email deobfuscation
- ✅ HTML template wrapping
- ✅ Automatic filename generation from URL path
- ✅ Folder structure management
- ✅ Comprehensive error reporting
- ✅ Retry logic with exponential backoff

## Installation

```bash
pip install -r requirements.txt
```

## Quick Start

1. **Prepare URLs file** (`urls.txt`):
   ```
   https://example.com/path/to/page1
   https://example.com/path/to/page2
   ```

2. **Run the scraper**:
   ```bash
   python scraper.py --urls urls.txt --sample sample
   ```

## Usage

### Basic Command

```bash
python scraper.py --urls urls.txt --sample sample
```

### Advanced Options (HTML mode)

```bash
python scraper.py \
  --config config.json \
  --urls urls.txt \
  --sample sample \
  --selector "div.content" \
  --output ./my-output \
  --delay 1000
```

### Image mode — download a specific image from each page

Use `--mode image` with a CSS selector that targets the `<img>` element directly (or a container that holds it). The scraper saves one image file per URL, named after the last path segment of the page URL.

```bash
python scraper.py \
  --urls cover_urls.txt \
  --mode image \
  --selector "div.cover-box img" \
  --output ./cover-images
```

Images are saved to `output/assets/`. No HTML files or `lib/`/`fonts/` assets are produced in this mode.

### Command Line Options

| Option | Short | Description |
|---|---|---|
| `--config` | `-c` | Path to config JSON file (default: `config.json`) |
| `--urls` | `-u` | Path to URLs text file (**required**) |
| `--sample` | `-s` | Path to sample directory with `lib/` and `fonts/` folders |
| `--mode` | | `html` (default) or `image` — overrides config |
| `--selector` | | CSS selector — overrides config |
| `--output` | `-o` | Output directory — overrides config |
| `--delay` | | Delay between requests in ms — overrides config |
| `--no-resume` | | Ignore checkpoint file and start from scratch |

## Configuration

Edit `config.json` to customize settings:

```json
{
  "mode": "html",
  "selector": "div.col-12.col-lg-8",
  "outputDir": "./output",
  "assetsPath": "assets",
  "options": {
    "localizeImages": true,
    "deobfuscateEmails": true,
    "delayMs": 500,
    "retries": 3,
    "timeout": 30
  }
}
```

| Field | Values | Description |
|---|---|---|
| `mode` | `html` / `image` | Scraping mode (default: `html`) |
| `selector` | any CSS selector | Element to extract; in image mode targets the `<img>` or its container |
| `outputDir` | path | Root output folder |
| `assetsPath` | folder name | Subfolder inside `outputDir` for downloaded images |

## Output Structure

**HTML mode** (`--mode html`, default):
```
output/
├── page/
│   ├── path_to_page1.html
│   ├── path_to_page2.html
│   └── ...
├── assets/         # downloaded images referenced by the HTML
├── lib/
│   ├── accordion.js
│   └── extracted-styles.css
├── fonts/
└── scraping_report.txt
```

**Image mode** (`--mode image`):
```
output/
├── assets/
│   ├── journal1.jpg    # named after last page URL segment
│   ├── journal2.png
│   └── ...
└── scraping_report.txt
```

## File Naming Convention

URLs are converted to filenames by:
1. Extracting the path portion
2. Replacing `/` with `_`
3. Adding `.html` extension

Examples:
- `https://host/path/to/journal` → `path_to_journal.html`
- `https://host/editorial-board` → `editorial-board.html`

## Report

The tool generates `scraping_report.txt` with:
- Total URLs processed
- Success/failure counts
- Image localization details
- Email deobfuscation details
- Detailed error messages for failed URLs

## Testing

1. Create a test URLs file with 2-3 URLs
2. Run the scraper on the test set
3. Verify output in the `output/` directory
4. Review `scraping_report.txt` for any issues

## Troubleshooting

**No content extracted:**
- Verify the CSS selector matches your target content
- Check the selector in browser DevTools first

**Images not downloading:**
- Check network connectivity
- Verify image URLs are accessible
- Review timeout settings in config

**Email deobfuscation not working:**
- Ensure the site uses Cloudflare email protection
- Check for `__cf_email__` class in source HTML

## License

MIT
