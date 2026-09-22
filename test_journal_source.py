from journal_source import build_manifest, load_excluded_codes, newest_mddb_filename, parse_alpha_codes


def test_newest_mddb_filename_uses_timestamped_export_name():
    filename = newest_mddb_filename([
        "readme.txt",
        "atypon-sage-mddb_31-12-2025_21-00-03.xml",
        "atypon-sage-mddb_01-01-2026_21-00-03.xml",
    ])

    assert filename == "atypon-sage-mddb_01-01-2026_21-00-03.xml"


def test_load_excluded_codes_reads_static_exception_file(tmp_path):
    exception_file = tmp_path / "known_exceptions.yaml"
    exception_file.write_text(
        "corporate_fed:\n  - code: ABH\n  - code: APB\n  - code: JCX\n",
        encoding="utf-8",
    )

    assert load_excluded_codes(exception_file) == {"ABH", "APB", "JCX"}


def test_parse_alpha_codes_handles_xml_namespaces_and_duplicates():
    xml_content = b"""<mddb xmlns=\"urn:mddb\">
        <journal><alpha_code>abh</alpha_code></journal>
        <journal><alpha_code> AJS </alpha_code></journal>
        <journal><alpha_code>abh</alpha_code></journal>
    </mddb>"""

    assert parse_alpha_codes(xml_content) == ["ABH", "AJS"]


def test_build_manifest_adds_both_page_types_and_excludes_corporate_fed_codes():
    manifest = build_manifest(["AJS", "ABH"], ["ABH", "APB", "JCX"])

    assert manifest == [
        {
            "journal_code": "ABH",
            "msg_url": "https://journals.sagepub.com/author-instructions/ABH",
            "eb_url": "https://journals.sagepub.com/editorial-board/ABH",
            "template_version": "unknown",
            "excluded": True,
            "excluded_reason": "corporate-fed",
        },
        {
            "journal_code": "AJS",
            "msg_url": "https://journals.sagepub.com/author-instructions/AJS",
            "eb_url": "https://journals.sagepub.com/editorial-board/AJS",
            "template_version": "unknown",
            "excluded": False,
            "excluded_reason": "",
        },
    ]