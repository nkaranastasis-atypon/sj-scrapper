import json
import zipfile

import pytest

from run_pipeline import validate_manifest, validate_package


def test_validate_manifest_rejects_duplicate_codes():
    record = {
        "journal_code": "AJS",
        "msg_url": "msg",
        "eb_url": "eb",
        "template_version": "unknown",
        "excluded": False,
        "excluded_reason": "",
    }

    with pytest.raises(Exception, match="duplicate journal codes"):
        validate_manifest([record, dict(record)])


def test_validate_package_rejects_archive_without_pages(tmp_path):
    archive_path = tmp_path / "editorial-board.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("assets/logo.svg", "asset")

    with pytest.raises(Exception, match="has no pages"):
        validate_package({
            "editorial-board": archive_path,
            "author-instructions": archive_path,
            "summary": tmp_path / "summary.md",
        })
