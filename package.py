"""Package scraper output into delivery archives and a Jira-ready summary."""

import json
import zipfile
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from link_audit import TARGET_DOMAIN

TOOL_VERSION = "0.2.0"


PAGE_GROUPS = {
    "editorial-board": "editorial-board_{}.zip",
    "author-instructions": "submission-guidelines_{}.zip",
}
SHARED_DIRECTORIES = ("assets", "lib", "fonts")


def load_manifest(manifest_path: Optional[Path]) -> List[Dict[str, Any]]:
    """Load a journal manifest when one is available."""
    if not manifest_path or not manifest_path.exists():
        return []
    with manifest_path.open(encoding="utf-8") as manifest_file:
        records = json.load(manifest_file)
    if not isinstance(records, list):
        raise ValueError("Manifest must contain a JSON list")
    return records


def matching_page_files(page_dir: Path, prefix: str) -> List[Path]:
    """Return page files for one delivery type in stable order."""
    return sorted(page_dir.glob(f"{prefix}_*.html")) if page_dir.exists() else []


def archive_paths(
    output_dir: Path,
    page_files: Iterable[Path],
    archive_path: Path,
    include_assets: bool = True,
) -> None:
    """Create one archive with selected pages and delivery resources."""
    directories = SHARED_DIRECTORIES if include_assets else ("lib", "fonts")
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for page_file in page_files:
            archive.write(page_file, Path("page") / page_file.name)
        for directory_name in directories:
            directory = output_dir / directory_name
            if not directory.exists():
                continue
            for path in sorted(directory.rglob("*")):
                if path.is_file():
                    archive.write(path, Path(directory_name) / path.relative_to(directory))


def blocked_link_count(report_path: Path) -> int:
    """Count static SAGE links in the Phase 3 report."""
    if not report_path.exists():
        return 0
    return sum(1 for line in report_path.read_text(encoding="utf-8").splitlines() if line.startswith("Link:   "))


def load_asset_manifest(asset_manifest_path: Path) -> Dict[str, List[str]]:
    """Load the journal-code -> asset filenames mapping produced by the scraper."""
    if not asset_manifest_path.exists():
        return {}
    with asset_manifest_path.open(encoding="utf-8") as manifest_file:
        return json.load(manifest_file)


def summary_text(
    manifest: List[Dict[str, Any]],
    page_counts: Dict[str, int],
    blocked_count: int,
    blocked_report_exists: bool,
    month: str,
    change_report_path: Optional[Path] = None,
    asset_manifest: Optional[Dict[str, List[str]]] = None,
) -> str:
    """Build the delivery summary in a stable, paste-ready format."""
    excluded = [record for record in manifest if record.get("excluded")]
    corporate_fed = [
        record for record in excluded
        if record.get("excluded_reason") == "corporate-fed"
    ]
    change_lines = [
        "- Phase 4 was skipped; no changes report was generated.",
    ]
    if change_report_path and change_report_path.exists():
        change_lines = [
            line.rstrip()
            for line in change_report_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    lines = [
        "# SAGE MSG / Editorial Board Delivery Summary",
        "",
        f"Tool version: {TOOL_VERSION}",
        f"Delivery month: {month}",
        "",
        "## Package counts",
        "",
        f"- Editorial Board pages: {page_counts['editorial-board']}",
        f"- Submission Guidelines pages: {page_counts['author-instructions']}",
        f"- Total generated pages: {sum(page_counts.values())}",
        f"- Excluded journals: {len(excluded)}",
        "",
        "## Excluded - corporate-fed",
        "",
    ]
    if corporate_fed:
        lines.extend(
            f"- {record.get('journal_code', 'unknown')}"
            for record in corporate_fed
        )
    else:
        lines.append("- None recorded")

    lines.extend([
        "",
        "## Static SAGE links",
        "",
        f"- Static links found on {TARGET_DOMAIN}: {blocked_count}",
        f"- Report generated: {'yes' if blocked_report_exists else 'no'}",
        "",
        "## Assets by journal",
        "",
    ])
    asset_manifest = asset_manifest or {}
    total_assets = sum(len(filenames) for filenames in asset_manifest.values())
    lines.append(f"- Total assets downloaded: {total_assets}")
    lines.append(f"- Journals with assets: {len(asset_manifest)}")
    if asset_manifest:
        lines.extend(
            f"  - {journal_code}: {len(filenames)}"
            for journal_code, filenames in sorted(asset_manifest.items())
        )

    lines.extend([
        "",
        "## Changes since last run",
        "",
    ])
    lines.extend(change_lines)
    lines.append("")
    return "\n".join(lines)


def package_delivery(
    output_dir: Path,
    manifest_path: Optional[Path] = None,
    delivery_month: Optional[str] = None,
) -> Dict[str, Path]:
    """Create both delivery archives and the summary file."""
    month = delivery_month or date.today().strftime("%Y-%m")
    if len(month) != 7 or month[4] != "-":
        raise ValueError("delivery_month must use YYYY-MM format")

    page_dir = output_dir / "page"
    page_counts = {
        prefix: len(matching_page_files(page_dir, prefix))
        for prefix in PAGE_GROUPS
    }
    outputs: Dict[str, Path] = {}
    change_report = output_dir / "changes_since_last_run.txt"
    for prefix, filename_template in PAGE_GROUPS.items():
        archive_path = output_dir / filename_template.format(month)
        page_files = matching_page_files(page_dir, prefix)
        archive_paths(
            output_dir,
            page_files,
            archive_path,
            include_assets=prefix == "author-instructions",
        )
        with zipfile.ZipFile(archive_path, "a", compression=zipfile.ZIP_DEFLATED) as archive:
            if change_report.exists():
                archive.write(change_report, change_report.name)
        outputs[prefix] = archive_path

    static_links_report = output_dir / "static_sage_links_report.txt"
    asset_manifest = load_asset_manifest(output_dir / "asset_manifest.json")
    summary_path = output_dir / "DELIVERY_SUMMARY.md"
    summary_path.write_text(
        summary_text(
            load_manifest(manifest_path),
            page_counts,
            blocked_link_count(static_links_report),
            static_links_report.exists(),
            month,
            change_report,
            asset_manifest,
        ),
        encoding="utf-8",
    )
    outputs["summary"] = summary_path
    return outputs


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Package SAGE scraper output")
    parser.add_argument("--output", default="output", type=Path)
    parser.add_argument("--manifest", default=None, type=Path)
    parser.add_argument("--month", default=None, help="Delivery month in YYYY-MM format")
    args = parser.parse_args()
    for path in package_delivery(args.output, args.manifest, args.month).values():
        print(path)