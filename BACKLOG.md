# Commonplace backlog

## Library expansion: 100,000 unique quotes

- Status: complete — privately published 2026-10-25
- Priority: high
- Requested: 2026-10-25
- Current library: 102,444 unique quotes; 19,332 authors; 34 subjects
- Target: at least 100,000 distinct quotations, with broad topic coverage
- Reference: [Goodreads quote library and categories](https://www.goodreads.com/quotes), plus the category screenshot supplied by the user on 2026-10-25

### Scope

- Grow the collection substantially beyond the initial 2,000-quote seed. Suggested milestones: 10,000 → 50,000 → 100,000 unique quotes.
- Use Goodreads' category breadth as a taxonomy reference: Love, Life, Inspirational, Humor, Philosophy, God, Wisdom, Romance, Truth, Poetry, Life Lessons, Death, Happiness, Hope, Faith, Relationships, Spirituality, Motivation, Religion, Writing, Success, Time, and Science.
- Retain and expand the original requested subjects: Biology, History, Technology, Parenting, and Habits, alongside Learning, Courage, and Friendship.
- Support multiple topics per quote. Normalize redundant labels such as “Inspirational Quotes Quotes”; distinguish meaningful categories while consolidating aliases such as Motivation/Motivational and Inspiration/Inspirational.
- Keep topic coverage balanced so growth is useful beyond general inspirational quotations.

### Data requirements

- Identify suitable sources and permitted reuse/access methods. Goodreads is a reference, not an assumed bulk-data feed.
- Preserve author, original date when known, cited work, source URL, provenance, and attribution confidence. Label unknown dates and disputed attributions explicitly.
- Support real Goodreads likes or other popularity metrics when available, retaining the metric's source and retrieval date. Keep popularity separate from personal importance ratings.
- Deduplicate exact and near-identical quotes; retain meaningful variants and competing attributions as linked records.
- Count unique quotations toward the 100,000 target, not summed category memberships.
- Extend suggested reading ages across the larger corpus, with clearly labeled guidance and reviewed selections for younger readers.

### Acceptance criteria

- [x] At least 100,000 distinct, usable quotes available in the library.
- [x] Broad category coverage, with per-category counts and documented aliases.
- [x] Provenance retained for every imported record; no invented dates or popularity counts.
- [x] Repeatable import, normalization, and duplicate-review process.
- [x] Search, filtering, pagination, and book selection remain responsive at 100,000 quotes; use indexed queries and incremental loading rather than downloading the full corpus at startup.
- [x] Existing saved books, personal quotes, favorites, importance ratings, backups, and PDF exports continue to work after expansion.

Implemented, validated and published at https://commonplace-press-rhys.rhyslindmark.chatgpt.site .

### Completion evidence

- 100,000 unique QuoteKG/legacy entries plus 2,444 added CC0-source Goodreads quotes.
- 3,276 real historical Goodreads counts; Goodreads collection and default likes sorting. Counts retain snapshot date/source/version.
- Exact/near deduplication, original IDs/aliases, indexed incremental loading and browser-local saved-book compatibility verified.
- Evidence: `work/expansion/import-report.json`, `goodreads-report.json`, `validation-report.json`, `SOURCES.md`, `GOODREADS.md`, and the regression tests.

## Follow-up: expand Goodreads count coverage

- Status: planned
- Grow beyond the 3,276 currently matched counts using a suitable complete-text source or permitted current data access.
- Preserve snapshot/observation timestamps and attribution confidence; do not treat missing counts as zero or claim historical snapshots are live.
- The roughly 350,000-row faellielupe export has no clear compilation reuse license, so it currently contributes matching numeric facts only, not new quote text.

## Print & ship with no manual PDF upload

- Status: guided Lulu handoff implemented; hosted checkout integration planned.
- Intended flow: click Print & ship → review price/quantity and enter address/payment in hosted checkout → printer produces and ships.
- Candidate: Peecho hosted Checkout / Print Button (https://www.peecho.com/solutions/checkout), which accepts source PDF URLs and owns payment, fulfillment and shipping. Confirm product/5x8/cover support with merchant credentials before choosing it definitively. Alternative: Lulu Print API plus own checkout.
- Required: merchant account/configuration, server endpoints, temporary printer-accessible file storage with scoped access/expiry, PDF validation and exact product geometry, live quote including shipping/taxes, explicit payment confirmation, order idempotency/status/webhooks and failure recovery, file retention cleanup.
- Keep existing private site audience and browser-local drafts; transmit only the edition the user explicitly sends for ordering. Never represent a link as an automated transfer or completed order.
