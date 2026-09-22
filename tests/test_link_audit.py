from link_audit import audit_html, format_report, journal_code_from_url


def test_audit_html_resolves_and_filters_links():
    html = """
    <a href="/home/AJS">relative target</a>
    <a href="https://journals.sagepub.com/toc/AJS/current">absolute target</a>
    <a href="//journals.sagepub.com/loi/AJS">protocol-relative target</a>
    <a href="mailto:test@example.com">email</a>
    <a href="#section">anchor</a>
    <a href="https://example.com/outside">outside</a>
    <a href="/home/AJS">duplicate target</a>
    """

    assert audit_html(html, "https://journals.sagepub.com/author-instructions/AJS") == [
        "https://journals.sagepub.com/home/AJS",
        "https://journals.sagepub.com/toc/AJS/current",
        "https://journals.sagepub.com/loi/AJS",
    ]


def test_journal_code_from_url_uses_final_path_segment():
    assert journal_code_from_url(
        "https://journals.sagepub.com/editorial-board/PSP?view=full"
    ) == "PSP"


def test_format_report_groups_links_by_journal():
    report = format_report({
        "PSP": [("https://journals.sagepub.com/editorial-board/PSP", "https://journals.sagepub.com/home/PSP")],
        "AJS": [("https://journals.sagepub.com/author-instructions/AJS", "https://journals.sagepub.com/toc/AJS/current")],
    })

    assert report.index("Journal: AJS") < report.index("Journal: PSP")
    assert "https://journals.sagepub.com/toc/AJS/current" in report