# Goodreads source and indexed-popularity handoff

Checked 2026-10-25. Bounded metadata/API inspection plus the small CC0 archives only; no browser/server/install/new agent. Parent owns quote imports, numeric matching, data/UI changes and archive lifecycle. Existing licensed quote text must retain its own provenance when popularity is matched from a separate source.

## Explicitly labelled small sources

| Source | Uploader label / version | Dataset release date | Verified schema / size |
|---|---|---|---|
| [Popular Quotes from GoodReads — Souradip Pal](https://www.kaggle.com/datasets/souradippal/popular-quotes-from-goodreads) | CC0: Public Domain; v1 | 2023-07-01 14:30:38 UTC | `quotes.csv`: 3,000 rows, columns empty index header / `author` / `quote` / `likes`; 489,620 uncompressed bytes. Likes are strings such as `167877 likes`. |
| [Goodreads Quotes — Abhishek Verma](https://www.kaggle.com/datasets/abhishekvermasg1/goodreads-quotes) | CC0: Public Domain; v4 | 2021-03-30 19:02:38 UTC | `quotes.csv`: 3,001 rows, `index`, `quote`, `author`, `tags`, `likes`; 704,045 uncompressed bytes. Tags use semicolons; likes are numeric strings such as `149270`. |
| [Popular Quotes — hoangziet](https://www.kaggle.com/datasets/hoangziet/popular-quotes) | MIT; v1 | 2025-05-07 03:02:30 UTC | Metadata only; 319,717 uncompressed bytes. Description says the Goodreads Popular Quotes pages were crawled. No file download or schema validation in this audit. |

Authoritative metadata endpoints checked: [Souradip dataset record](https://www.kaggle.com/api/v1/datasets/view/souradippal/popular-quotes-from-goodreads), [Souradip file inventory](https://www.kaggle.com/api/v1/datasets/list/souradippal/popular-quotes-from-goodreads), [Abhishek dataset record](https://www.kaggle.com/api/v1/datasets/view/abhishekvermasg1/goodreads-quotes), [hoangziet dataset record](https://www.kaggle.com/api/v1/datasets/view/hoangziet/popular-quotes). API `licenseName`, `currentVersionNumber`, `lastUpdated` and version entries supply the labels/dates above.

Reproducible archive URLs:

- `https://www.kaggle.com/api/v1/datasets/download/souradippal/popular-quotes-from-goodreads?datasetVersionNumber=1`
- `https://www.kaggle.com/api/v1/datasets/download/abhishekvermasg1/goodreads-quotes?datasetVersionNumber=4`

Archive SHA-256 observed: Souradip ZIP `5d8cf8d68f6354181c665064fae3756d47d000b7fa34463a4e9f473b438202f4`; Abhishek ZIP `454887a4d4b17aaa4714d10bd29216070e1784bbcf7245accab2b538f4a72ba8`. Parent already downloaded Souradip archive. Abhishek's bounded verification archive is `/tmp/commonplace-goodreads-cc0.zip`; parent may reuse it for the authorized import and clean it after preserving source evidence.

## Provenance and date limits

These are uploader-labelled datasets of scraped Goodreads material, not an official/live Goodreads API. The version/release dates are **dataset snapshot release dates**, not verified timestamps for when each like count was observed. Preserve that distinction in UI/export provenance. Counts can change, scraping/parsing may contain errors, and the small files do not supply individual Goodreads quote IDs/URLs. Link the relevant dataset and Goodreads source section where an exact quote link is unavailable; do not invent a Goodreads quote URL.

Retain uploader/source credit even for CC0-labelled input: Souradip Pal or Abhishek Verma; dataset name/version/URL; Goodreads as the popularity source; retrieval date 2026-10-25; release date as above; normalization/import/matching notice. Keep original author attribution and original tag fields separate from computed app topics. A dataset uploader's label does not independently establish rights in every underlying quotation; existing source-text provenance remains important.

Parent additionally selected [faellielupe/goodreads-quotes](https://www.kaggle.com/datasets/faellielupe/goodreads-quotes), a much larger 2020 metadata source with an unknown compilation licence, for **numeric-count matching to already licensed text only**. This agent did not download, audit or approve that corpus as a reusable text source. Preserve its source/version/date and matching rule separately from the quote-text licence; do not present its unknown compilation licence as CC0. Parent owns the exact archive/version evidence and match validation.

## Worker changes and root integration

`dist/library-worker.js` now reads unsigned little-endian uint32 at catalog byte28 only when `manifest.hasLikeCounts === true`; `0xffffffff` means unknown. Other manifests ignore those formerly reserved bytes and continue treating built-in likes as null. Known zero is a real count. `sort:'likes'` places known counts descending, missing last, with curated order for ties; personal importance overrides and all other sort modes are unchanged. Custom records continue using their numeric `record.likes`.

`collection:'goodreads'` includes built-in rows whose indexed count is known and excludes unsourced personal records. A custom record is included only when `record.popularity?.source === 'Goodreads'`. Root must write matching byte28 values, set `hasLikeCounts:true`, keep full-record `likes` consistent with the index, and attach source/snapshot metadata to the full records. Parent is adding the Goodreads tab and appropriate display labels.

Verification: bundled Node syntax check and `tests/search.test.cjs` pass. Synthetic likes100/5/unknown/known-zero test descending order, stable ties, topic/age/favorites filters, custom mixing, the Goodreads collection, old-catalog guards, personal-rating independence and unchanged curated/author/short/oldest sorting. All existing worker/client tests continue passing. No app/client/importer/corpus edits were made by this task.

## Applied import policy

Souradippal v1 supplies the added Goodreads quote text. Abhishek Verma's older export is used for exact text/author numeric-count matching only, because its rows can contain first-line excerpts. Both providers label their datasets CC0. Malformed/unbalanced outer quote wrappers are excluded from new quote text rather than presenting partial multiline passages as complete quotations.

The larger faellielupe v1 archive exposes 348,085 rows in a SQLite `QUOTES` table with QUOTE/AUTHOR/TITLE/LIKES/TAGS. Its compilation license is unknown. This integration uses its quote/author fields transiently as exact normalized matching keys and imports only corresponding numeric popularity facts; it does not add its quote text, book titles or tags. Literal escaped line breaks are normalized for matching. Counts are never applied across differing author attributions. Newer dataset releases take precedence over older counts, without assuming likes must increase.

Per-record `popularity` stores count, Goodreads source, dataset URL/version, snapshot date and its meaning: release date, with exact individual observation time unknown. Missing counts remain null. The binary facet index stores uint32 likes at byte28, guarded by manifest.hasLikeCounts; 0xffffffff means unknown. Goodreads view includes only known counts, and global default sort is Goodreads likes descending with missing counts last.
