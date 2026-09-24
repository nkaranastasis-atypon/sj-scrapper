import json
import zipfile

from package import package_delivery


def test_package_delivery_creates_split_archives_and_summary(tmp_path):
    output_dir = tmp_path / "output"
    page_dir = output_dir / "page"
    (output_dir / "assets").mkdir(parents=True)
    (output_dir / "lib").mkdir()
    (output_dir / "fonts").mkdir()
    page_dir.mkdir()
    (page_dir / "editorial-board_AJS.html").write_text("board", encoding="utf-8")
    (page_dir / "author-instructions_AJS.html").write_text("msg", encoding="utf-8")
    (output_dir / "assets" / "logo.png").write_bytes(b"asset")
    (output_dir / "lib" / "accordion.js").write_text("lib", encoding="utf-8")
    (output_dir / "fonts" / "font.woff").write_bytes(b"font")
    (output_dir / "static_sage_links_report.txt").write_text(
        "Link:   https://journals.sagepub.com/home/AJS\n", encoding="utf-8"
    )
    (output_dir / "changes_since_last_run.txt").write_text(
        "Changed journals since the last run:\n- AJS\n- XYZ\n", encoding="utf-8"
    )
    (output_dir / "run_manifest_20260922-142203.json").write_text(
        json.dumps([{"journal_code": "AJS", "html_sha256": "abc"}]), encoding="utf-8"
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps([
        {"journal_code": "ABH", "excluded": True, "excluded_reason": "corporate-fed"},
        {"journal_code": "AJS", "excluded": False},
    ]), encoding="utf-8")

    outputs = package_delivery(output_dir, manifest_path, "2026-09")

    assert outputs["summary"].name == "DELIVERY_SUMMARY-2026-09.md"

    with zipfile.ZipFile(outputs["editorial-board"]) as archive:
        assert set(archive.namelist()) == {
            "page/editorial-board_AJS.html",
            "lib/accordion.js",
            "fonts/font.woff",
            "changes_since_last_run.txt",
        }
    with zipfile.ZipFile(outputs["author-instructions"]) as archive:
        assert "page/author-instructions_AJS.html" in archive.namelist()
        assert "page/editorial-board_AJS.html" not in archive.namelist()
        assert "assets/logo.png" in archive.namelist()
        assert "changes_since_last_run.txt" in archive.namelist()
        assert "run_manifest_20260922-142203.json" not in archive.namelist()

    summary = outputs["summary"].read_text(encoding="utf-8")
    assert "ABH" in summary
    assert "Static links found on journals.sagepub.com: 1" in summary
    assert "Changed journals since the last run" in summary
    assert "- AJS" in summary
    assert "- XYZ" in summary
    assert "Tool version:" in summary
