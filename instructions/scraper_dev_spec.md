# Web Scraper Automation Tool - Development Specification

## Core Requirements

Build a Python CLI tool that scrapes web pages and processes content with configurable transformations.

## Input/Output

**Input:** JSON config file with:
```json
{
  "urlTemplate": "https://example.com/{replace}",
  "selector": ".content",
  "replacements": ["word1", "word2", "word3"],
  "outputFormat": "html|text|innerHTML",
  "outputDir": "./output",
  "assetsPath": "assets/",
  "customHead": "<meta charset='UTF-8'>...",
  "options": {
    "localizeImages": true,
    "deobfuscateEmails": true,
    "downloadIndividual": true,
    "downloadCombined": true,
    "delayMs": 500,
    "retries": 3
  }
}
```

**Output:** 
- Individual HTML/text files per replacement word
- Combined JSON file with all results
- Combined HTML file with all content
- Processing report (txt) with image/email replacements

## Core Functions

### 1. Fetch & Extract
- Replace `{replace}` in URL template with each word
- Fetch HTML with retry logic (exponential backoff)
- Parse with BeautifulSoup/lxml
- Extract element using CSS selector
- Return outerHTML, innerHTML, or text based on format

### 2. Image Localization
- Find all image references: `<img src>`, CSS `background-image`, inline `style` attributes
- Handle URL types: absolute (http/https), protocol-relative (//), absolute path (/), relative (./,../)
- Extract filename from URL path
- Replace with local path: `{assetsPath}/{filename}`
- Add `data-original-src` attribute with original URL
- Return replacement log: `[{original, local, filename, type}]`

### 3. Email Deobfuscation
- Find Cloudflare protected emails: `<span class="__cf_email__" data-cfemail="...">`
- Decode algorithm: 
  - First 2 hex chars = XOR key
  - XOR each subsequent char pair with key
  - Convert to ASCII
- Replace span text and update parent `<a href>` to `mailto:`
- Find direct links: `<a href="/cdn-cgi/l/email-protection#...">`
- Return replacement log: `[{encoded, decoded, element}]`

### 4. HTML Wrapping
- For HTML output, wrap content in complete HTML document
- Insert custom head content if provided
- Default head: charset UTF-8, viewport, title
- Structure: `<!DOCTYPE html><html><head>...</head><body>...</body></html>`

### 5. File Output
- Individual files: `scraped_{word}.html` or `.txt`
- Combined JSON: `scraped_data_combined.json` with all results
- Combined HTML: `scraped_data_combined.html` with wrapped content
- Processing report: `content_processing_report.txt` with replacement details

## Technical Requirements

**Dependencies:**
- `requests` or `httpx` for HTTP
- `beautifulsoup4` + `lxml` for HTML parsing
- `click` or `argparse` for CLI
- Standard library: `json`, `pathlib`, `time`, `re`

**Error Handling:**
- Catch HTTP errors, timeouts, parse failures
- Log errors with word/URL context
- Continue processing on individual failures
- Return success/error counts in summary

**CLI Interface:**
```bash
# Basic usage
scraper --config config.json

# Override options
scraper --config config.json --delay 1000 --no-images

# Output directory
scraper --config config.json --output ./results
```

## Processing Pipeline

1. Load config JSON
2. For each replacement word:
   - Build URL from template
   - Fetch HTML with retry
   - Parse and extract element
   - If HTML format:
     - Apply image localization (if enabled)
     - Apply email deobfuscation (if enabled)
   - Wrap in HTML structure (if HTML format)
   - Save individual file (if enabled)
   - Collect result data
   - Sleep for delay period
3. Generate combined JSON output
4. Generate combined HTML output
5. Generate processing report
6. Print summary statistics

## Output Structure

```
output/
├── scraped_word1.html
├── scraped_word2.html
├── scraped_word3.html
├── scraped_data_combined.json
├── scraped_data_combined.html
└── content_processing_report.txt
```

## Success Criteria

- Successfully scrapes multiple URLs with configurable delays
- Correctly transforms image paths (all URL types)
- Decodes Cloudflare obfuscated emails
- Generates all output formats
- Handles errors gracefully
- Provides progress feedback
- Configurable via JSON + CLI args