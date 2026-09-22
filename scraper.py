#!/usr/bin/env python3
"""
Web Scraper Tool - Extracts and processes web content with image localization and email deobfuscation
"""

import requests
import json
import time
import re
import os
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import click
import yaml
from link_audit import audit_html, journal_code_from_url, write_report


class ScraperReport:
    """Tracks scraping statistics and errors"""
    
    def __init__(self):
        self._lock = threading.Lock()
        self.total = 0
        self.successful = 0
        self.failed = 0
        self.errors = []
        self.skipped = []
        self.selector_matches = []
        self.images_processed = []
        self.emails_decoded = []
    
    def add_success(self, url: str, filename: str):
        with self._lock:
            self.successful += 1

    def add_skipped(self, url: str, reason: str):
        with self._lock:
            self.skipped.append({"url": url, "reason": reason})
        
    def add_error(self, url: str, error: str):
        with self._lock:
            self.failed += 1
            self.errors.append({"url": url, "error": error})
    
    def add_image(self, original: str, local: str, filename: str):
        with self._lock:
            self.images_processed.append({
                "original": original,
                "local": local,
                "filename": filename
            })

    def add_selector_match(self, selector: str, url: str):
        with self._lock:
            self.selector_matches.append({
                "selector": selector,
                "url": url,
            })
    
    def add_email(self, encoded: str, decoded: str):
        with self._lock:
            self.emails_decoded.append({
                "encoded": encoded,
                "decoded": decoded
            })
    
    def generate_report(self) -> str:
        """Generate text report"""
        lines = [
            "=" * 80,
            "WEB SCRAPER PROCESSING REPORT",
            "=" * 80,
            f"\nTotal URLs processed: {self.total}",
            f"Successful: {self.successful}",
            f"Failed: {self.failed}",
            f"\nImages localized: {len(self.images_processed)}",
            f"Emails decoded: {len(self.emails_decoded)}",
        ]
        
        if self.errors:
            lines.append("\n" + "=" * 80)
            lines.append("ERRORS")
            lines.append("=" * 80)
            for err in self.errors:
                lines.append(f"\nURL: {err['url']}")
                lines.append(f"Error: {err['error']}")

        if self.skipped:
            lines.append("\n" + "=" * 80)
            lines.append("Excluded - corporate-fed")
            lines.append("=" * 80)
            for entry in self.skipped:
                lines.append(f"\nURL: {entry['url']}")
                lines.append(f"Reason: {entry['reason']}")

        if self.selector_matches:
            lines.append("\n" + "=" * 80)
            lines.append("Selector matches")
            lines.append("=" * 80)
            for match in self.selector_matches:
                lines.append(f"\nURL: {match['url']}")
                lines.append(f"Selector: {match['selector']}")
        
        if self.images_processed:
            lines.append("\n" + "=" * 80)
            lines.append("IMAGE REPLACEMENTS (Sample - first 10)")
            lines.append("=" * 80)
            for img in self.images_processed[:10]:
                lines.append(f"\nOriginal: {img['original']}")
                lines.append(f"Local: {img['local']}")
        
        if self.emails_decoded:
            lines.append("\n" + "=" * 80)
            lines.append("EMAIL DEOBFUSCATIONS")
            lines.append("=" * 80)
            for email in self.emails_decoded:
                lines.append(f"\nEncoded: {email['encoded']}")
                lines.append(f"Decoded: {email['decoded']}")
        
        lines.append("\n" + "=" * 80)
        return "\n".join(lines)


class WebScraper:
    """Main scraper class"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.selector = config.get("selector", "div.col-12.col-lg-8")
        configured_selectors = config.get("selectors") or []
        if isinstance(configured_selectors, str):
            configured_selectors = [configured_selectors]
        self.selectors = [
            selector for selector in [*configured_selectors, self.selector]
            if selector and selector != ""
        ]
        self.selectors = list(dict.fromkeys(self.selectors))
        self.last_selector_match = None
        self.user_agent = config.get(
            "userAgent",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        self.output_dir = Path(config.get("outputDir", "./output"))
        self.assets_path = config.get("assetsPath", "assets")
        self.options = config.get("options", {})
        self.mode = config.get("mode", "html")
        self.exceptions_path = Path(config.get("exceptionsPath", "known_exceptions.yaml"))
        self._corporate_fed_codes = self._load_corporate_fed_codes()
        self._old_template_image_codes = self._load_old_template_image_codes()
        self.report = ScraperReport()
        self.blocked_links = {}
        self._blocked_links_lock = threading.Lock()
        self._thread_local = threading.local()
        self.session = requests.Session()
        self._configure_session(self.session)

    def _load_corporate_fed_codes(self) -> set[str]:
        """Return corporate-fed journal codes from the configured exceptions file."""
        return self._load_exception_codes("corporate_fed")

    def _load_old_template_image_codes(self) -> set[str]:
        """Return journal codes that require extra page-level image discovery."""
        return self._load_exception_codes("old_template_images")

    def _load_exception_codes(self, category: str) -> set[str]:
        """Load a category of journal codes from the exceptions YAML file."""
        try:
            with self.exceptions_path.open("r", encoding="utf-8") as exception_file:
                exceptions = yaml.safe_load(exception_file) or {}
        except OSError:
            return set()

        entries = exceptions.get(category, [])
        return {
            str(entry.get("code", "")).strip().upper()
            for entry in entries
            if entry.get("code") and str(entry.get("code")).strip().upper() != "TBD"
        }

    def _journal_code_from_url(self, url: str) -> str:
        """Extract the journal code from a Sage URL."""
        try:
            return urlparse(url).path.rstrip("/").rsplit("/", 1)[-1].upper()
        except Exception:
            return ""

    def is_corporate_fed_url(self, url: str) -> bool:
        """Return True when the journal code in the URL is excluded as corporate-fed."""
        return self._journal_code_from_url(url) in self._corporate_fed_codes

    def is_old_template_image_journal(self, url: str) -> bool:
        """Return True when the journal needs page-level pb-assets discovery."""
        return self._journal_code_from_url(url) in self._old_template_image_codes

    def _configure_session(self, session: requests.Session) -> requests.Session:
        session.headers.update({'User-Agent': self.user_agent})
        return session

    def _get_session(self) -> requests.Session:
        """Return the main session or a session owned by this worker thread."""
        if threading.current_thread() is threading.main_thread():
            return self.session
        if not hasattr(self._thread_local, "session"):
            self._thread_local.session = self._configure_session(requests.Session())
        return self._thread_local.session
    
    def fetch_url(self, url: str) -> Optional[str]:
        """Fetch URL with retry logic"""
        retries = self.options.get("retries", 3)
        timeout = self.options.get("timeout", 30)
        delay = self.options.get("delayMs", 500) / 1000
        
        for attempt in range(retries):
            try:
                time.sleep(delay)
                response = self._get_session().get(url, timeout=timeout)
                response.raise_for_status()
                return response.text
            except requests.exceptions.RequestException as e:
                if attempt == retries - 1:
                    raise
                time.sleep(delay * (attempt + 1))  # Exponential backoff
        
        return None
    
    def extract_content(self, html: str, url: str) -> Optional[BeautifulSoup]:
        """Extract content using the configured selector list, falling back in order."""
        soup = BeautifulSoup(html, 'lxml')
        self.last_selector_match = None

        for selector in self.selectors:
            element = soup.select_one(selector)
            if element:
                self.last_selector_match = selector
                self.report.add_selector_match(selector, url)
                return element

        return None
    
    def deobfuscate_email(self, encoded: str) -> str:
        """Decode Cloudflare-protected email"""
        try:
            # Remove any whitespace
            encoded = encoded.strip()
            
            # First 2 chars are the XOR key
            key = int(encoded[:2], 16)
            
            # Decode the rest
            decoded = ""
            for i in range(2, len(encoded), 2):
                char_code = int(encoded[i:i+2], 16)
                decoded += chr(char_code ^ key)
            
            return decoded
        except Exception:
            return ""
    
    def transform_accordion(self, element: BeautifulSoup) -> None:
        """Transform accordion structure to match expected format"""
        # Find all ed-board-name divs and transform them
        board_names = element.find_all("div", class_="ed-board-name")
        
        for idx, name_div in enumerate(board_names):
            sequence = name_div.get("data-sequence", str(idx + 1))
            
            # Get the parent soup to create new tags
            soup = name_div.find_parent()
            while soup.parent is not None:
                soup = soup.parent
            
            # Create the button element
            button = BeautifulSoup('<button></button>', 'lxml').button
            button["class"] = (name_div.get("class", []) if isinstance(name_div.get("class"), list) 
                             else [name_div.get("class")]) + ["bs-accordion__control"]
            button["data-sequence"] = sequence
            button["type"] = "button"
            button["data-toggle"] = "collapse"
            button["data-target"] = f"#id{idx}"
            button["aria-expanded"] = "true"
            button["aria-controls"] = f"id{idx}"
            
            # Move the text content to button
            button.string = name_div.get_text()
            
            # Add arrow icon
            icon = BeautifulSoup('<i></i>', 'lxml').i
            icon["aria-hidden"] = "true"
            icon["class"] = ["icon-arrow_down"]
            button.append(icon)
            
            # Create h3 wrapper
            h3 = BeautifulSoup('<h3></h3>', 'lxml').h3
            h3.append(button)
            
            # Replace the div with h3
            name_div.replace_with(h3)
            
            # Find and update the corresponding table wrapper
            # It should be the next sibling
            wrapper = h3.find_next_sibling("div", class_="ed-board-table-wrapper")
            if wrapper:
                # Add collapse classes and id
                current_classes = wrapper.get("class", [])
                if not isinstance(current_classes, list):
                    current_classes = [current_classes]
                wrapper["class"] = current_classes + ["collapse", "bs-accordion__content", "show"]
                wrapper["id"] = f"id{idx}"
        
        # Transform expand-all button if present
        expand_button = element.find("button", class_="expand-all")
        if expand_button:
            expand_button["aria-expanded"] = "true"
    
    def process_emails(self, element: BeautifulSoup) -> None:
        """Find and deobfuscate Cloudflare-protected emails"""
        if not self.options.get("deobfuscateEmails", True):
            return
        
        # Find all __cf_email__ spans
        cf_spans = element.find_all("span", class_="__cf_email__")
        
        for span in cf_spans:
            encoded = span.get("data-cfemail", "")
            if encoded:
                decoded = self.deobfuscate_email(encoded)
                if decoded:
                    # Replace span with decoded email
                    span.string = decoded
                    span.attrs = {}  # Remove all attributes
                    
                    # Update parent <a> tag if exists
                    parent = span.parent
                    if parent and parent.name == "a":
                        parent['href'] = f"mailto:{decoded}"
                    
                    self.report.add_email(encoded, decoded)
        
        # Find direct cdn-cgi links
        cgi_links = element.find_all("a", href=re.compile(r'/cdn-cgi/l/email-protection#'))
        
        for link in cgi_links:
            href = link.get('href', '')
            match = re.search(r'#([a-f0-9]+)', href)
            if match:
                encoded = match.group(1)
                decoded = self.deobfuscate_email(encoded)
                if decoded:
                    link['href'] = f"mailto:{decoded}"
                    if not link.string or 'email protection' in link.string.lower():
                        link.string = decoded
                    self.report.add_email(encoded, decoded)
    
    def download_image(self, img_url: str, base_url: str, assets_dir: Path) -> Optional[str]:
        """Download image and return local filename"""
        try:
            # Resolve relative URLs
            full_url = urljoin(base_url, img_url)
            
            # Extract filename from URL
            parsed = urlparse(full_url)
            path_parts = parsed.path.split('/')
            filename = path_parts[-1] if path_parts[-1] else 'image.jpg'
            
            # Remove query parameters from filename
            filename = filename.split('?')[0]
            
            # Ensure filename is valid
            filename = re.sub(r'[^\w\-.]', '_', filename)
            
            # Download image
            response = self._get_session().get(full_url, timeout=10)
            response.raise_for_status()
            
            # Save to assets directory
            assets_dir.mkdir(parents=True, exist_ok=True)
            file_path = assets_dir / filename
            
            with open(file_path, 'wb') as f:
                f.write(response.content)
            
            return filename
        except Exception as e:
            print(f"Warning: Failed to download image {img_url}: {e}")
            return None
    
    def _discover_page_level_images(self, base_url: str, assets_dir: Path, page_html: Optional[str] = None) -> set[str]:
        """Return page-level /pb-assets/cmscontent image URLs referenced anywhere on the page."""
        discovered: set[str] = set()
        if not page_html:
            return discovered

        page_soup = BeautifulSoup(page_html, 'lxml')
        for tag in page_soup.find_all(attrs={"src": True}):
            src = tag.get("src", "")
            if src and "/pb-assets/cmscontent/" in src:
                discovered.add(src)
        for tag in page_soup.find_all(attrs={"href": True}):
            href = tag.get("href", "")
            if href and "/pb-assets/cmscontent/" in href:
                discovered.add(href)
        return discovered

    def process_images(self, element: BeautifulSoup, base_url: str, assets_dir: Path, page_html: Optional[str] = None) -> None:
        """Find and localize images, including page-level old-template /pb-assets references."""
        if not self.options.get("localizeImages", True):
            return

        seen: set[str] = set()

        # Process <img> tags
        for img in element.find_all("img"):
            src = img.get("src", "")
            if src and not src.startswith("data:"):
                if src in seen:
                    continue
                seen.add(src)
                filename = self.download_image(src, base_url, assets_dir)
                if filename:
                    local_path = f"../{self.assets_path}/{filename}"
                    img['data-original-src'] = src
                    img['src'] = local_path
                    self.report.add_image(src, local_path, filename)

        # Process background-image in style attributes
        elements_with_style = element.find_all(style=re.compile(r'background-image'))

        for elem in elements_with_style:
            style = elem.get('style', '')
            url_match = re.search(r'url\(["\']?([^"\')]+)["\']?\)', style)
            if url_match:
                img_url = url_match.group(1)
                if img_url not in seen and not img_url.startswith("data:"):
                    seen.add(img_url)
                    filename = self.download_image(img_url, base_url, assets_dir)
                    if filename:
                        local_path = f"../{self.assets_path}/{filename}"
                        new_style = style.replace(img_url, local_path)
                        elem['style'] = new_style
                        elem['data-original-style'] = style
                        self.report.add_image(img_url, local_path, filename)

        if page_html and (self.is_old_template_image_journal(base_url) or "pb-assets/cmscontent/" in page_html):
            for src in self._discover_page_level_images(base_url, assets_dir, page_html):
                if src in seen:
                    continue
                seen.add(src)
                filename = self.download_image(src, base_url, assets_dir)
                if filename:
                    self.report.add_image(src, f"../{self.assets_path}/{filename}", filename)
    
    def wrap_in_template(self, content: BeautifulSoup) -> str:
        """Wrap content in HTML template"""
        template = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Scraped Content</title>
<script type="text/javascript" src="../lib/accordion.js"></script>
<link rel="stylesheet" href="../lib/extracted-styles.css">
</head>
<body>
{str(content)}
</body>
</html>"""
        return template
    
    def url_to_filename(self, url: str) -> str:
        """Convert URL to filename based on path"""
        parsed = urlparse(url)
        path = parsed.path.strip('/')
        
        # Replace / with _
        filename = path.replace('/', '_')
        
        # Remove invalid characters
        filename = re.sub(r'[^\w\-]', '_', filename)
        
        # Add .html extension
        if not filename.endswith('.html'):
            filename += '.html'
        
        return filename
    
    def _process_url_image(self, url: str) -> bool:
        """Process a single URL in image mode - locate a specific <img> and save it as a file"""
        try:
            print(f"Processing: {url}")

            # Fetch page HTML
            html = self.fetch_url(url)
            if not html:
                raise Exception("Failed to fetch URL")

            # Locate the <img> element via CSS selector
            soup = BeautifulSoup(html, 'lxml')
            element = soup.select_one(self.selector)
            if not element:
                raise Exception(f"No element found matching selector: {self.selector}")

            # If the selector matched a container, look for the first <img> inside
            if element.name != 'img':
                element = element.find('img')
                if not element:
                    raise Exception(f"No <img> tag found within element matching selector: {self.selector}")

            # Prefer lazy-load attributes over src (which may be a placeholder data: URI)
            src = ''
            for attr in ('data-src', 'data-lazy-src', 'data-original', 'data-img-src'):
                candidate = element.get(attr, '')
                if candidate and not candidate.startswith('data:'):
                    src = candidate
                    break
            if not src:
                candidate = element.get('src', '')
                if candidate and not candidate.startswith('data:'):
                    src = candidate
            if not src:
                raise Exception("Matched <img> has no usable src (only data: URI placeholders found)")

            # Resolve to absolute URL
            full_img_url = urljoin(url, src)

            # Build filename: last path segment of the PAGE URL + image extension
            page_slug = urlparse(url).path.rstrip('/').rsplit('/', 1)[-1]
            page_slug = re.sub(r'[^\w\-]', '_', page_slug) or 'image'

            img_ext = Path(urlparse(full_img_url).path).suffix

            # Download the image
            assets_dir = self.output_dir / self.assets_path
            assets_dir.mkdir(parents=True, exist_ok=True)

            response = self._get_session().get(full_img_url, timeout=self.options.get('timeout', 30))
            response.raise_for_status()

            # If the URL had no extension, derive it from Content-Type
            if not img_ext:
                content_type = response.headers.get('Content-Type', '')
                ext_map = {
                    'image/jpeg': '.jpg', 'image/jpg': '.jpg',
                    'image/png': '.png', 'image/gif': '.gif',
                    'image/webp': '.webp', 'image/svg+xml': '.svg',
                }
                img_ext = ext_map.get(content_type.split(';')[0].strip(), '.jpg')

            filename = f"{page_slug}{img_ext}"
            file_path = assets_dir / filename

            with open(file_path, 'wb') as f:
                f.write(response.content)

            self.report.add_image(full_img_url, str(file_path), filename)
            self.report.add_success(url, filename)
            print(f"  ✓ Saved image: {file_path}")
            return True

        except Exception as e:
            error_msg = str(e)
            self.report.add_error(url, error_msg)
            print(f"  ✗ Error: {error_msg}")
            return False

    def process_url(self, url: str) -> bool:
        """Process a single URL"""
        if self.mode == 'image':
            return self._process_url_image(url)
        try:
            print(f"Processing: {url}")

            if self.is_corporate_fed_url(url):
                journal_code = urlparse(url).path.rstrip("/").rsplit("/", 1)[-1].upper()
                self.report.add_skipped(url, "corporate-fed journal exclusion")
                self.report.add_success(url, f"skipped:{journal_code}")
                print(f"  ✓ Skipped {journal_code}: corporate-fed journal exclusion")
                return True

            # Fetch HTML
            html = self.fetch_url(url)
            if not html:
                raise Exception("Failed to fetch URL")
            
            # Extract content
            element = self.extract_content(html, url)
            if not element:
                raise Exception(f"No element found matching selector: {self.selector}")
            
            # Create output directories
            page_dir = self.output_dir / "page"
            assets_dir = self.output_dir / self.assets_path
            page_dir.mkdir(parents=True, exist_ok=True)
            
            # Process images
            self.process_images(element, url, assets_dir, page_html=html)
            
            # Process emails
            self.process_emails(element)
            
            # Transform accordion structure
            try:
                self.transform_accordion(element)
            except Exception as e:
                print(f"  Warning: Accordion transformation failed: {e}")
                # Continue without transformation
            
            # Wrap in template
            output_html = self.wrap_in_template(element)
            
            # Generate filename
            filename = self.url_to_filename(url)
            output_path = page_dir / filename
            
            # Write file
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(output_html)

            blocked_links = audit_html(output_html, url)
            if blocked_links:
                journal_code = journal_code_from_url(url)
                with self._blocked_links_lock:
                    self.blocked_links.setdefault(journal_code, [])
                    self.blocked_links[journal_code].extend(
                        (url, blocked_url) for blocked_url in blocked_links
                    )
            
            self.report.add_success(url, filename)
            print(f"  ✓ Saved to: {output_path}")
            return True
            
        except Exception as e:
            error_msg = str(e)
            self.report.add_error(url, error_msg)
            print(f"  ✗ Error: {error_msg}")
            return False
    
    def copy_sample_assets(self, sample_dir: Path):
        """Copy lib, fonts, and assets folders from sample directory"""
        for folder in ['lib', 'fonts', 'assets']:
            src = sample_dir / folder
            dst = self.output_dir / folder
            
            if src.exists():
                if folder == 'assets':
                    # For assets, copy files but don't overwrite the folder
                    # since we'll be adding downloaded images to it
                    dst.mkdir(parents=True, exist_ok=True)
                    for item in src.iterdir():
                        if item.is_file():
                            shutil.copy2(item, dst / item.name)
                    print(f"Copied {folder}/ files to output directory")
                else:
                    # For lib and fonts, replace the entire folder
                    if dst.exists():
                        shutil.rmtree(dst)
                    shutil.copytree(src, dst)
                    print(f"Copied {folder}/ to output directory")
    
    def run(self, urls_file: Path, sample_dir: Optional[Path] = None, resume: bool = True):
        """Main execution method"""
        with open(urls_file, 'r', encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
        self.run_urls(urls, sample_dir, resume)

    def run_urls(self, urls: List[str], sample_dir: Optional[Path] = None, resume: bool = True):
        """Process a supplied list of URLs."""
        
        # Check for checkpoint file to resume
        checkpoint_file = self.output_dir / '.scraper_checkpoint.txt'
        processed_urls = set()
        
        if resume and checkpoint_file.exists():
            with open(checkpoint_file, 'r', encoding='utf-8') as f:
                processed_urls = set(line.strip() for line in f if line.strip())
            print(f"\n📋 Found checkpoint file - {len(processed_urls)} URLs already processed")
            urls = [url for url in urls if url not in processed_urls]
        
        self.report.total = len(urls) + len(processed_urls)
        
        print(f"\n{'='*80}")
        print(f"Starting scraper - {len(urls)} URLs to process")
        if processed_urls:
            print(f"Resuming from checkpoint - {len(processed_urls)} already completed")
        print(f"{'='*80}\n")
        
        # Ensure output directory exists before any URL is processed
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Copy sample assets if provided (not needed in image mode)
        if self.mode != 'image' and sample_dir and sample_dir.exists():
            self.copy_sample_assets(sample_dir)
        
        max_workers = max(1, int(self.options.get("maxWorkers", 8)))
        if max_workers == 1:
            results = ((url, self.process_url(url)) for url in urls)
            self._record_results(results, checkpoint_file, len(urls))
        else:
            print(f"Using {max_workers} parallel workers")
            executor = ThreadPoolExecutor(max_workers=max_workers)
            futures = {}
            try:
                futures = {executor.submit(self.process_url, url): url for url in urls}
                results = ((url, future.result()) for future, url in (
                    (future, futures[future]) for future in as_completed(futures)
                ))
                self._record_results(results, checkpoint_file, len(urls))
            except KeyboardInterrupt:
                print("\nInterrupt received; cancelling queued scraping tasks.")
                for future in futures:
                    future.cancel()
                executor.shutdown(wait=True, cancel_futures=True)
                raise
            else:
                executor.shutdown(wait=True)
        
        self.write_reports()

        # Clean up checkpoint file on successful completion
        if checkpoint_file.exists():
            checkpoint_file.unlink()
            print(f"✓ Checkpoint file removed (all URLs processed)")

    def _record_results(self, results, checkpoint_file: Path, total: int):
        """Persist completed URLs and progress from sequential or parallel work."""
        completed = 0
        for url, _ in results:
            completed += 1
            with open(checkpoint_file, 'a', encoding='utf-8') as f:
                f.write(f"{url}\n")
            if completed % 100 == 0:
                print(f"\n{'='*80}")
                print(f"📊 PROGRESS CHECKPOINT: {completed}/{total} URLs processed")
                print(f"   Success: {self.report.successful} | Failed: {self.report.failed}")
                print(f"   Images: {len(self.report.images_processed)} | Emails: {len(self.report.emails_decoded)}")
                print(f"{'='*80}\n")
                self._save_intermediate_report(completed, total)

    def write_reports(self):
        """Write the current scraping and blocked-link reports."""
        report_text = self.report.generate_report()
        report_path = self.output_dir / "scraping_report.txt"
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report_text)

        blocked_links_path = self.output_dir / "blocked_links_report.txt"
        write_report(blocked_links_path, self.blocked_links)
        
        print(f"\n{report_text}")
        print(f"\nReport saved to: {report_path}")
        print(f"Blocked links report saved to: {blocked_links_path}")
    
    def _save_intermediate_report(self, current: int, total: int):
        """Save intermediate progress report"""
        report_path = self.output_dir / f"progress_report_{current}_of_{total}.txt"
        
        lines = [
            "=" * 80,
            f"INTERMEDIATE PROGRESS REPORT - {current}/{total} URLs",
            "=" * 80,
            f"\nProcessed so far: {current}",
            f"Successful: {self.report.successful}",
            f"Failed: {self.report.failed}",
            f"Images localized: {len(self.report.images_processed)}",
            f"Emails decoded: {len(self.report.emails_decoded)}",
            "\n" + "=" * 80
        ]
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines))
        
        print(f"   💾 Intermediate report saved: {report_path.name}")


@click.command()
@click.option('--config', '-c', type=click.Path(exists=True), default='config.json',
              help='Path to config JSON file')
@click.option('--urls', '-u', type=click.Path(exists=True),
              help='Path to text file with URLs (one per line)')
@click.option('--manifest', type=click.Path(exists=True),
              help='Path to journal manifest JSON produced by journal_source.py')
@click.option('--sample', '-s', type=click.Path(exists=True),
              help='Path to sample directory with lib/ and fonts/ folders')
@click.option('--selector', type=str,
              help='CSS selector (overrides config)')
@click.option('--output', '-o', type=click.Path(),
              help='Output directory (overrides config)')
@click.option('--delay', type=int,
              help='Delay between requests in ms (overrides config)')
@click.option('--no-resume', is_flag=True,
              help='Start from beginning, ignoring checkpoint file')
@click.option('--mode', type=click.Choice(['html', 'image']), default=None,
              help='Scraping mode: html (extract page section, default) or image (download a specific image element)')
def main(config, urls, manifest, sample, selector, output, delay, no_resume, mode):
    """Web scraper tool - Extract and process web pages"""
    
    # Load config
    with open(config, 'r') as f:
        config_data = json.load(f)
    
    # Override with command line options
    if selector:
        config_data['selector'] = selector
    if output:
        config_data['outputDir'] = output
    if delay:
        config_data['options']['delayMs'] = delay
    if mode:
        config_data['mode'] = mode
    
    # Create and run scraper
    scraper = WebScraper(config_data)
    sample_path = Path(sample) if sample else Path('sample')
    if bool(urls) == bool(manifest):
        raise click.UsageError('Provide exactly one of --urls or --manifest.')
    if urls:
        scraper.run(Path(urls), sample_path, resume=not no_resume)
        return

    with open(manifest, encoding='utf-8') as manifest_file:
        records = json.load(manifest_file)
    manifest_urls = [
        url
        for record in records
        if not record.get('excluded', False)
        for url in (record.get('msg_url'), record.get('eb_url'))
        if url
    ]
    scraper.run_urls(manifest_urls, sample_path, resume=not no_resume)


if __name__ == '__main__':
    main()
