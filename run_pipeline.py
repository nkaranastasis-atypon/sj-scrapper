"""Run the SAGE manifest, scrape, reporting, and packaging steps safely."""

import json
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import click

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
    blocked_path = output_dir / "blocked_links_report.txt"
    if not report_path.exists() or not blocked_path.exists():
        raise click.ClickException("Reporting step failed: expected report files are missing")
    if scraper.report.failed > max_failures:
        raise click.ClickException(
            f"Scraping step failed: {scraper.report.failed} failures exceed allowed {max_failures}"
        )
    if scraper.report.successful == 0:
        raise click.ClickException("Scraping step failed: no pages were generated")

    click.echo("[4/4] Packaging and validating delivery artifacts")
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