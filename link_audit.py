"""Audit generated HTML for links to journals.sagepub.com."""

from collections import defaultdict
from pathlib import Path
from typing import DefaultDict, Iterable, List, Mapping
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


TARGET_DOMAIN = "journals.sagepub.com"


def audit_html(html: str, base_url: str, target_domain: str = TARGET_DOMAIN) -> List[str]:
    """Return unique absolute target-domain links found in generated HTML."""
    soup = BeautifulSoup(html, "lxml")
    links = []
    seen = set()

    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        if not href or href.startswith(("#", "mailto:")):
            continue

        resolved = urljoin(base_url, href)
        parsed = urlparse(resolved)
        if parsed.scheme not in ("http", "https"):
            continue
        if parsed.hostname != target_domain:
            continue
        if resolved not in seen:
            seen.add(resolved)
            links.append(resolved)

    return links


def journal_code_from_url(url: str) -> str:
    """Extract the final path segment used as the journal code."""
    path = urlparse(url).path.rstrip("/")
    return path.rsplit("/", 1)[-1] or "unknown"


def format_report(entries: Mapping[str, Iterable[tuple[str, str]]]) -> str:
    """Format audit entries grouped by journal code."""
    lines = [
        "BLOCKED LINKS REPORT",
        "=" * 80,
    ]
    total = sum(1 for journal_entries in entries.values() for _ in journal_entries)
    lines.append(f"Total journal links found: {total}")

    for journal_code in sorted(entries):
        lines.extend(["", f"Journal: {journal_code}", "-" * 80])
        for source_url, blocked_url in entries[journal_code]:
            lines.append(f"Source: {source_url}")
            lines.append(f"Link:   {blocked_url}")

    lines.append("")
    return "\n".join(lines)


def write_report(report_path: Path, entries: Mapping[str, Iterable[tuple[str, str]]]) -> None:
    """Write the grouped blocked-link report."""
    report_path.write_text(format_report(entries), encoding="utf-8")