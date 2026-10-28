# Quote-library expansion source decision

Checked 2026-10-25 with web/API metadata and tiny live queries only. No bulk dataset, dependencies, browser, build, or extra agent was started. Workspace volume had 55 GiB free; expansion directory was 12 KiB before this note. Parent retained system memory measurements and recovery management.

## Recommended: QuoteKG v1.2

**Proceed with QuoteKG, preserving attribution and CC BY-SA 4.0 terms.** Its live endpoint provides enough English material and author/source provenance to pursue 100,000 usable, locally deduplicated quotations. Actual accepted row count must come from importer validation; upstream counts alone are not the delivered-library count.

- [Official project](https://quotekg.l3s.uni-hannover.de/) and [live SPARQL endpoint](https://quotekg.l3s.uni-hannover.de/sparql).
- [Versioned archive, DOI 10.5281/zenodo.6385077](https://zenodo.org/records/6385077); [record JSON](https://zenodo.org/api/records/6385077).
- [Primary ESWC paper](https://2022.eswc-conferences.org/wp-content/uploads/2022/05/paper_113_Kuculo_et_al.pdf), table 2: 267,740 English quotation IDs, 271,541 mentions, 19,073 persons; 193,848 English mentions have contexts. QuoteKG extracts person pages from Wikiquote and aligns mentions, so it supplies authors and citations rather than uniformly curated topic tags.
- Live JSON query independently returned the same 267,740 English IDs / 271,541 mentions. A stricter live query below returned **253,622 quotation IDs / 254,728 distinct lowercased English text literals** with an author label, explicit false misattribution, and 20–1,000 characters. More texts than IDs is expected because a quote can have several English mentions. Local text normalization, language checks, author cleanup, quality filters and duplicate removal remain required.

### License evidence and discrepancy

The [Zenodo JSON metadata](https://zenodo.org/api/records/6385077) identifies `cc-by-4.0`, but the archive's own [void.ttl](https://zenodo.org/records/6385077/files/void.ttl) explicitly identifies `https://creativecommons.org/licenses/by-sa/4.0/`. The paper section 6 agrees with **CC BY-SA 4.0**. Treat the distributed graph/extract as BY-SA 4.0; retain QuoteKG creator credit (Tin Kuculo, Simon Gottschalk, Elena Demidova), version/DOI, license link, modification notice, and per-record provenance. The pipeline's MIT software license is not the graph-data license. The compilation license does not establish that every quoted underlying work is public domain.

### Access and implementation route

**Implementation decision: use the versioned archive through a bounded subject-block parser and SQLite staging.** Parent independently verified HTTP Range access; a single streamed archive is more reproducible than hundreds of slow live queries. Remove the raw archive after preserving an accepted converted artifact and integrity evidence. English-only SPARQL batches remain a smaller-transfer alternative, but the grouped sample query took roughly 20–30 seconds per tiny page. Verified GET parameters: `format=json`, URL-encoded `query`. Endpoint currently accepts standard explicit prefixes and returns SPARQL `head.vars` / `results.bindings`. Batch on quotation URI with stable ordering and cursor/offset; select one English mention per quotation and deduplicate normalized text locally. Preserve quotation/mention URI, author label, original text, source Wikiquote page, context, source URL and misattribution flag in the intermediate artifact. Avoid a single huge JSON response or an in-memory RDF graph.

The tiny sample returned readable author labels, English `so:text`, `qkg:isMisattributed=false`, and author `owl:sameAs` links such as `https://en.wikiquote.org/wiki/Thomas_Jefferson`. Context can contain bibliographic text (for example a letter/date). Live source predicate was **`https://schema.org/source`**; also accept `dcterms:source` because documentation differs. Topic discovery can use `so:mentions` / linked entities, but these are not a complete ready-made topic taxonomy. Derive app topics transparently; do not label computed categories as original source tags.

Chosen archive input: [quotekg.ttl](https://zenodo.org/records/6385077/files/quotekg.ttl), **1,070,148,662 bytes**, MD5 `57f28b3944c275529de9bd1c790b816e`; [schema](https://zenodo.org/records/6385077/files/quotekg_schema.ttl), 1,061 bytes; [VoID](https://zenodo.org/records/6385077/files/void.ttl), 3,244 bytes. No English-only file appears in the versioned archive inventory. Stream the fallback through a bounded parser/disk staging process; do not load 1.07 GB into a JS/Python RDF model. Live bulk pagination reliability/rate limits have not been proven in this metadata audit; an endpoint-based importer should checkpoint and retry bounded failures.

Reproduce the strict headroom check by GET to the endpoint with `format=json` and this URL-encoded query:

```sparql
PREFIX so: <https://schema.org/>
PREFIX qkg: <https://quotekg.l3s.uni-hannover.de/resource/>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
SELECT (COUNT(DISTINCT ?quotation) AS ?quotes)
       (COUNT(DISTINCT LCASE(STR(?text))) AS ?distinctLowercaseTexts)
WHERE {
  ?quotation a so:Quotation ; so:spokenByCharacter ?person ;
             qkg:isMisattributed false ; qkg:hasMention ?mention .
  ?person skos:prefLabel ?name .
  ?mention so:text ?text .
  FILTER(LANG(?text)="en" && STRLEN(?text)>=20 && STRLEN(?text)<=1000)
}
```

## Other leads (prior reconnaissance; not preferred)

- [Quotes-500K original repository](https://github.com/ShivaliGoel/Quotes-500K): research/education wording is not a verified reusable compilation license. Kaggle/Hugging Face mirrors do not cure that gap; do not adopt without explicit data-license evidence.
- [m-ric/english_historical_quotes](https://huggingface.co/datasets/m-ric/english_historical_quotes): roughly 24k; useful supplementary lead, insufficient alone.
- English Wikiquote extracts around 58k in the known inneratlas lead are insufficient alone and overlap QuoteKG. Avoid combining raw counts as if all rows were distinct.

## Audit footprint

Only this source note was added in the repository. Temporary metadata/sample HTML/TTL files under `/tmp/commonplace-quotekg-*` were removed after recording the evidence. No large artifacts remain from this audit.

## Tested keyset page query

Exact request construction tested: `GET https://quotekg.l3s.uni-hannover.de/sparql?format=json&query=` followed by URL-encoded full SPARQL below (Python `urllib.parse.urlencode` during audit; JavaScript `new URLSearchParams({format: 'json', query})` is equivalent). No auth or browser was required. Standard SPARQL JSON values are nested objects; read each binding's `.value` and language from `["xml:lang"]`.

Two successive pages with `LIMIT 2` succeeded: first IDs `Quotation100003`, `Quotation100004` (2 rows, 2,336 bytes); then cursor `https://quotekg.l3s.uni-hannover.de/resource/Quotation100004` returned `Quotation100007`, `Quotation10001` (2 rows, 2,738 bytes). This verifies **lexicographic string URI ordering**, not numerical suffix ordering, and working exclusive keyset advancement. Both requests completed within a 30-second curl timeout, but the grouped query was slow even for two records. Use a bounded timeout around 60 seconds, sequential pages, checkpoint persistence and limited backoff. Bulk throughput remains unmeasured.

The inner query limits quotation IDs before expanding author/context fields and chooses the lexicographically first eligible mention IRI as a deterministic primary English text. The outer rows may multiply for multiple contexts/source URLs; merge locally by quotation IRI and accumulate citations. The outer query must not impose a row limit that truncates a quotation's sources. Set the cursor to the largest returned **quotation URI string**, after persisting the entire successful page. Change `LIMIT 2` to a measured bounded production page size (for example 500–1,000); do not advance a failed/incomplete page. Replace the empty string in the cursor filter with a safely encoded SPARQL string literal for the last quotation URI. Stop only after an empty complete page or after reaching the required locally accepted count.

```sparql
PREFIX so: <https://schema.org/>
PREFIX qkg: <https://quotekg.l3s.uni-hannover.de/resource/>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX dcterms: <http://purl.org/dc/terms/>
SELECT ?quotation ?personLabel ?mention ?text ?misattributed ?wikiquote ?context ?contextText ?source
WHERE {
  { SELECT ?quotation (MIN(STR(?candidate)) AS ?mentionIRI)
    WHERE {
      ?quotation a so:Quotation ; so:spokenByCharacter ?person ;
                 qkg:isMisattributed false ; qkg:hasMention ?candidate .
      ?person skos:prefLabel ?name .
      ?candidate so:text ?candidateText .
      FILTER(LANG(?candidateText)="en" && STRLEN(?candidateText)>=20 && STRLEN(?candidateText)<=1000)
      FILTER(STR(?quotation) > "")
    }
    GROUP BY ?quotation ORDER BY STR(?quotation) LIMIT 2
  }
  BIND(IRI(?mentionIRI) AS ?mention)
  ?quotation so:spokenByCharacter ?person ; qkg:isMisattributed ?misattributed .
  ?person skos:prefLabel ?personLabel .
  ?mention so:text ?text .
  OPTIONAL { ?person owl:sameAs ?wikiquote . FILTER(STRSTARTS(STR(?wikiquote),"https://en.wikiquote.org/")) }
  OPTIONAL {
    ?mention qkg:hasContext ?context .
    OPTIONAL { ?context qkg:contextText ?contextText . }
    OPTIONAL { ?context (so:source|dcterms:source) ?source . }
  }
}
ORDER BY STR(?quotation) STR(?mention) STR(?context) STR(?source)
```

Tiny pages confirmed a direct external context citation in `so:source` as well as the English Wikiquote author link. These are historical/public-figure quotations across many subjects; even short eligible records can contain polemical or offensive rhetoric. Source eligibility does not replace the application's existing editorial/quality checks. No whole-corpus sample or bulk import was performed by this audit.
