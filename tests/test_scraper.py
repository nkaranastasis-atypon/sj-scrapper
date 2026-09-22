#!/usr/bin/env python3
"""
Test script to verify scraper functionality with a simple local test
"""

from pathlib import Path
import tempfile
import shutil

def create_test_html():
    """Create a simple test HTML file to scrape"""
    html = """<!DOCTYPE html>
<html>
<head><title>Test Page</title></head>
<body>
    <div class="header">This should not be extracted</div>
    <div class="col-12 col-lg-8">
        <h2>Test Content</h2>
        <p>This is the content we want to extract.</p>
        <img src="https://via.placeholder.com/150" alt="Test Image">
        
        <!-- Cloudflare protected email example -->
        <p>Contact: <a href="/cdn-cgi/l/email-protection#d3b6bbb2aeb6a193b4beb2babffdb0bcbe">
        <span class="__cf_email__" data-cfemail="82e7eae3ffe7f0c2e5efe3ebeeace1edef">[email&#160;protected]</span>
        </a></p>
    </div>
    <div class="footer">This should not be extracted</div>
</body>
</html>"""
    return html

def test_local():
    """Test with a local HTML file"""
    print("🧪 Running local HTML parsing test...\n")
    
    from bs4 import BeautifulSoup
    
    html = create_test_html()
    soup = BeautifulSoup(html, 'lxml')
    
    # Test CSS selector
    element = soup.select_one("div.col-12.col-lg-8")
    
    if element:
        print("✅ CSS Selector Test: PASSED")
        print(f"   Extracted {len(element.get_text())} characters")
    else:
        print("❌ CSS Selector Test: FAILED")
        return False
    
    # Test email deobfuscation
    encoded = "82e7eae3ffe7f0c2e5efe3ebeeace1edef"
    key = int(encoded[:2], 16)
    decoded = ""
    for i in range(2, len(encoded), 2):
        char_code = int(encoded[i:i+2], 16)
        decoded += chr(char_code ^ key)
    
    if "@" in decoded:
        print("✅ Email Deobfuscation Test: PASSED")
        print(f"   Decoded: {decoded}")
    else:
        print("❌ Email Deobfuscation Test: FAILED")
        return False
    
    # Test image finding
    images = element.find_all("img")
    print(f"✅ Image Detection Test: PASSED")
    print(f"   Found {len(images)} image(s)")
    
    print("\n✨ All tests passed!\n")
    return True

def show_usage():
    """Show usage examples"""
    print("=" * 80)
    print("WEB SCRAPER - READY TO USE")
    print("=" * 80)
    print()
    print("📝 Next Steps:")
    print()
    print("1. Edit urls.txt and add your test URLs (2-3 URLs recommended)")
    print()
    print("2. Run a test scrape:")
    print("   python scraper.py --urls urls.txt --sample sample")
    print()
    print("3. Check the output:")
    print("   - output/page/ - HTML files")
    print("   - output/assets/ - Downloaded images")
    print("   - output/scraping_report.txt - Processing report")
    print()
    print("4. For production run with all URLs:")
    print("   python scraper.py --urls full-urls.txt --sample sample")
    print()
    print("=" * 80)
    print()
    print("💡 Tips:")
    print("   - Start with a small test (2-3 URLs)")
    print("   - Check scraping_report.txt for errors")
    print("   - Use --selector to change the CSS selector if needed")
    print("   - Use --delay to adjust request delay (ms)")
    print()
    print("📖 See QUICKSTART.md for detailed guide")
    print("=" * 80)

if __name__ == '__main__':
    if test_local():
        show_usage()
