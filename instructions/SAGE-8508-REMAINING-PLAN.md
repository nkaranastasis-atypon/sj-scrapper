# SAGE-8508 Remaining Delta Plan

Status assessed against commits through `9a07e41` and the current workspace.
This document records remaining work only; it does not change the execution
scope of the scraper.

## Completed

- **Phase 0:** Safety-net tests cover filename conversion, email decoding,
  image URL resolution, background images, and configured user agent.
- **Phase 1 core:** `journal_source.py` retrieves the newest matching MDDB XML
  from SFTP, parses `<alpha_code>`, and writes a JSON manifest. `scraper.py`
  accepts `--manifest` while retaining `--urls`.
- **Phase 2 partial:** `known_exceptions.yaml` contains the initial static
  corporate-fed exclusions `ABH`, `APB`, and `JCX`.
- **Phase 3:** Generated HTML is audited for resolved links to
  `journals.sagepub.com`; results are grouped in
  `blocked_links_report.txt`.
- **Phase 5 core:** `package.py` creates split delivery archives and a
  `DELIVERY_SUMMARY.md`.

## Remaining work

### Phase 1 acceptance and hardening

- Run the generator with real SFTP credentials and verify the journal count is
  in the expected range near 1,641.
- Compare the generated manifest with the previous delivery and report added
  and removed journal codes.
- Keep credentials out of committed configuration; prefer an environment
  variable or ignored local config override before the first live run.

### Phase 2 selector and exception behavior

- Replace the single extraction selector with an ordered selector list for
  new and old templates.
- Record the selector/template match in the scraping report.
- Load corporate-fed exceptions into the scraper so those journals are
  skipped before fetching and appear in a distinct report section.
- Add the seven old-template image exceptions once their journal codes are
  confirmed; broaden image discovery to page-level
  `/pb-assets/cmscontent/{CODE}/...` references for those journals.
- Add fixture-based tests for selector fallback, corporate-fed skipping, and
  page-level old-template image discovery.

### Phase 4: intentionally deferred

- Hash each final journal HTML plus downloaded assets and write
  `run_manifest_{date}.json`.
- Compare with the prior run and produce
  `changes_since_last_run.txt`.
- Add structural checks for required section IDs and report missing sections.

Phase 5 currently reports that Phase 4 was skipped; packaging should be
updated after Phase 4 exists so the summary includes real change data.

### Phase 5 follow-up

- Validate both archives against a real completed run, including expected
  page counts and shared assets.
- Confirm whether the delivery archives should include all shared resources
  in both archives or use a different SAGE-8091 layout.

### Phase 6: intentionally deferred

- Bound fetch concurrency while preserving request throttling and retries.
- Replace print-only progress with run-specific logging.
- Add a tool version and stamp it into scraping and delivery reports.

## Recommended order

1. Configure credentials safely and run Phase 1 against the live SFTP feed.
2. Finish Phase 2 behavior and confirm exception codes.
3. Implement Phase 4 validation and diffing.
4. Validate Phase 5 against a real delivery.
5. Consider Phase 6 operational improvements after one recurring run.