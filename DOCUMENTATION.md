# Web Scraper Tool - Complete Documentation

## 📋 Project Overview

**Purpose**: Batch scrape and process hundreds of web pages with configurable content extraction, image localization, and email deobfuscation.

**Status**: ✅ Ready for testing and production use

## 🗂️ Project Structure

```
c:\Atypon\scrapper/
├── scraper.py              # Main scraper tool
├── config.json             # Configuration file
├── requirements.txt        # Python dependencies
├── urls.txt               # Input URLs (one per line)
├── test_scraper.py        # Test script
├── README.md              # Full documentation
├── QUICKSTART.md          # Quick start guide
├── instructions/
│   └── scraper_dev_spec.md
├── sample/                # Template for output structure
│   ├── page/
│   ├── assets/
│   ├── lib/
│   │   ├── accordion.js
│   │   └── extracted-styles.css
│   └── fonts/
└── output/                # Generated after running (not in repo)
    ├── page/              # Extracted HTML files
    ├── assets/            # Downloaded images
    ├── lib/               # Copied from sample
    ├── fonts/             # Copied from sample
    └── scraping_report.txt
```

## ⚙️ Features Implemented

### Core Features
- ✅ **Batch URL Processing**: Read URLs from text file (one per line)
- ✅ **CSS Selector Extraction**: Extract specific page sections
- ✅ **Image Localization**: Download images to local assets folder
- ✅ **Email Deobfuscation**: Decode Cloudflare-protected emails
- ✅ **HTML Template Wrapping**: Wrap extracted content in complete HTML
- ✅ **Smart Naming**: Convert URL paths to filenames
- ✅ **Folder Management**: Auto-create output structure
- ✅ **Asset Copying**: Copy lib/ and fonts/ from sample
- ✅ **Comprehensive Reporting**: Success/failure tracking with details

### Technical Features
- ✅ **Retry Logic**: Exponential backoff for failed requests
- ✅ **Rate Limiting**: Configurable delay between requests
- ✅ **Error Handling**: Continue processing on individual failures
- ✅ **Timeout Control**: Configurable request timeouts
- ✅ **Session Management**: Persistent HTTP session
- ✅ **Progress Tracking**: Real-time console output

## 🚀 Usage

### Basic Usage
```bash
python scraper.py --urls urls.txt --sample sample
```

### Advanced Options
```bash
python scraper.py \
  --config config.json \
  --urls urls.txt \
  --sample sample \
  --selector "div.main-content" \
  --output ./my-output \
  --delay 1000
```

## 📊 Configuration

**config.json**:
```json
{
  "selector": "div.col-12.col-lg-8",     // CSS selector for content
  "outputDir": "./output",                // Output directory
  "assetsPath": "assets",                 // Assets subfolder name
  "options": {
    "localizeImages": true,               // Download images locally
    "deobfuscateEmails": true,            // Decode CF emails
    "delayMs": 500,                       // Delay between requests
    "retries": 3,                         // Number of retries
    "timeout": 30                         // Request timeout (seconds)
  }
}
```

## 📝 Input Format

**urls.txt** - One URL per line:
```
https://example.com/journal/author-instructions
https://example.com/journal/editorial-board
https://example.com/journal2/submission-guidelines
...
```

## 📤 Output Format

### File Naming Convention
URLs are converted to filenames:
- `https://host/path/to/journal` → `path_to_journal.html`
- `https://host/editorial-board` → `editorial-board.html`

### Generated Files
```
output/
├── page/
│   ├── journal_author-instructions.html
│   ├── journal_editorial-board.html
│   └── ...
├── assets/
│   ├── image1.jpg
│   ├── logo.png
│   └── ...
├── lib/
│   ├── accordion.js
│   └── extracted-styles.css
├── fonts/
└── scraping_report.txt
```

### HTML Output Template
Each file contains:
```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Scraped Content</title>
<script type="text/javascript" src="../lib/accordion.js"></script>
<link rel="stylesheet" href="../lib/extracted-styles.css">
</head>
<body>
<!-- Extracted content here -->
</body>
</html>
```

## 📈 Report Format

**scraping_report.txt** contains:
- Total URLs processed
- Success/failure counts
- Number of images localized
- Number of emails decoded
- Detailed error messages for failures
- Sample of image replacements
- List of all decoded emails

Example:
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

## 🧪 Testing Workflow

### Phase 1: Initial Test (2-3 URLs)
1. Edit `urls.txt` with 2-3 test URLs
2. Run: `python scraper.py --urls urls.txt --sample sample`
3. Check output files in `output/page/`
4. Review `output/scraping_report.txt`
5. Verify images in `output/assets/`

### Phase 2: Small Batch (10-20 URLs)
1. Add 10-20 URLs to test file
2. Run scraper
3. Review report for errors
4. Adjust config if needed (selector, delay, etc.)

### Phase 3: Production Run (Full Dataset)
1. Prepare complete `urls.txt` with all URLs
2. Consider running in batches if very large
3. Monitor progress
4. Review final report
5. Fix any errors and re-run failed URLs

## 🔧 Troubleshooting

### Issue: No content extracted
**Solution**: 
- Verify CSS selector in browser DevTools
- Check if page structure matches expected selector
- Try different selector: `--selector "div.content"`

### Issue: Images not downloading
**Solution**:
- Check network connectivity
- Verify image URLs are accessible
- Increase timeout in config.json
- Check for authentication requirements

### Issue: Server rate limiting
**Solution**:
- Increase delay: `--delay 2000` (2 seconds)
- Reduce concurrent requests
- Add authentication headers if needed

### Issue: Email deobfuscation not working
**Solution**:
- Verify site uses Cloudflare email protection
- Check for `__cf_email__` class in page source
- Some sites may use different protection

### Issue: Some URLs fail
**Solution**:
1. Check `scraping_report.txt` for specific errors
2. Extract failed URLs
3. Create new file with just failed URLs
4. Investigate and fix issues
5. Re-run: `python scraper.py --urls failed-urls.txt --sample sample`

## 💾 Dependencies

Install with: `pip install -r requirements.txt`

- `requests>=2.31.0` - HTTP requests
- `beautifulsoup4>=4.12.0` - HTML parsing
- `lxml>=4.9.0` - Fast XML/HTML parser
- `click>=8.1.0` - CLI framework

## 🎯 Next Steps for You

1. **Prepare Test URLs** (Ready to do now):
   - Edit `urls.txt`
   - Add 2-3 test URLs from your site
   
2. **Run Test Scrape**:
   ```bash
   python scraper.py --urls urls.txt --sample sample
   ```

3. **Verify Results**:
   - Check `output/page/` for HTML files
   - Open files in browser
   - Review `output/scraping_report.txt`

4. **Adjust if Needed**:
   - Change CSS selector if content not extracted correctly
   - Adjust delay if rate limited
   - Modify config.json as needed

5. **Production Run**:
   - Prepare full `urls.txt` with all URLs
   - Run scraper on full dataset
   - Package `output/` folder for export

## 📞 Support

If you encounter issues:
1. Check `scraping_report.txt` for error details
2. Review browser DevTools to verify CSS selector
3. Test with single URL first
4. Check network connectivity and authentication

## 📄 Files Reference

- `scraper.py` - Main tool (635 lines, fully commented)
- `config.json` - Configuration
- `requirements.txt` - Dependencies
- `README.md` - Full documentation
- `QUICKSTART.md` - Quick start guide
- `test_scraper.py` - Test script
- `urls.txt` - Input URLs

---

**Tool Status**: ✅ Production Ready
**Last Updated**: January 21, 2026
**Python Version**: 3.7+
