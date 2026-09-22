import json
import zipfile

import pytest

from run_pipeline import (
    build_run_manifest,
    changes_since_last_run,
    validate_manifest,
    validate_package,
    validate_required_section_ids,
)


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


def test_validate_package_allows_empty_archive_for_interrupted_run(tmp_path):
    archive_path = tmp_path / "partial.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("assets/logo.svg", "asset")
    summary_path = tmp_path / "summary.md"
    summary_path.write_text("partial", encoding="utf-8")

    validate_package(
        {
            "editorial-board": archive_path,
            "author-instructions": archive_path,
            "summary": summary_path,
        },
        allow_empty_pages=True,
    )


def test_build_run_manifest_hashes_html_and_assets(tmp_path):
    page_dir = tmp_path / "page"
    page_dir.mkdir()
    html_path = page_dir / "author-instructions_AJS.html"
    html_path.write_text("<html>hello</html>", encoding="utf-8")
    asset_dir = tmp_path / "assets"
    asset_dir.mkdir()
    (asset_dir / "logo.png").write_bytes(b"asset-bytes")

    manifest_path = build_run_manifest(tmp_path, [{"journal_code": "AJS"}])
    data = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert data[0]["journal_code"] == "AJS"
    assert data[0]["html_sha256"]
    assert data[0]["asset_hashes"]["logo.png"]


def test_changes_since_last_run_reports_changed_journal_codes(tmp_path):
    previous = tmp_path / "run_manifest_previous.json"
    current = tmp_path / "run_manifest_current.json"
    previous.write_text(
        json.dumps([
            {"journal_code": "AJS", "html_sha256": "aaa", "asset_hashes": {"logo.png": "hash1"}},
            {"journal_code": "ABC", "html_sha256": "bbb", "asset_hashes": {"logo.png": "hash2"}},
        ]),
        encoding="utf-8",
    )
    current.write_text(
        json.dumps([
            {"journal_code": "AJS", "html_sha256": "zzz", "asset_hashes": {"logo.png": "hash9"}},
            {"journal_code": "ABC", "html_sha256": "bbb", "asset_hashes": {"logo.png": "hash2"}},
        ]),
        encoding="utf-8",
    )

    assert changes_since_last_run(previous, current) == ["AJS"]


def test_validate_required_section_ids_skips_nonstandard_pages(tmp_path):
    page_dir = tmp_path / "page"
    page_dir.mkdir()

    (page_dir / "editorial-board_AJS.html").write_text(
        "<html><body><h1>Editorial board</h1></body></html>",
        encoding="utf-8",
    )
    (page_dir / "author-instructions_ACC.html").write_text(
        "<html><body><div class='submission-guideline'><h2>Submission guidelines</h2></div></body></html>",
        encoding="utf-8",
    )

    validate_required_section_ids(tmp_path)

    (page_dir / "author-instructions_PSP.html").write_text(
        "<html><body><div class='bs-accordion'><h3 id='heading-key-information'></h3><h3 id='heading-publishing-fees-and-open-access'></h3></div></body></html>",
        encoding="utf-8",
    )

    validate_required_section_ids(tmp_path)

    (page_dir / "author-instructions_BAD.html").write_text(
        "<html><body><div class='bs-accordion'><h3 id='heading-other-section'></h3></div></body></html>",
        encoding="utf-8",
    )

    with pytest.raises(Exception, match="missing required section ids"):
        validate_required_section_ids(tmp_path)
