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
- ✅ SFTP MDDB journal manifest generation from `<alpha_code>` values
- ✅ Static corporate-fed exception list (`ABH`, `APB`, `JCX`)
- ✅ Static SAGE-link audit for generated HTML
- ✅ Delivery archives and Jira-ready summary generation

## Installation

```bash
pip install -r requirements.txt
copy config\config.example.json config\config.json
```

## Quick Start

1. **Prepare a URL list** (`urls.txt`) for a manual or small test run:
   ```
   https://example.com/path/to/page1
   https://example.com/path/to/page2
   ```

2. **Run the scraper**:
   ```bash
   python scraper.py --urls urls.txt --sample sample
   ```

For a recurring SAGE export, generate the journal manifest from the newest
MDDB XML on SFTP, then scrape the non-excluded journals:

```bash
python journal_source.py --config config\config.json
python scraper.py --manifest journal_manifest.json --sample sample
python package.py --output output --manifest journal_manifest.json
```

The SFTP username and private key path belong in the local, ignored
`config\config.json`; start from `config\config.example.json` and never commit credentials
or private-key paths.
The source expects files named `atypon-sage-mddb_<date>_<time>.xml` and
extracts each journal's three-letter `<alpha_code>`. The key path is passed to
Paramiko as `key_filename`.

For a guarded end-to-end run, use `run_pipeline.py`. It creates a fresh output
directory, validates the manifest, runs the scrape, checks both reports, and
validates the delivery archives before completing:

```bash
python run_pipeline.py --config config\config.json --sample sample
```

To compare this run with a prior pipeline output, provide the prior output
directory. The current run still writes to a new, empty output directory:

```bash
python run_pipeline.py \
  --config config\config.json \
  --previous-run output/pipeline-20260922-153355 \
  --sample sample
```

For a safe rehearsal with the recorded XML snippet, skip SFTP with `--xml`:

```bash
python run_pipeline.py \
  --config config\config.json \
  --xml "instructions/atypon-sage-mddb_01-01-2026_21-00-03 - snippet.xml" \
  --sample sample \
  --max-failures 2
```

The pipeline stops before packaging if any sanity check fails. Use
`--max-failures` only when a test run intentionally includes known extraction
failures; the default is zero.

## Usage

### Basic Command

```bash
python scraper.py --urls urls.txt --sample sample
```

### Advanced Options (HTML mode)

```bash
python scraper.py \
  --config config/config.json \
  --urls urls.txt \
  --sample sample \
  --selector "div.content" \
  --output ./my-output \
  --delay 1000
```

### Manifest input

`--manifest` is an alternative to `--urls`. It accepts the JSON file created
by `journal_source.py`, skips records marked `excluded`, and processes both the
`msg_url` and `eb_url` for each remaining journal. `--urls` remains available
for ad hoc runs and tests; provide exactly one of the two options.

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
| `--config` | `-c` | Path to config JSON file (default: `config/config.json`) |
| `--urls` | `-u` | Path to URLs text file; mutually exclusive with `--manifest` |
| `--manifest` | | Path to JSON journal manifest; mutually exclusive with `--urls` |
| `--sample` | `-s` | Path to sample directory with `lib/` and `fonts/` folders |
| `--mode` | | `html` (default) or `image` — overrides config |
| `--selector` | | CSS selector — overrides config |
| `--output` | `-o` | Output directory — overrides config |
| `--delay` | | Delay between requests in ms — overrides config |
| `--no-resume` | | Ignore checkpoint file and start from scratch |

`run_pipeline.py` also accepts `--previous-run`, which points to a completed
pipeline output directory containing a `run_manifest_*.json` file.

## Configuration

Edit `config/config.json` to customize settings:

```json
{
  "mode": "html",
  "selector": "div.col-12.col-lg-8",
  "outputDir": "./output",
  "assetsPath": "assets",
  "exceptionsPath": "known_exceptions.yaml",
  "journalSource": {
    "host": "sftp2.literatumonline.com",
    "port": 22,
    "username": "",
    "keyFilename": "",
    "remoteDir": "/sage/mddb/live/received",
    "manifestPath": "./journal_manifest.json"
  },
  "options": {
    "localizeImages": true,
    "deobfuscateEmails": true,
    "delayMs": 500,
    "maxWorkers": 1,
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
| `exceptionsPath` | path | YAML file containing static journal exceptions |
| `journalSource` | object | SFTP connection and manifest output settings |
| `options.maxWorkers` | positive integer | Parallel page workers; defaults to `8`, while `1` keeps sequential behavior |

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

HTML runs also create `static_sage_links_report.txt`, grouped by journal code.
After scraping, `package.py` adds the two delivery archives and
`DELIVERY_SUMMARY.md` to the output directory.

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

`static_sage_links_report.txt` lists links in generated HTML that resolve to
`journals.sagepub.com`, so they can be reviewed before delivery.

## Delivery packaging

Run the packager after a completed HTML scrape:

```bash
python package.py --output output --manifest journal_manifest.json
```

It creates `editorial-board_YYYY-MM.zip`,
`submission-guidelines_YYYY-MM.zip`, and `DELIVERY_SUMMARY.md`. Use
`--month YYYY-MM` when producing a delivery for a specific month.

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
