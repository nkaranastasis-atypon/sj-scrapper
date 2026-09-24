import json
import zipfile

import pytest

from run_pipeline import (
    _combined_file_hash,
    build_run_manifest,
    changes_since_last_run,
    upload_delivery_artifacts,
    write_changes_report,
    validate_manifest,
    validate_package,
    validate_required_section_ids,
)


class FakeTransport:
    def __init__(self):
        self.keepalive = None

    def set_keepalive(self, seconds):
        self.keepalive = seconds


class FakeChannel:
    def __init__(self):
        self.timeout = None

    def settimeout(self, timeout):
        self.timeout = timeout


class FakeSFTP:
    def __init__(self):
        self.channel = FakeChannel()
        self.directories = {"/"}
        self.uploaded = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def get_channel(self):
        return self.channel

    def stat(self, path):
        if path not in self.directories:
            raise OSError(path)

    def mkdir(self, path):
        self.directories.add(path)

    def put(self, local_path, remote_path):
        self.uploaded.append((local_path, remote_path))


class FakeSSHClient:
    def __init__(self, sftp):
        self.sftp = sftp
        self.transport = FakeTransport()
        self.connect_options = None
        self.closed = False

    def set_missing_host_key_policy(self, policy):
        self.policy = policy

    def connect(self, **kwargs):
        self.connect_options = kwargs

    def get_transport(self):
        return self.transport

    def open_sftp(self):
        return self.sftp

    def close(self):
        self.closed = True


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


def test_upload_delivery_artifacts_uploads_only_archives_and_summary(tmp_path, monkeypatch):
    outputs = {}
    for name, filename in {
        "editorial-board": "editorial-board_2026-09.zip",
        "author-instructions": "submission-guidelines_2026-09.zip",
        "summary": "DELIVERY_SUMMARY-2026-09.md",
    }.items():
        path = tmp_path / filename
        path.write_text(name, encoding="utf-8")
        outputs[name] = path
    (tmp_path / "scraping_report.txt").write_text("not uploaded", encoding="utf-8")
    (tmp_path / "static_sage_links_report.txt").write_text("not uploaded", encoding="utf-8")

    fake_sftp = FakeSFTP()
    fake_client = FakeSSHClient(fake_sftp)
    monkeypatch.setattr("run_pipeline.paramiko.SSHClient", lambda: fake_client)

    uploaded = upload_delivery_artifacts(
        {
            "journalSource": {
                "host": "sftp.example.test",
                "port": 22,
                "username": "sage",
                "keyFilename": "key.pem",
                "deliveryRemoteDir": "/sage/delivery/2026-09",
                "readTimeout": 60,
                "keepaliveSeconds": 15,
            }
        },
        outputs,
        lambda message: None,
    )

    assert uploaded == [
        "/sage/delivery/2026-09/editorial-board_2026-09.zip",
        "/sage/delivery/2026-09/submission-guidelines_2026-09.zip",
        "/sage/delivery/2026-09/DELIVERY_SUMMARY-2026-09.md",
    ]
    assert [remote_path for _, remote_path in fake_sftp.uploaded] == uploaded
    assert fake_client.connect_options["hostname"] == "sftp.example.test"
    assert fake_client.connect_options["key_filename"] == "key.pem"
    assert fake_client.transport.keepalive == 15
    assert fake_sftp.channel.timeout == 60
    assert fake_client.closed


def test_build_run_manifest_hashes_html_and_assets(tmp_path):
    page_dir = tmp_path / "page"
    page_dir.mkdir()
    html_path = page_dir / "author-instructions_AJS.html"
    html_path.write_text("<html><img src='../assets/logo.png'></html>", encoding="utf-8")
    asset_dir = tmp_path / "assets"
    asset_dir.mkdir()
    (asset_dir / "logo.png").write_bytes(b"asset-bytes")
    (asset_dir / "unused.png").write_bytes(b"unused-bytes")

    manifest_path = build_run_manifest(tmp_path, [{"journal_code": "AJS"}])
    data = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert data[0]["journal_code"] == "AJS"
    assert data[0]["html_sha256"]
    assert data[0]["asset_hashes"]["logo.png"]
    assert "unused.png" not in data[0]["asset_hashes"]


def test_combined_file_hash_ignores_request_volatile_html_values(tmp_path):
    first = tmp_path / "first.html"
    second = tmp_path / "second.html"
    first.write_text(
        '<script nonce="old">x</script><div id="accordion123"><span data-cfemail="82e7eae3ffe7f0c2e5efe3ebeeace1edef"></span></div>',
        encoding="utf-8",
    )
    second.write_text(
        '<script nonce="new">x</script><div id="accordion456"><span data-cfemail="91f4f9f0ecf4e3d1f6fcf0f8fdbff2fefc"></span></div>',
        encoding="utf-8",
    )

    assert _combined_file_hash([first]) == _combined_file_hash([second])


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


def test_write_changes_report_reads_previous_run_directory(tmp_path):
    previous_dir = tmp_path / "previous"
    current_dir = tmp_path / "current"
    previous_dir.mkdir()
    current_dir.mkdir()
    previous_manifest = previous_dir / "run_manifest_previous.json"
    current_manifest = current_dir / "run_manifest_current.json"
    previous_manifest.write_text(
        json.dumps([{"journal_code": "AJS", "html_sha256": "old"}]),
        encoding="utf-8",
    )
    current_manifest.write_text(
        json.dumps([{"journal_code": "AJS", "html_sha256": "new"}]),
        encoding="utf-8",
    )

    report_path = write_changes_report(current_dir, current_manifest, previous_dir)

    assert report_path.read_text(encoding="utf-8") == (
        "Changed journals since the last run:\n- AJS\n"
    )


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
