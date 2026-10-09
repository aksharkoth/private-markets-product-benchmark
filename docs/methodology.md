# Methodology and review boundary

## One use case
Turn a small product-disclosure tracking sheet into a reproducible, provenance-linked management-fee comparison and an exception list for product-team review.

## Data contract
All supplied observations are synthetic. Required columns are defined in `benchmark.py`; unknown additional columns are ignored. Values are trimmed, but category spelling and currency capitalization must match the documented taxonomy. CSV record numbers, not physical line numbers inside quoted multiline fields, identify findings.

Categories:
- Strategy: private_credit, private_equity, real_assets.
- Vehicle: evergreen, drawdown.
- Currency: USD, EUR, GBP; no conversion.
- Fee basis: nav, committed_capital, invested_capital.
- Liquidity: monthly, quarterly, none.
- Investor segment: qualified, institutional.

Management fees must already be annual stated percentages. The program does not annualize quarterly charges or infer missing fee bases. Minimum subscription is a nonnegative amount in the row's currency; it is tracked but not used to rank products. A zero fee or subscription is permitted mechanically, not endorsed as economically plausible. No upper fee threshold is invented.

## Validation and quarantine
Every occurrence of a duplicate product identifier is rejected; no arbitrary first-row winner is chosen. Empty required values, control characters, unknown categories, invalid or negative numeric values, nonfinite values, unknown source references, malformed dates, future observations, stale observations, and sources published before their stated observations generate findings. A row with any finding is quarantined. Dates exactly at the age limit are accepted.

Malformed CSV structure, missing headers, duplicate headers, an invalid source registry, or invalid configuration stop the run. This demo accepts only synthetic source kinds. It does not fetch URLs or verify that local fixture locators resolve; locators are review aids. A valid source reference does not prove the disclosure is accurate.

## Comparability
Cohorts match all six dimensions: strategy, vehicle, currency, fee basis, liquidity, and investor segment. Stated management-fee percentage multiplied by 100 gives basis points. Decimal arithmetic avoids binary floating-point rounding in the fee calculation.

With at least two accepted records, output the unweighted median, minimum, maximum, and range of stated fees. With one record, retain the cohort count but leave statistics empty. All accepted observations have equal weight; the dataset does not establish market coverage or representativeness. There is no product score or overall ranking.

## Governance support, not governance approval
The review brief identifies proposed research, product, legal/compliance, marketing, and technology follow-up. These are suggested functions, not people, relationships, meetings, approvals, or completed work. Quarantine creates a visible review queue; passing the checks is not a release authorization.

## Output safeguards and reproducibility
HTML cells are escaped. Spreadsheet-sensitive leading characters in CSV values are prefixed with an apostrophe. This changes exported text presentation deliberately; originals remain in the input files. Consumer-specific spreadsheet handling still requires review.

An explicit evaluation date prevents dependence on today's clock. Cohorts and issue-category summaries are sorted; input order is preserved for accepted records and findings. Output contains no runtime timestamp or machine-specific path. The manifest hashes the two input CSV files; it is not a signature or a complete software/environment attestation. Identical CSV bytes, options, and code should produce identical artifact bytes.

The writer replaces six known filenames in the output directory. Writes are not transactional; use a fresh output directory if preserving a prior run matters. Errors during writing can leave partial artifacts. Avoid concurrent runs targeting the same directory.

## Important omissions
Management fees are not all-in costs. Carried interest, incentive fees, administration expenses, waivers, fee tiers, leverage, share classes, redemption gates, lockups, notice periods, valuation practices, taxes, returns, and risk are not modeled. Matching liquidity labels does not establish equivalent redemption terms. No legal investor-eligibility determination is made. Synthetic fixtures cannot establish actual competitor positioning.
