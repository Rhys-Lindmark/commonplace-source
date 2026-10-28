# Commonplace Press

A browser-local commonplace book website: 102,444 bundled quotations from 19,332 authors across 34 subjects, search, topic and suggested-age filters, personal quotes, importance ratings, favorites, a reorderable book composer, saved editions, JSON backup and restore, and PDF downloads. The Goodreads collection includes 3,276 historical like counts and 2,444 added CC0-source quotes.

## Run

Use Node 20+ for the checks and PDF tests. There is no package installation or build step.

```sh
python3 -m http.server 4183 --bind 127.0.0.1 --directory dist
node --check dist/app.js
node --check dist/pdf.js
node tests/pdf.test.cjs
node tests/library.test.cjs
node tests/migration.test.cjs
node tests/search.test.cjs
node tests/expanded-data.test.cjs
node tests/expanded-pdf.test.cjs
```

The PDF test regenerates the three sample deliverables in `output/pdf` and verifies pagination, trim sizes, cover dimensions, passage fitting, empty-selection handling, and data IDs. jsPDF is vendored, version 3.0.4, with its license. Libre Baskerville is embedded in generated PDFs; font licenses are in `dist/assets`.

## Data and storage

Bundled Quotable dataset: https://github.com/quotable-io/data. Original snapshot fetched 2026-10-25; 2,120 unique attributed quotations. Seven additional passages are checked against public-domain text at Project Gutenberg, with original publication years and source links. `data-curated.json` preserves these checked entries. `prepare_data.py` can regenerate the library using cached `/tmp/commonplace-{quotes,authors}.json` or fetch the upstream data if unavailable.

Topic classification uses keyword suggestions. Reading ages are approximate reading complexity suggestions, with a small reviewed set for ages 0–5; caregivers should review individual passages. Initial importance values are editorial defaults, and users can change them. Most imported quotes have no documented original date and are explicitly labeled accordingly. No dates, Goodreads counts, or verified-attribution flags are fabricated. Imported Goodreads counts retain dataset version, release date and source URL; exact observation time is unknown. Counts are snapshots from 2020–2023, not live API data. You can also supply a count on personal quotes.

Collection state is stored under `commonplace.press.v1` in localStorage. It is not synchronized across devices. The JSON backup includes custom quotes, selections, favorites, ratings, settings and saved books. Restore validates schema and referenced IDs and downloads the previous collection as a backup before replacing the current state.

## Print files

- Reading PDF: front cover, title/colophon, one quote per page, and a final blank page only when needed for an even interior page count.
- Interior PDF: title/colophon and one quote per page; no bleed; even page count with no minimum-page padding.
- Wrap cover PDF: one page containing back + spine + front with 0.125 inch bleed on all sides. Spine width follows Lulu’s paperback formula: interior pages / 444 + 0.06 inches. Legacy saved spine overrides are ignored. Thin spines intentionally have no spine text.
- All editions use 5 x 8 inches, including older saved books.
- Quote pages show no top quote counter or attribution footer. Bottom page numbers remain and can link to sources; archive credit stays on the colophon. Long passages shrink to 8pt; passages that cannot fit on one page fail explicitly rather than silently clipping or spilling onto a second quote page.

Check the specific printer's page minimum, paper, cover template and spine calculation before uploading. This site does not submit print orders. Attribution does not grant rights to republish protected text.

## Hosting

Serve `dist/` with any static host. Hosting credentials and deployment identity are intentionally excluded from this public source release.

## Expanded corpus and incremental index

The QuoteKG v1.2 import accepts100,000 distinct, author-balanced English quotations, including the original2,126 unique seedrecords and an alias for the duplicated legacyrecord. The checksum-pinned archive is DOI10.5281/zenodo.6385077,MD5`57f28b3944c275529de9bd1c790b816e`. Credit Tin Kuculo,Simon Gottschalk,Elena Demidova and Wikiquote contributors. The archive itself and paper specify CC BY-SA4.0 despite differing outer Zenodo metadata; this extract follows the stricter license. Suggested topics are computed, not presented as original Wikiquote tags.

The final library adds2,444 complete/printable quotes from Souradip Pal's CC0-labeled Goodreads export and has3,276 exact text+author-matched historical Goodreads counts. Abhishek Verma's2021 export and faellielupe's2020 SQLite export contribute matched numeric counts only; the latter's unclear compilation license is not used to import new text. The2021 export contains first-line fragments, so unmatched text is not imported. Invalid/partial outer wrappers are excluded from new quote text. See `work/expansion/GOODREADS.md`, the import reports and per-record provenance. Default ordering is Goodreads likes; missing counts remain null and sort last. The Goodreads tab shows records with imported counts only.

`dist/data/manifest.json` describes the release and facets. The32-byte-per-record catalog is metadata only; a reusable Worker searches prefix-sharded token postings and reads facets. Visible text loads in200-record chunks, with at most8record chunks and8postings dictionaries cached. Manifest+catalog startup is about3.7MB versus roughly143MiB of full corpus data. Actual-data tests measure filesystem-backed metadata operations; their milliseconds do not claim network/render performance. Selected/favorite/shelf snapshots remain independent of cache eviction.

### Reproduce data

Use Python3.9+ with standard-library modules and Node20+. No dependencies or browser binaries are required. Download the pinned QuoteKG archive to `work/expansion/raw/quotekg.ttl`. Run `python3 scripts/import_quotekg.py` (default target100000). The importer verifies the archive checksum and stages RDF into SQLite without loading a whole RDF graph. It retains explicit unknown dates, rejects known misattribution flags, normalizes whitespace, consolidates exact/near duplicates, and keeps variant/alternate-attribution evidence. `--reuse-staging` is for a completed staging database/eligible table from the same version.

For Goodreads enrichment, obtain these public archives into the ignored raw directory:

- `goodreads-cc0.zip`: Kaggle`souradippal/popular-quotes-from-goodreads`,v1.
- `goodreads-cc0-2021.zip`: Kaggle`abhishekvermasg1/goodreads-quotes`,v4.
- `goodreads-metadata.zip`: Kaggle`faellielupe/goodreads-quotes`,v1; stream-extract only its`quotes.sqlite` as`goodreads.sqlite`.

Run `python3 scripts/enrich_goodreads.py`, then `python3 scripts/audit_goodreads.py`. The audit traces every published count to an exact raw-source row using its quote-field SHA256; counts from duplicate text variants are never summed. It rebuilds the catalog/postings and appends compatible new IDs; snapshots/metadata fields retain dataset versions and source dates. Font coverage lists are retained in the expansion directory and derived from the vendored typefaces. Raw downloads/staging and duplicate accepted-record snapshots are disposable after validation; all published records and provenance remain under`dist/data`. No live Goodreads connection or recurring scraping is configured.

Expanded regression coverage includes actual-corpus uniqueness/counts/provenance/fontcoverage; indexed likes; incremental fetches; aliases; distant-record resolution; saved snapshot preservation; malformed-storage recovery; offline personal/snapshot restores; all trim sizes; embedded international text; and mandatory dataset/source credits even when optional notes are disabled.

## Cover editor

- Three title typefaces (Baskerville, Baskerville Italic, DM Sans), 12–40 pt size control, automatic whole-word fitting for long titles.
- Ten cover palettes and a custom color picker; contrasting lettering is automatic.
- Uploaded PNG/JPG/WebP art is normalized locally to a bounded PNG, contained without cropping, saved with editions/backups, and embedded in reading/wrap PDFs.
- Image generation is explicitly awaiting an OpenAI Developers connection; no generation endpoint is deployed or represented as working. Follow the Sites secret provisioning workflow before implementing/enabling it. Style brief: antique scientific engraving, fine etched lines and crosshatching, isolated composition, transparent background, no lettering, matching the existing armillary illustration.

## Print and ship handoff

The main export action prepares a ZIP with `01-interior.pdf`, `02-cover.pdf`, and `START-HERE.txt`. It recommends Lulu personal printing (5x8 Novella, paperback, Standard Black & White, 60# cream, matte). The bundle interior is grayscale and uses wider margins for thick books. The cover follows Lulu’s documented paperback spine and outer bleed. Users unzip and upload the two PDFs, review Lulu’s exact template/preview, then enter shipping/payment there. No order is submitted by this site.

The 32–800-page paperback requirement is shown live. We never reintroduce minimum-page padding; short books retain reading/individual exports. Sources checked2026-10-26: https://www.lulu.com/print-api/products ; https://assets.lulu.com/media/guides/en/lulu-book-creation-guide.pdf ; https://help.lulu.com/en/support/solutions/articles/64000255486-how-to-create-a-print-book .

For an upload-free checkout, Peecho’s hosted Print Button/Checkout is the proposed next integration: merchant account, server-created private order, temporary printer-accessible PDF storage, matching book/cover product validation, hosted address/payment collection, status/webhooks, retries/idempotency, and retention cleanup. No merchant account is connected and no checkout is claimed live. See https://www.peecho.com/solutions/checkout .

## GitHub and ai.rhyslindmark.com

Public source: https://github.com/Rhys-Lindmark/commonplace-source. The original development repository and its history remain private. This clean release excludes personal work logs, generated books, local browser collections, hosting identity, and access-bearing citation query parameters. The public app is deployed at https://ai.rhyslindmark.com/commonplace through the existing `rhyslindmark-website` Cloudflare Pages project.

To update the public copy, commit/push source here, then run:

```sh
python3 scripts/export_subpath.py --destination /path/to/rhyslindmark-website/public/commonplace
```

The exporter copies only deploy-ready `dist/` files, adds a `/commonplace/` HTML base and canonical URL, records the source SHA, and protects locally modified/unmanaged files. Commit that directory in the website repository and push its main branch; the existing Cloudflare GitHub integration deploys it. Font and quote-data licenses are retained. No dependencies, raw imports, local browser collections, or private work logs enter the public asset directory.

Browser storage is isolated by origin: use Back up on the original ChatGPT Site and Restore on the new address to move a collection. New image generation and printer merchant integrations remain awaiting their connections, as documented above.

## Quote chronology

Current result:65,099work/source-context dates and37,345estimates, including371very-low-confidence corpus-prior fallbacks;1,254records are BCE. Every quote has a sortable date.

All102444catalog quotes receive chronology metadata from `python3 scripts/complete_dates.py --apply`. The source-first pass checks reviewed work/speech references, existing source descriptions, citations, and exact linked bibliographic works with credited-author matches. A source-context year describes publication or attestation and does not independently authenticate the wording or its first utterance.

Unresolved records receive estimates, normally at75%of a known author lifespan. Birth-only, death-only, activity-period, and dated-work anchors provide bounded alternatives. The small remainder without a resolved author/source anchor uses a very-low-confidence corpus-date prior. Every estimate retains its method, confidence, author sources and anchors internally. Wikidata coarse dates retain period bounds and BCE astronomical years are converted to historical years without year zero.

Only quote cards display `· estimate`. Detail views, book previews and PDFs display the year without that marker. Original quote IDs, wording, seven original year values, likes, topics, saved books and backup formats are preserved. Date sorting/search uses the complete chronology; saved catalog snapshots refresh by audit ID.

Reproducible public metadata and reports live in `work/date-estimates/`; source references are in `SOURCES.md`. `fetch_author_dates.mjs` and `enrich_author_dates.mjs` resolve exact linked identities, followed by `fetch_date_precision.mjs`. `fetch_work_dates.mjs` and `refine_work_dates.mjs` resolve credited works and date precision. Fetches are sequential, bounded and resumable with ignored caches. After applying dates, run `python3 scripts/build_sections.py` to regenerate the catalog release. Import/enrichment CLI entrypoints apply both steps automatically. Run `npm test` for parser, full-corpus, sorting/search, migration and PDF verification. The previous v1 source-only audit remains in `work/date-audit/` as historical evidence.

## Bounded topic sections

Oversized topics expand into editorial keyword sections, each capped at10,000 catalog quotes. `All topics` remains the complete library overview. Reflections with no clear keyword match are divided by author ranges; personal additions appear separately when needed to preserve the cap. Original topic tags and saved-book IDs remain unchanged.

Run `python3 scripts/build_sections.py` after rebuilding a catalog. The import/enrichment CLI already runs this after the chronology audit. The generator writes lazy `dist/data/sections/*.json` membership lists, manifest browsing metadata, and `work/topic-sections/report.json`. Keyword rules are tracked in `work/topic-sections/rules.json`; run `node tests/sections.test.cjs` for exhaustive partition/filter checks.

## Security and privacy

Collection data stays in browser localStorage; no personal books or browser backups are bundled. Imported source URLs omit document-access query keys. Keep API keys and hosting credentials outside this repository. Code visibility does not grant additional rights to quoted works; retain the dataset, font, and vendor licenses already included.
