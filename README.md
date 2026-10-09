# Private Markets Product Benchmarking and Data-Quality Review

A small independent portfolio project for investment-product research support: validate a disclosure tracking sheet, quarantine data exceptions, and publish comparable management-fee cohorts with provenance and a review brief.

**Independent-project disclaimer:** This is an educational project, not work performed for Invesco or any asset manager. It has no company affiliation, private data, credentials, completed stakeholder approvals, investment advice, or production-readiness claim. Every product and disclosure in the sample is synthetic. Similarity to any actual product name is incidental.

## Setup
Requires Python 3.10+ with its standard library. No package installation, API keys, internet access, or credentials are needed. Save the supplied files preserving their paths and work from the project root.

## Local verification and reproducible demo
```sh
python -m unittest discover -s tests -p 'test*.py' -v
python benchmark.py --as-of 2026-10-09 --max-age-days 180 --out build
```

On systems using `python3`, substitute it for `python`. Tests are provided but have not been claimed to have run here.

Open `build/dashboard.html` in a browser. No server is required. Inspect `build/review.md` and `build/issues.csv` alongside the dashboard.

For an automation-style quarantine gate:
```sh
python benchmark.py --as-of 2026-10-09 --out build-strict --strict
```
The supplied fixture intentionally contains exceptions, so strict mode is expected to return **1** while still generating review artifacts. Normal mode returns **0** after a successful report build. Invalid input/configuration or an I/O error returns **2**.

## Generated artifacts
- `accepted.csv`: accepted observations, normalized fees, and source locators.
- `issues.csv`: row-level exception queue; one record may have multiple findings.
- `cohorts.csv`: matching cohort dimensions, counts, and eligible fee statistics.
- `dashboard.html`: self-contained, escaped comparison and exception tables.
- `review.md`: observed counts and proposed review follow-up.
- `manifest.json`: deterministic parameters, counts, and input CSV SHA-256 hashes.

CSV files can be inspected in Excel or imported into Power BI. Suggested types: identifiers/categories as text, fees/subscriptions as decimal numbers, `as_of` as date, and counts as integers. The project provides importable data, not a Power BI report or a claimed Power BI implementation.

## Evaluation: expected fixture behavior, not measured results
The tests assert these expectations for the fixed sample and demo date:
- 8 input records, 5 accepted, 3 quarantined, and 3 findings.
- Exceptions: one stale observation, one negative fee, one unknown source.
- 4 accepted cohorts; only S01 and S02 form a two-record comparison.
- That cohort's stated-fee median is 137.5 basis points and its range is 25 basis points.
- Other cohorts have blank peer statistics, not fabricated estimates.

These are arithmetic expectations derived from synthetic fixtures, not actual market findings or already-observed test results. A successful local test run verifies implemented behavior against these assertions; it does not validate real disclosures or legal comparability.

Tests also cover duplicate quarantine, missing values, category mismatches, nonfinite numbers, zero values, date boundaries, source chronology, each cohort dimension, empty datasets, malformed CSV, HTML escaping, spreadsheet formula safeguards, CLI status codes, input hashes, and byte-identical repeated outputs.

To check reproducibility manually:
```sh
python benchmark.py --as-of 2026-10-09 --out build-repeat
python -c "from pathlib import Path; a=Path('build'); b=Path('build-repeat'); assert all(p.read_bytes()==(b/p.name).read_bytes() for p in a.iterdir() if p.is_file()); print('Artifacts match')"
```
Use clean output directories; this check assumes only generated artifacts are present.

## Data and limitations
`data/disclosures.md` records the synthetic source fixtures. `data/sources.csv` maps provenance references, and `data/products.csv` contains manually transcribed observations and deliberate defects. No external disclosure scraping is implemented.

The narrow taxonomy prevents some obvious pooling mistakes but does not establish economic equivalence. Management fees exclude performance fees and other expenses. No risk, performance, underwriting, market coverage, or investment recommendation is evaluated. Source-reference validation is not independent source verification. Review steps are proposals, not completed approvals. See `docs/methodology.md` for the full decision boundary and output-write limitations.

## Suggested demonstration
1. Run verification and inspect the three exception types.
2. Explain why EUR, monthly liquidity, and committed-capital products are not pooled with the USD quarterly NAV cohort.
3. Trace an accepted row to its synthetic source note.
4. Explain what additional disclosure fields and legal/compliance review would be required before using this approach on real data.
