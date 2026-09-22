from pathlib import Path
from unittest.mock import Mock

from bs4 import BeautifulSoup

from scraper import WebScraper


DEFAULT_CONFIG = {
    "selector": "div.content",
    "options": {"localizeImages": True},
}


def test_url_to_filename_uses_path_only():
    scraper = WebScraper(DEFAULT_CONFIG)

    assert scraper.url_to_filename(
        "https://journals.example.test/author-instructions/AJS?view=full"
    ) == "author-instructions_AJS.html"


def test_deobfuscate_email_decodes_cloudflare_value():
    scraper = WebScraper(DEFAULT_CONFIG)

    assert scraper.deobfuscate_email(
        "82e7eae3ffe7f0c2e5efe3ebeeace1edef"
    ) == "eha}er@gmail.com"


def test_download_image_resolves_supported_url_forms(tmp_path):
    scraper = WebScraper(DEFAULT_CONFIG)
    response = Mock(content=b"image", headers={})
    response.raise_for_status.return_value = None
    scraper.session.get = Mock(return_value=response)

    urls = [
        "https://cdn.example.test/images/absolute.png",
        "//cdn.example.test/images/protocol.png",
        "/images/root.png",
        "images/relative.png",
    ]
    expected = [
        "https://cdn.example.test/images/absolute.png",
        "https://cdn.example.test/images/protocol.png",
        "https://journals.example.test/images/root.png",
        "https://journals.example.test/author-instructions/images/relative.png",
    ]

    for img_url, expected_url in zip(urls, expected):
        filename = scraper.download_image(
            img_url,
            "https://journals.example.test/author-instructions/AJS",
            tmp_path,
        )
        assert filename is not None
        assert scraper.session.get.call_args.args[0] == expected_url


def test_process_images_localizes_background_image_url(tmp_path):
    scraper = WebScraper(DEFAULT_CONFIG)
    response = Mock(content=b"image", headers={})
    response.raise_for_status.return_value = None
    scraper.session.get = Mock(return_value=response)
    element = BeautifulSoup(
        '<section><div style="color: red; background-image: url(\'/images/bg.png\')"></div></section>',
        "lxml",
    ).section
    styled_element = element.div

    scraper.process_images(
        element,
        "https://journals.example.test/author-instructions/AJS",
        tmp_path,
    )

    assert styled_element["style"] == "color: red; background-image: url('../assets/bg.png')"
    assert styled_element["data-original-style"] == "color: red; background-image: url('/images/bg.png')"
    assert (tmp_path / "bg.png").read_bytes() == b"image"


def test_user_agent_is_loaded_from_config():
    scraper = WebScraper({**DEFAULT_CONFIG, "userAgent": "test-agent"})

    assert scraper.session.headers["User-Agent"] == "test-agent"


def test_scraper_report_includes_tool_version():
    scraper = WebScraper(DEFAULT_CONFIG)

    report = scraper.report.generate_report()

    assert "Tool version:" in report


def test_scraper_exposes_version_and_run_log(tmp_path):
    from scraper import __version__

    scraper = WebScraper({**DEFAULT_CONFIG, "outputDir": str(tmp_path)})

    assert __version__ == "0.2.0"
    assert scraper.logger is not None
    assert (tmp_path / "run.log").exists()


def test_extract_content_tries_fallback_selectors():
    scraper = WebScraper({
        **DEFAULT_CONFIG,
        "selector": "div.missing",
        "selectors": ["div.missing", "div.old-template"],
    })
    html = "<html><body><div class='old-template'>Old template content</div></body></html>"

    element = scraper.extract_content(html, "https://journals.example.test/author-instructions/AJS")

    assert element is not None
    assert element.get_text(strip=True) == "Old template content"
    assert scraper.last_selector_match == "div.old-template"


def test_corporate_fed_url_is_detected_from_exception_file(tmp_path):
    exceptions_path = tmp_path / "exceptions.yaml"
    exceptions_path.write_text("corporate_fed:\n  - code: AJS\n", encoding="utf-8")
    scraper = WebScraper({
        **DEFAULT_CONFIG,
        "exceptionsPath": str(exceptions_path),
    })

    assert scraper.is_corporate_fed_url("https://journals.example.test/author-instructions/AJS")
    assert not scraper.is_corporate_fed_url("https://journals.example.test/author-instructions/ABC")


def test_process_url_skips_corporate_fed_journal_before_fetch(tmp_path):
    exceptions_path = tmp_path / "exceptions.yaml"
    exceptions_path.write_text("corporate_fed:\n  - code: AJS\n", encoding="utf-8")
    scraper = WebScraper({
        **DEFAULT_CONFIG,
        "exceptionsPath": str(exceptions_path),
    })
    scraper.fetch_url = Mock()

    result = scraper.process_url("https://journals.example.test/author-instructions/AJS")

    assert result is True
    scraper.fetch_url.assert_not_called()
    assert "Excluded - corporate-fed" in scraper.report.generate_report()


def test_report_records_selector_match():
    scraper = WebScraper({**DEFAULT_CONFIG, "selectors": ["div.main", "div.old-template"]})
    html = "<html><body><div class='old-template'>content</div></body></html>"

    scraper.extract_content(html, "https://journals.example.test/author-instructions/AJS")

    report = scraper.report.generate_report()
    assert "Selector matches" in report
    assert "div.old-template" in report


def test_process_url_records_obsolete_journal_code_as_skipped_data_issue():
    scraper = WebScraper(DEFAULT_CONFIG)
    error_page = """
    <main class="content">
      <div class="general-error-page">Journal not found</div>
    </main>
    """
    scraper.fetch_url = Mock(return_value=error_page)

    result = scraper.process_url("https://journals.example.test/author-instructions/JNL")

    assert result is True
    assert scraper.report.failed == 0
    assert "obsolete journal code" in scraper.report.generate_report().lower()


def test_process_images_discovers_page_level_pb_assets(tmp_path):
    scraper = WebScraper(DEFAULT_CONFIG)
    response = Mock(content=b"image", headers={})
    response.raise_for_status.return_value = None
    scraper.session.get = Mock(return_value=response)
    page_html = """
    <html><body>
      <div class='main'>content</div>
      <img src='/pb-assets/cmscontent/AJS/example.png'>
    </body></html>
    """
    element = BeautifulSoup("<div class='main'>content</div>", "lxml").div

    scraper.process_images(element, "https://journals.example.test/author-instructions/AJS", tmp_path, page_html=page_html)

    assert (tmp_path / "example.png").exists()
    assert any("/pb-assets/cmscontent/AJS/example.png" in entry["original"] for entry in scraper.report.images_processed)


def test_old_template_exception_codes_are_loaded_from_yaml(tmp_path):
    exceptions_path = tmp_path / "exceptions.yaml"
    exceptions_path.write_text(
        "corporate_fed:\n  - code: ABH\nold_template_images:\n  - code: VET\n",
        encoding="utf-8",
    )
    scraper = WebScraper({**DEFAULT_CONFIG, "exceptionsPath": str(exceptions_path)})

    assert scraper.is_old_template_image_journal("https://journals.example.test/author-instructions/VET")
    assert not scraper.is_old_template_image_journal("https://journals.example.test/author-instructions/ABC")


def test_run_removes_intermediate_progress_reports_when_complete(tmp_path):
    scraper = WebScraper({
        **DEFAULT_CONFIG,
        "outputDir": str(tmp_path),
        "options": {"maxWorkers": 1},
    })
    scraper.process_url = Mock(return_value=True)
    urls = [f"https://journals.example.test/author-instructions/JNL{index}" for index in range(100)]

    scraper.run_urls(urls, resume=False)

    assert not list(tmp_path.glob("progress_report_*_of_*.txt"))