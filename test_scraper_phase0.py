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