"""Build the SAGE MSG/Editorial Board manifest from the MDDB SFTP feed."""

import json
import re
import xml.etree.ElementTree as ElementTree
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

import click
import paramiko
import yaml


MDDB_FILENAME_PATTERN = re.compile(r"^atypon-sage-mddb_(.+)\.xml$")
MDDB_TIMESTAMP_PATTERNS = ("%d-%m-%Y_%H-%M-%S", "%Y%m%d_%H%M%S")
JOURNALS_BASE_URL = "https://journals.sagepub.com"


class JournalSourceError(RuntimeError):
    """Raised when the configured MDDB source cannot produce a manifest."""


def newest_mddb_filename(filenames: Iterable[str]) -> str:
    """Return the chronologically newest timestamped MDDB XML filename."""
    matches = [filename for filename in filenames if MDDB_FILENAME_PATTERN.match(filename)]
    if not matches:
        raise JournalSourceError("No atypon-sage-mddb_<timestamp>.xml files found on SFTP")

    def sort_key(filename: str) -> tuple[int, datetime | str]:
        timestamp = MDDB_FILENAME_PATTERN.match(filename).group(1)
        for pattern in MDDB_TIMESTAMP_PATTERNS:
            try:
                return (1, datetime.strptime(timestamp, pattern))
            except ValueError:
                continue
        return (0, timestamp)

    return max(matches, key=sort_key)


def parse_alpha_codes(xml_content: bytes) -> List[str]:
    """Extract distinct alpha codes from an MDDB XML document."""
    try:
        root = ElementTree.fromstring(xml_content)
    except ElementTree.ParseError as error:
        raise JournalSourceError(f"Invalid MDDB XML: {error}") from error

    codes = {
        (element.text or "").strip().upper()
        for element in root.iter()
        if element.tag.rsplit("}", 1)[-1] == "alpha_code" and (element.text or "").strip()
    }
    if not codes:
        raise JournalSourceError("MDDB XML does not contain any <alpha_code> values")
    return sorted(codes)


def build_manifest(codes: Sequence[str], excluded_codes: Iterable[str]) -> List[Dict[str, Any]]:
    """Create scraper-ready MSG and Editorial Board URLs for MDDB codes."""
    excluded = {code.strip().upper() for code in excluded_codes}
    return [
        {
            "journal_code": code,
            "msg_url": f"{JOURNALS_BASE_URL}/author-instructions/{code}",
            "eb_url": f"{JOURNALS_BASE_URL}/editorial-board/{code}",
            "template_version": "unknown",
            "excluded": code in excluded,
            "excluded_reason": "corporate-fed" if code in excluded else "",
        }
        for code in sorted({code.strip().upper() for code in codes if code.strip()})
    ]


def load_excluded_codes(exception_path: Path) -> set[str]:
    """Load corporate-fed journal codes from the static exception file."""
    try:
        with exception_path.open(encoding="utf-8") as exception_file:
            exceptions = yaml.safe_load(exception_file) or {}
    except OSError as error:
        raise JournalSourceError(f"Unable to read exception file: {error}") from error

    entries = exceptions.get("corporate_fed", [])
    return {
        str(entry.get("code", "")).strip().upper()
        for entry in entries
        if entry.get("code") and str(entry.get("code")).strip().upper() != "TBD"
    }


def fetch_latest_mddb_xml(source_config: Dict[str, Any]) -> bytes:
    """Download the newest configured MDDB XML from SFTP."""
    host = source_config.get("host")
    username = source_config.get("username")
    remote_dir = source_config.get("remoteDir")
    if not all([host, username, remote_dir]):
        raise JournalSourceError("journalSource requires host, username, and remoteDir")

    connect_options: Dict[str, Any] = {"hostname": host, "username": username}
    if source_config.get("password"):
        connect_options["password"] = source_config["password"]
    if source_config.get("keyFilename"):
        connect_options["key_filename"] = source_config["keyFilename"]
    if source_config.get("port"):
        connect_options["port"] = source_config["port"]
    connect_options["timeout"] = source_config.get("connectTimeout", 30)
    connect_options["banner_timeout"] = source_config.get("bannerTimeout", 30)
    connect_options["auth_timeout"] = source_config.get("authTimeout", 30)

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(**connect_options)
        transport = client.get_transport()
        if transport:
            transport.settimeout(source_config.get("readTimeout", 120))
        with client.open_sftp() as sftp:
            filename = newest_mddb_filename(sftp.listdir(remote_dir))
            with sftp.open(f"{remote_dir.rstrip('/')}/{filename}", "rb") as remote_file:
                return remote_file.read()
    except (OSError, paramiko.SSHException) as error:
        raise JournalSourceError(f"Unable to download MDDB XML: {error}") from error
    finally:
        client.close()


def generate_manifest_from_xml(xml_path: Path, config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Build a manifest from a local MDDB XML file for offline rehearsals."""
    codes = parse_alpha_codes(xml_path.read_bytes())
    exception_path = Path(config.get("exceptionsPath", "known_exceptions.yaml"))
    return build_manifest(codes, load_excluded_codes(exception_path))


def generate_manifest(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Download, parse, and turn the latest MDDB XML into manifest records."""
    source_config = config.get("journalSource", {})
    codes = parse_alpha_codes(fetch_latest_mddb_xml(source_config))
    exception_path = Path(config.get("exceptionsPath", "known_exceptions.yaml"))
    return build_manifest(codes, load_excluded_codes(exception_path))


@click.command()
@click.option("--config", "config_path", type=click.Path(exists=True), default="config.json")
@click.option("--output", "output_path", type=click.Path(), default=None)
def main(config_path: str, output_path: str | None) -> None:
    """Create a journal manifest from the newest MDDB SFTP export."""
    with open(config_path, encoding="utf-8") as config_file:
        config = json.load(config_file)

    manifest = generate_manifest(config)
    destination = Path(output_path or config.get("journalSource", {}).get("manifestPath", "journal_manifest.json"))
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    click.echo(f"Wrote {len(manifest)} journals to {destination}")


if __name__ == "__main__":
    main()