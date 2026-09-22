# SAGE-8508 — Hardening plan for the MSG/Editorial Board scraper

Context: `scraper.py` (in this repo) already does the core extraction, image
localization, and email deobfuscation for the SAGE-7808 / SAGE-8091 MSG and
Editorial Board exports. SAGE-8508 asks for this to become a standing export
every ~4 months for CNP. This plan turns the one-off-friendly PoC into a
repeatable, low-effort recurring job. Part 1 is written to be handed to an AI
dev agent as a backlog. Part 2 is process/ownership steps for Nikos, not code.

---

## Code changes (feed this to a dev agent)

Work against `C:\Atypon\github\nk\scrapper`. Existing entry point is
`scraper.py` (`WebScraper` class, `click`-based CLI). Keep the current CLI
working throughout — each phase should be additive/backwards compatible so
`python scraper.py --urls urls.txt --sample sample` still works for ad hoc
single-journal runs.

### Phase 0 — Safety net (do first)
- Add `pytest` tests covering the pure functions that are easy to break
  silently: `WebScraper.url_to_filename`, `WebScraper.deobfuscate_email`,
  `WebScraper.download_image` (URL resolution for absolute / protocol-relative
  / root-relative / relative paths), and `process_images`' background-image
  regex. Use recorded HTML fixtures, not live network calls.
- Extract the hardcoded `selector` default and `User-Agent` string in
  `WebScraper.__init__` into `config.json`, with the current values as
  defaults, so later phases can add fallback selectors without touching code.
- Acceptance: `pytest` green, no behavior change on a small sample run.

### Phase 1 — Dynamic journal/page list (replaces hand-built `urls.txt`)
- New module `journal_source.py`. Given the current process is "someone
  assembles urls.txt by hand," replace this with a generator that produces
  the URL list from an authoritative source — sitemap.xml on
  journals.sagepub.com, or a PCMS/journal-list export if Nikos can get one
  (see Part 2, item 1). Confirm the real path patterns for the two page types
  before building (likely `/author-instructions/{CODE}` and
  `/editorial-board/{CODE}`, but verify against the SAGE-8091 delivery).
- Output a manifest, not a flat text file: CSV/JSON with columns
  `journal_code, msg_url, eb_url, template_version (unknown until Phase 2),
  excluded (bool), excluded_reason`.
- Add a `--manifest` CLI option as an alternative input to `--urls`; keep
  `--urls` for manual/test runs on a handful of URLs.
- Acceptance: running the generator against the current live site produces a
  journal count in the same ballpark as the 1641 from SAGE-8091, and a
  human-readable diff against last time's manifest (added/removed codes).

### Phase 2 — Make the known exceptions explicit instead of tribal knowledge
- Add `known_exceptions.yaml` seeded from the SAGE-7808 findings: the 3
  corporate-site-fed journals (Abhigyan, Applied Biosafety, Journal of
  Correctional Health Care) and the 7 old-template journals with embedded
  images (About Campus, Journal of Veterinary Diagnostic Investigation,
  Veterinary Pathology, Journal of Children's Orthopaedics, Palliative
  Medicine, Personality Science, Workplace Health & Safety). Each entry:
  `journal_code, category (corporate_fed | old_template_images), notes`.
- In `WebScraper.extract_content`, replace the single `selector` lookup with
  a small ordered list of selectors (new template, then old template) tried
  in sequence; record which one matched per journal in the report instead of
  just failing with "No element found matching selector."
- Journals listed in `known_exceptions.yaml` as `corporate_fed` are skipped
  before fetching and logged to a distinct "Excluded — corporate-fed" report
  section, rather than being attempted and failing.
- For `old_template_images` journals: extend `process_images` (currently
  scoped to the extracted `element`) to also resolve and attempt-download any
  `/pb-assets/cmscontent/{CODE}/...` references found anywhere on the fetched
  page, not just inside the selected element, since these images are
  sometimes referenced outside the extracted DOM subtree.
- Acceptance: re-running against the 10 known exception journals produces
  correct, labeled behavior (skip-with-reason or successful asset pull) with
  no manual side-channel steps.

### Phase 3 — Flag CNP-inaccessible links proactively
- New module `link_audit.py`, run against each generated output HTML after
  `process_url` completes: find `<a href>` values that resolve (after
  `urljoin`) to the `journals.sagepub.com` domain and aren't `mailto:`/anchor
  links. These are the links CNP flagged in SAGE-7808 as unreachable from
  China. Collect them into `blocked_links_report.txt`, grouped by journal
  code, so this is a delivery artifact instead of something CNP discovers and
  reports back weeks later.
- Acceptance: report lists every such link found in a full run; spot-check a
  few against pages known to contain them (e.g., the VET/PSP examples from
  SAGE-7808).

### Phase 4 — Validation and diffing between runs
- After a run, compute a content hash per journal (hash of the final wrapped
  HTML + any newly downloaded assets) and write `run_manifest_{date}.json`.
  Compare against the previous run's manifest (kept alongside prior
  deliveries, see Part 2, item 5) to produce `changes_since_last_run.txt`:
  which journal codes actually changed since the last delivery.
- Add a structural sanity check using the section IDs already documented in
  SAGE-7808 (`heading-key-information`, `heading-publishing-fees-and-open-access`,
  etc.) — flag any journal whose extracted content is missing expected
  section IDs, instead of only catching total extraction failure.
- Acceptance: on a run with no site changes, `changes_since_last_run.txt` is
  empty; on a run where you've manually edited one journal's MSG in a test
  environment, that journal shows up as changed and nothing else does.

### Phase 5 — Packaging and delivery summary
- Add `package.py`: zip `page/`, `assets/`, `lib/`, `fonts/` into
  `editorial-board_{YYYY-MM}.zip` and `submission-guidelines_{YYYY-MM}.zip`
  (matching the naming already used when these were delivered in SAGE-8091),
  and generate a single `DELIVERY_SUMMARY.md` combining: total counts,
  excluded/corporate-fed list, blocked-links summary, and
  changes-since-last-run — something that can be pasted directly into the
  Jira comment instead of written by hand each time.
- Acceptance: one command produces delivery-ready zips plus a paste-ready
  summary.

### Phase 6 — Ops hygiene (lower priority, nice to have)
- Bound concurrency (e.g., a thread pool of 8–10) for the fetch step —
  ~3,300 sequential requests at the current 500ms delay is tens of minutes;
  this isn't urgent for a quarterly job but is a cheap win.
- Replace `print`-only output with Python `logging` to a run-specific log
  file, so a run's full trace isn't lost once the terminal scrolls.
- Add a `__version__` to the tool and stamp it into `scraping_report.txt` /
  `DELIVERY_SUMMARY.md`, so you know which tool version produced which
  historical delivery when CNP asks questions about an old batch.
