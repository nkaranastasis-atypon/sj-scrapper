"""Run the SAGE manifest, scrape, reporting, and packaging steps safely."""

import hashlib
import json
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import click
from bs4 import BeautifulSoup

from journal_source import generate_manifest, generate_manifest_from_xml
from package import package_delivery
from scraper import WebScraper


def load_config(config_path: Path) -> Dict[str, Any]:
    """Load and minimally validate the JSON configuration."""
    try:
        with config_path.open(encoding="utf-8") as config_file:
            config = json.load(config_file)
    except (OSError, json.JSONDecodeError) as error:
        raise click.ClickException(f"Configuration step failed: {error}") from error
    if not isinstance(config, dict):
        raise click.ClickException("Configuration step failed: config must be a JSON object")
    return config


def validate_manifest(records: List[Dict[str, Any]]) -> None:
    """Ensure every manifest record has the contract needed by the scraper."""
    required = {
        "journal_code", "msg_url", "eb_url", "template_version",
        "excluded", "excluded_reason",
    }
    if not records:
        raise click.ClickException("Manifest step failed: no journal records were produced")
    codes = []
    for record in records:
        if not required <= record.keys():
            raise click.ClickException("Manifest step failed: record is missing required fields")
        if not record["journal_code"] or not record["msg_url"] or not record["eb_url"]:
            raise click.ClickException("Manifest step failed: record contains an empty required value")
        codes.append(record["journal_code"])
    if len(codes) != len(set(codes)):
        raise click.ClickException("Manifest step failed: duplicate journal codes found")


def write_manifest(path: Path, records: List[Dict[str, Any]]) -> None:
    """Write a validated manifest as readable JSON."""
    path.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")


def _sha256_file(path: Path) -> str:
    """Return a SHA-256 hash for a file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _combined_file_hash(paths: List[Path]) -> str:
    """Hash the content of a set of files in stable order."""
    if not paths:
        return ""
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(path.read_bytes())
        digest.update(b"\n")
    return digest.hexdigest()


def _asset_hashes(output_dir: Path) -> Dict[str, str]:
    """Return a mapping of asset filename -> SHA-256 for all downloaded assets."""
    asset_dir = output_dir / "assets"
    if not asset_dir.exists():
        return {}
    return {
        str(path.relative_to(asset_dir)): _sha256_file(path)
        for path in sorted(asset_dir.rglob("*"))
        if path.is_file()
    }


def build_run_manifest(output_dir: Path, records: List[Dict[str, Any]]) -> Path:
    """Write a run manifest containing HTML and asset hashes for each journal."""
    page_dir = output_dir / "page"
    manifest_records = []
    shared_assets = _asset_hashes(output_dir)

    for record in records:
        journal_code = str(record.get("journal_code", "")).strip().upper()
        page_files = sorted(
            list(page_dir.glob(f"*{journal_code}*.html"))
            if page_dir.exists()
            else []
        )
        manifest_records.append({
            "journal_code": journal_code,
            "msg_url": record.get("msg_url", ""),
            "eb_url": record.get("eb_url", ""),
            "template_version": record.get("template_version", "unknown"),
            "excluded": bool(record.get("excluded", False)),
            "excluded_reason": record.get("excluded_reason", ""),
            "html_sha256": _combined_file_hash(page_files),
            "asset_hashes": shared_assets,
        })

    manifest_path = output_dir / f"run_manifest_{datetime.now():%Y%m%d-%H%M%S}.json"
    manifest_path.write_text(json.dumps(manifest_records, indent=2) + "\n", encoding="utf-8")
    return manifest_path


def changes_since_last_run(previous_manifest: Path, current_manifest: Path) -> List[str]:
    """Return journal codes whose run manifest entries changed since the previous run."""
    with previous_manifest.open(encoding="utf-8") as previous_file:
        previous_records = json.load(previous_file)
    with current_manifest.open(encoding="utf-8") as current_file:
        current_records = json.load(current_file)

    previous_by_code = {record["journal_code"]: record for record in previous_records}
    current_by_code = {record["journal_code"]: record for record in current_records}

    changed = []
    for code in sorted(set(previous_by_code) | set(current_by_code)):
        previous_record = previous_by_code.get(code)
        current_record = current_by_code.get(code)
        if previous_record != current_record:
            changed.append(code)
    return changed


def write_changes_report(output_dir: Path, current_manifest: Path) -> Path:
    """Compare against the most recent previous run and write a human-readable delta file."""
    previous_candidates = sorted(output_dir.glob("run_manifest_*.json"), key=lambda path: path.stat().st_mtime)
    previous = None
    for candidate in reversed(previous_candidates):
        if candidate.resolve() != current_manifest.resolve():
            previous = candidate
            break

    report_path = output_dir / "changes_since_last_run.txt"
    if previous is None:
        report_path.write_text("No previous run manifest was found; no changes could be compared.\n", encoding="utf-8")
        return report_path

    changed = changes_since_last_run(previous, current_manifest)
    if not changed:
        report_path.write_text("No journal changes detected since the last run.\n", encoding="utf-8")
        return report_path

    report_path.write_text(
        "Changed journals since the last run:\n" + "\n".join(f"- {code}" for code in changed) + "\n",
        encoding="utf-8",
    )
    return report_path


def validate_required_section_ids(output_dir: Path) -> None:
    """Ensure only standard submission-guidelines pages include the baseline accordion ids."""
    required_ids = {
        "heading-key-information",
        "heading-publishing-fees-and-open-access",
    }
    page_dir = output_dir / "page"
    if not page_dir.exists():
        return

    for html_path in sorted(page_dir.glob("*.html")):
        if "editorial-board_" in html_path.name:
            continue
        if not "author-instructions_" in html_path.name:
            continue

        soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "lxml")
        has_accordion = bool(
            soup.find(attrs={"class": "bs-accordion"})
            or soup.find(attrs={"data-widget-def": "UX3AccordionWidget"})
            or soup.find(id="accordion")
        )
        if not has_accordion:
            continue

        missing = [section_id for section_id in sorted(required_ids) if not soup.find(id=section_id)]
        if missing:
            raise click.ClickException(
                f"Page validation failed: {html_path.name} is missing required section ids: {', '.join(missing)}"
            )


def validate_package(outputs: Dict[str, Path], allow_empty_pages: bool = False) -> None:
    """Verify package files exist, are readable ZIPs, and contain pages."""
    for name in ("editorial-board", "author-instructions"):
        archive_path = outputs.get(name)
        if not archive_path or not archive_path.exists():
            raise click.ClickException(f"Packaging step failed: missing {name} archive")
        with zipfile.ZipFile(archive_path) as archive:
            if archive.testzip() is not None:
                raise click.ClickException(f"Packaging step failed: corrupt {archive_path.name}")
            if not allow_empty_pages and not any(entry.startswith("page/") for entry in archive.namelist()):
                raise click.ClickException(f"Packaging step failed: {archive_path.name} has no pages")
    summary = outputs.get("summary")
    if not summary or not summary.exists() or not summary.read_text(encoding="utf-8").strip():
        raise click.ClickException("Packaging step failed: delivery summary is missing or empty")


def run_pipeline(
    config_path: Path,
    output_dir: Path,
    sample_dir: Optional[Path],
    xml_path: Optional[Path],
    delivery_month: Optional[str],
    max_failures: int,
) -> Dict[str, Path]:
    """Run all current phases and stop when a sanity check fails."""
    if output_dir.exists() and any(output_dir.iterdir()):
        raise click.ClickException(f"Output step refused: directory is not empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    click.echo("[1/4] Loading configuration")
    config = load_config(config_path)
    config["outputDir"] = str(output_dir)

    click.echo("[2/4] Building and validating journal manifest")
    if xml_path:
        if not xml_path.exists():
            raise click.ClickException(f"Manifest step failed: XML file not found: {xml_path}")
        records = generate_manifest_from_xml(xml_path, config, click.echo)
    else:
        records = generate_manifest(config, click.echo)
    validate_manifest(records)
    manifest_path = output_dir / "journal_manifest.json"
    write_manifest(manifest_path, records)

    active_urls = [
        url
        for record in records
        if not record["excluded"]
        for url in (record["msg_url"], record["eb_url"])
    ]
    if not active_urls:
        raise click.ClickException("Manifest step failed: all journals are excluded")

    click.echo(f"  Journals: {len(records)}; URLs to scrape: {len(active_urls)}")
    click.echo("[3/4] Scraping pages and validating reports")
    scraper = WebScraper(config)
    interrupted = False
    try:
        scraper.run_urls(active_urls, sample_dir, resume=False)
    except KeyboardInterrupt:
        interrupted = True
        click.echo("\nScraping interrupted; preserving checkpoint and packaging completed pages.")
        scraper.write_reports()
    report_path = output_dir / "scraping_report.txt"
    static_links_path = output_dir / "static_sage_links_report.txt"
    if not report_path.exists() or not static_links_path.exists():
        raise click.ClickException("Reporting step failed: expected report files are missing")
    if scraper.report.failed > max_failures:
        raise click.ClickException(
            f"Scraping step failed: {scraper.report.failed} failures exceed allowed {max_failures}"
        )
    if scraper.report.successful == 0:
        raise click.ClickException("Scraping step failed: no pages were generated")

    click.echo("[4/4] Packaging and validating delivery artifacts")
    current_run_manifest = build_run_manifest(output_dir, records)
    validate_required_section_ids(output_dir)
    write_changes_report(output_dir, current_run_manifest)
    outputs = package_delivery(output_dir, manifest_path, delivery_month)
    validate_package(outputs, allow_empty_pages=interrupted)
    if interrupted:
        click.echo(
            f"Pipeline completed with interruption: "
            f"{scraper.report.successful}/{len(active_urls)} pages generated."
        )
    else:
        click.echo(f"Pipeline complete: {scraper.report.successful}/{len(active_urls)} pages generated")
    return outputs


@click.command()
@click.option("--config", "config_path", type=click.Path(exists=True, path_type=Path), default=Path("config.json"))
@click.option("--output", "output_dir", type=click.Path(path_type=Path), default=None)
@click.option("--sample", "sample_dir", type=click.Path(exists=True, path_type=Path), default=Path("sample"))
@click.option("--xml", "xml_path", type=click.Path(exists=True, path_type=Path), default=None,
              help="Use a local MDDB XML instead of SFTP.")
@click.option("--month", "delivery_month", default=None, help="Delivery month in YYYY-MM format.")
@click.option("--max-failures", default=0, type=click.IntRange(min=0),
              help="Maximum allowed page failures before packaging is refused.")
def main(
    config_path: Path,
    output_dir: Optional[Path],
    sample_dir: Path,
    xml_path: Optional[Path],
    delivery_month: Optional[str],
    max_failures: int,
) -> None:
    """Run manifest generation, scraping, reporting, and packaging in order."""
    if output_dir is None:
        output_dir = Path("output") / f"pipeline-{datetime.now():%Y%m%d-%H%M%S}"
    try:
        run_pipeline(config_path, output_dir, sample_dir, xml_path, delivery_month, max_failures)
    except click.ClickException:
        raise
    except Exception as error:
        raise click.ClickException(f"Pipeline stopped unexpectedly: {error}") from error


if __name__ == "__main__":
    main()