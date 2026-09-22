# Quick Start Guide

## ⚡ For First-Time Testing

### Step 1: Prepare Your URLs File

Edit `urls.txt` and add 2-3 test URLs:

```
https://your-site.com/journal/author-instructions
https://your-site.com/journal/editorial-board
```

### Step 2: Run Test Scrape

```bash
python scraper.py --urls urls.txt --sample sample
```

This will:
- Process all URLs in `urls.txt`
- Extract content matching `div.col-12.col-lg-8`
- Download images to `output/assets/`
- Copy `lib/` and `fonts/` from `sample/`
- Generate files in `output/page/`
- Create `output/scraping_report.txt`

### Step 3: Verify Output

Check the `output/` directory:
```
output/
├── page/
│   ├── journal_author-instructions.html
│   └── journal_editorial-board.html
├── assets/
│   └── (downloaded images)
├── lib/
│   ├── accordion.js
│   └── extracted-styles.css
├── fonts/
└── scraping_report.txt
```

Open one of the HTML files in a browser to verify the output looks correct.

### Step 4: Review Report

Open `output/scraping_report.txt` to see:
- How many URLs succeeded/failed
- Which images were downloaded
- Which emails were decoded
- Any errors that occurred

---

## 🚀 For Production Run

### Step 1: Prepare Full URLs List

Create or replace `urls.txt` with all your URLs (hundreds):

```
https://site.com/journal1/author-instructions
https://site.com/journal1/editorial-board
https://site.com/journal2/author-instructions
https://site.com/journal2/editorial-board
...
```

### Step 2: Customize Settings (Optional)

Edit `config/config.json` if needed:

```json
{
  "selector": "div.col-12.col-lg-8",
  "outputDir": "./output",
  "assetsPath": "assets",
  "options": {
    "localizeImages": true,
    "deobfuscateEmails": true,
    "delayMs": 500,        // Increase if server rate-limits you
    "retries": 3,
    "timeout": 30
  }
}
```

### Step 3: Run Production Scrape

```bash
python scraper.py --urls urls.txt --sample sample
```

For a different CSS selector:
```bash
python scraper.py --urls urls.txt --sample sample --selector "div.main-content"
```

### Step 4: Review and Package

1. Check `scraping_report.txt` for errors
2. If errors occurred, fix issues and re-run failed URLs
3. Verify a few random HTML files
4. The `output/` folder is ready to export to 3rd party

---

## 🔧 Troubleshooting

### Wrong content extracted
- Check CSS selector in browser DevTools
- Use `--selector` to override: `--selector "div.content"`

### Images not downloading
- Check network access to image URLs
- Increase timeout: edit `config/config.json` → `"timeout": 60`

### Rate limited by server
- Increase delay: `--delay 2000` (2 seconds between requests)

### Want to re-run specific failed URLs
1. Check `scraping_report.txt` for failed URLs
2. Create new `failed-urls.txt` with just those URLs
3. Run: `python scraper.py --urls failed-urls.txt --sample sample`

---

## 📊 Understanding the Report

```
================================================================================
WEB SCRAPER PROCESSING REPORT
================================================================================

Total URLs processed: 150
Successful: 148
Failed: 2

Images localized: 487
Emails decoded: 23

================================================================================
ERRORS
================================================================================

URL: https://site.com/bad-page
Error: No element found matching selector: div.col-12.col-lg-8
```

This tells you:
- 148 out of 150 pages scraped successfully
- 487 images were downloaded and localized
- 23 Cloudflare-protected emails were decoded
- 2 pages failed (with specific error messages)

---

## 💡 Pro Tips

1. **Test first**: Always run with 2-3 URLs before full batch
2. **Monitor progress**: Watch console output for errors in real-time
3. **Clean output**: Delete `output/` folder before each run to start fresh
4. **Backup URLs**: Keep a copy of your original `urls.txt`
5. **Incremental runs**: You can process URLs in batches if needed
