# SAGE-8508 — Hardening plan for the MSG/Editorial Board scraper

Context: `scraper.py` (in this repo) already does the core extraction, image
localization, and email deobfuscation for the SAGE-7808 / SAGE-8091 MSG and
Editorial Board exports. SAGE-8508 asks for this to become a standing export
every ~4 months for CNP. This plan turns the one-off-friendly PoC into a
repeatable, low-effort recurring job. Part 1 is written to be handed to an AI
dev agent as a backlog. Part 2 is process/ownership steps for Nikos, not code.

---

## Process steps (not code)

1. **Get a real source for the exception list, once.** The old-template /
   corporate-fed journal lists came from a manual Vicki Slim review in
   September 2025 (attached as an Excel file in SAGE-7808). Ask her or her
   successor for the current list once, seed `known_exceptions.yaml` from it,
   and agree that Sage will flag it if a journal migrates template — don't
   silently let this file rot for years without anyone owning it.

2. **Confirm the URL patterns from a source you control**, not by re-deriving
   them from scraping. If PCMS or Passport has a clean journal-code export,
   generating the manifest from that is more robust than parsing a public
   sitemap that might not enumerate both page types cleanly.

3. **Name this as a standing deliverable somewhere that isn't just this Jira
   ticket thread.** Whatever governs SAGE's support scope (an SOW line, a
   recurring internal ticket template, whatever Atypon uses) should say
   "MSG/EB export for CNP, ~4-month cadence, ~X hours effort" explicitly. This
   is the piece that actually resolves the "implicit escalation" complaint —
   the code hardening makes the work cheap, but only a named commitment stops
   it from being absorbed as free ad hoc ticket work indefinitely.

4. **Set a recurring reminder tied to the actual commitment**, e.g. a
   scheduled task every ~4 months prompting "SAGE MSG/EB export due" — so the
   job runs on a rhythm you control rather than only when Sage happens to
   file a new ticket.

5. **Keep every delivered zip + manifest in one fixed place** (this repo, or
   wherever makes sense) so Phase 4's diffing has something to diff against,
   and so you have an audit trail if CNP later disputes what was delivered
   when.

6. **Set an explicit boundary on exception handling.** Decide once that
   "known unhandled cases get flagged in the delivery note, not silently
   patched by hand each cycle" — otherwise every new edge case CNP surfaces
   quietly becomes new standing manual work layered on top of the automated
   parts.

7. **Use the current goodwill to push one thing back to Sage/CNP**: their
   earlier complaints (CSS not linked, relative paths broken, can't resolve
   redirect links) are partly a CNP-side import fragility problem. Worth
   asking Daniel/Alex whether CNP can fix their import pipeline once, rather
   than Atypon re-solving the same packaging quirks every 4 months.
