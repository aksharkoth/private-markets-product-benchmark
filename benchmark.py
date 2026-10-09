"""Independent synthetic private-markets product benchmarking demo."""
import argparse
import csv
import hashlib
import html
import io
import json
import sys
from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from statistics import median

PRODUCT_FIELDS = (
    'product_id', 'product_name', 'strategy', 'vehicle', 'currency',
    'fee_basis', 'liquidity', 'investor_segment', 'management_fee_pct',
    'min_subscription', 'as_of', 'source_id'
)
SOURCE_FIELDS = ('source_id', 'title', 'kind', 'fixture_locator', 'published_on')
GROUP_FIELDS = ('strategy', 'vehicle', 'currency', 'fee_basis', 'liquidity', 'investor_segment')
RECORD_FIELDS = PRODUCT_FIELDS + ('management_fee_bps', 'source_title', 'fixture_locator')
ISSUE_FIELDS = ('row_number', 'product_id', 'field', 'code', 'raw_value', 'message')
SUMMARY_FIELDS = GROUP_FIELDS + ('count', 'comparison_status', 'median_fee_bps', 'min_fee_bps', 'max_fee_bps', 'spread_bps')
ALLOWED = {
    'strategy': {'private_credit', 'private_equity', 'real_assets'},
    'vehicle': {'evergreen', 'drawdown'},
    'currency': {'USD', 'EUR', 'GBP'},
    'fee_basis': {'nav', 'committed_capital', 'invested_capital'},
    'liquidity': {'monthly', 'quarterly', 'none'},
    'investor_segment': {'qualified', 'institutional'},
}


def read_table(path, required):
    with Path(path).open(encoding='utf-8', newline='') as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        if len(fields) != len(set(fields)):
            raise ValueError(f'{Path(path).name}: duplicate CSV header')
        missing = set(required) - set(fields)
        if missing:
            raise ValueError(f'{Path(path).name}: missing columns: {", ".join(sorted(missing))}')
        rows = []
        for number, row in enumerate(reader, 2):
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f'{Path(path).name}: malformed row {number}')
            rows.append({key: value.strip() for key, value in row.items()})
        return rows


def parse_date(value):
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError('Use YYYY-MM-DD')
    return parsed


def number(value):
    result = Decimal(value)
    if not result.is_finite():
        raise ValueError('Number must be finite')
    return result


def text_number(value):
    return format(value, 'f').rstrip('0').rstrip('.') if '.' in format(value, 'f') else format(value, 'f')


def validate_sources(rows, cutoff):
    sources = {}
    for row in rows:
        if any(not row[field] for field in SOURCE_FIELDS):
            raise ValueError('Source registry contains an empty required field')
        if any(any(ord(char) < 32 for char in row[field]) for field in SOURCE_FIELDS):
            raise ValueError('Source registry contains control characters')
        identifier = row['source_id']
        if identifier in sources:
            raise ValueError(f'Duplicate source identifier: {identifier}')
        if row['kind'] != 'synthetic':
            raise ValueError('This demo accepts explicitly synthetic sources only')
        published = parse_date(row['published_on'])
        if published > cutoff:
            raise ValueError('Source publication date is after the evaluation date')
        sources[identifier] = row
    return sources


def validate_products(rows, sources, cutoff, max_age_days):
    if max_age_days < 0:
        raise ValueError('max_age_days must be nonnegative')
    duplicates = Counter(row['product_id'] for row in rows)
    accepted, issues = [], []
    for row_number, row in enumerate(rows, 2):
        local = []

        def flag(field, code, message):
            local.append({
                'row_number': str(row_number), 'product_id': row['product_id'],
                'field': field, 'code': code, 'raw_value': row.get(field, ''),
                'message': message,
            })

        for field in PRODUCT_FIELDS:
            if not row[field]:
                flag(field, 'missing', 'Required field is empty')
            elif any(ord(char) < 32 for char in row[field]):
                flag(field, 'control_character', 'Control characters are not permitted')
        if row['product_id'] and duplicates[row['product_id']] > 1:
            flag('product_id', 'duplicate', 'Every occurrence of this identifier is quarantined')
        for field, choices in ALLOWED.items():
            if row[field] and row[field] not in choices:
                flag(field, 'category', 'Value is outside the documented taxonomy')
        fee = None
        for field in ('management_fee_pct', 'min_subscription'):
            if not row[field]:
                continue
            try:
                value = number(row[field])
                if value < 0:
                    raise ValueError('Negative number')
                if field == 'management_fee_pct':
                    fee = value
            except (InvalidOperation, ValueError):
                flag(field, 'numeric', 'Expected a finite, nonnegative number')
        observed = None
        if row['as_of']:
            try:
                observed = parse_date(row['as_of'])
                age = (cutoff - observed).days
                if age < 0:
                    flag('as_of', 'future', 'Observation is after the evaluation date')
                elif age > max_age_days:
                    flag('as_of', 'stale', 'Observation exceeds the configured age limit')
            except ValueError:
                flag('as_of', 'date', 'Expected a valid YYYY-MM-DD date')
        source = sources.get(row['source_id'])
        if row['source_id'] and source is None:
            flag('source_id', 'unknown_source', 'Identifier is absent from the source registry')
        if source is not None and observed is not None:
            if parse_date(source['published_on']) < observed:
                flag('source_id', 'source_timing', 'Source predates the stated observation date')
        if local:
            issues.extend(local)
        else:
            accepted.append({
                **{field: row[field] for field in PRODUCT_FIELDS},
                'management_fee_bps': text_number(fee * Decimal(100)),
                'source_title': source['title'],
                'fixture_locator': source['fixture_locator'],
            })
    return accepted, issues


def summarize(records):
    groups = defaultdict(list)
    for record in records:
        groups[tuple(record[field] for field in GROUP_FIELDS)].append(number(record['management_fee_bps']))
    result = []
    for key, fees in sorted(groups.items()):
        row = dict(zip(GROUP_FIELDS, key))
        row.update(count=str(len(fees)), comparison_status='singleton: no peer statistics')
        row.update({field: '' for field in SUMMARY_FIELDS[-4:]})
        if len(fees) >= 2:
            row.update(
                comparison_status='descriptive comparison only',
                median_fee_bps=text_number(median(fees)),
                min_fee_bps=text_number(min(fees)),
                max_fee_bps=text_number(max(fees)),
                spread_bps=text_number(max(fees) - min(fees)),
            )
        result.append(row)
    return result


def spreadsheet_safe(value):
    value = str(value)
    if value.lstrip().startswith(('=', '+', '-', '@')) or value.startswith(('\t', '\r', '\n')):
        return "'" + value
    return value


def csv_text(fields, rows):
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator='\n')
    writer.writeheader()
    for row in rows:
        writer.writerow({field: spreadsheet_safe(row.get(field, '')) for field in fields})
    return buffer.getvalue()


def html_table(fields, rows):
    header = ''.join(f'<th>{html.escape(field)}</th>' for field in fields)
    body = ''.join('<tr>' + ''.join(f'<td>{html.escape(str(row.get(field, "")))}</td>' for field in fields) + '</tr>' for row in rows)
    return f'<div class="scroll"><table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table></div>'


def make_dashboard(records, issues, summaries, cutoff, max_age_days, input_count):
    counts = f'{input_count} input records; {len(records)} accepted; {input_count - len(records)} quarantined; {len(issues)} findings.'
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Synthetic product benchmark</title><style>
body{{font:16px system-ui,sans-serif;margin:2rem;line-height:1.5;color:#152536}}
table{{border-collapse:collapse;font-size:13px}}th,td{{border:1px solid #bbc8d4;padding:.5rem;text-align:left}}
th{{background:#e9f0f5}}.scroll{{overflow:auto}}.notice{{background:#fff2cc;padding:1rem}}
</style></head><body><h1>Private markets product benchmark</h1>
<p class="notice">Independent educational project. All products, sources, and observations are synthetic.
No affiliation, investment recommendation, compliance approval, or production claim.</p>
<p>Evaluation date: {cutoff.isoformat()}; maximum observation age: {max_age_days} days.</p>
<p>{counts}</p><h2>Comparable cohorts</h2>
<p>Fees are annual stated management fees in basis points, not total costs. One percentage point equals 100 basis points.
Singleton statistics are withheld. Cohort matching does not establish economic equivalence.</p>
{html_table(SUMMARY_FIELDS, summaries)}
<h2>Accepted records and provenance</h2>{html_table(RECORD_FIELDS, records)}
<h2>Quarantined-record findings</h2>{html_table(ISSUE_FIELDS, issues)}
<h2>Review needed before any real-world use</h2><ul>
<li>Product research: verify original disclosures and share-class terms.</li>
<li>Legal/compliance: assess comparison methodology and permitted distribution.</li>
<li>Marketing: review wording and prominence of limitations.</li>
<li>Technology: review ingestion, controls, and spreadsheet/dashboard integration.</li>
</ul><p>These are suggested review functions, not completed approvals or actual relationships.</p></body></html>'''


def review_brief(records, issues, summaries, cutoff, max_age_days, input_count):
    codes = Counter(issue['code'] for issue in issues)
    finding_lines = '\n'.join(f'- {code}: {count} finding(s)' for code, count in sorted(codes.items())) or '- None'
    comparable = sum(int(row['count']) >= 2 for row in summaries)
    return f'''# Synthetic product-data review brief

Independent educational project; no affiliation or completed stakeholder review.

## Scope and reproducible observations
- Evaluation date: {cutoff.isoformat()}; age limit: {max_age_days} days.
- Input records: {input_count}; accepted: {len(records)}; quarantined: {input_count - len(records)}.
- Cohorts: {len(summaries)}; cohorts with at least two records: {comparable}.
- Findings: {len(issues)}. A record can have multiple findings.

## Findings by category
{finding_lines}

## Proposed follow-up, not completed work
1. Research: resolve quarantined records against original source disclosures.
2. Product: confirm share classes, fee bases, liquidity restrictions, and cohort definitions.
3. Legal/compliance: review comparative claims and distribution requirements.
4. Marketing: review presentation language and limitations.
5. Technology: review refresh controls and CSV/Power BI ingestion.

## Decision boundary
Accepted means passing these mechanical checks, not verified accuracy or approval.
No overall ranking, return forecast, total-cost estimate, or investment recommendation is produced.
Synthetic fixture provenance is not independent evidence. See docs/methodology.md.
'''


def run(products_path, sources_path, output_path, cutoff, max_age_days):
    products_path, sources_path = Path(products_path), Path(sources_path)
    product_bytes, source_bytes = products_path.read_bytes(), sources_path.read_bytes()
    rows = read_table(products_path, PRODUCT_FIELDS)
    sources = validate_sources(read_table(sources_path, SOURCE_FIELDS), cutoff)
    records, issues = validate_products(rows, sources, cutoff, max_age_days)
    summaries = summarize(records)
    manifest = {
        'schema_version': 1,
        'independent_project': True,
        'synthetic_data': True,
        'evaluation_date': cutoff.isoformat(),
        'max_age_days': max_age_days,
        'inputs': {
            'products_sha256': hashlib.sha256(product_bytes).hexdigest(),
            'sources_sha256': hashlib.sha256(source_bytes).hexdigest(),
        },
        'counts': {
            'input': len(rows), 'accepted': len(records),
            'quarantined': len(rows) - len(records), 'findings': len(issues),
            'cohorts': len(summaries),
        },
    }
    outputs = {
        'accepted.csv': csv_text(RECORD_FIELDS, records),
        'issues.csv': csv_text(ISSUE_FIELDS, issues),
        'cohorts.csv': csv_text(SUMMARY_FIELDS, summaries),
        'dashboard.html': make_dashboard(records, issues, summaries, cutoff, max_age_days, len(rows)),
        'review.md': review_brief(records, issues, summaries, cutoff, max_age_days, len(rows)),
        'manifest.json': json.dumps(manifest, sort_keys=True, indent=2) + '\n',
    }
    output_path = Path(output_path)
    input_paths = {products_path.resolve(), sources_path.resolve()}
    if any((output_path / name).resolve() in input_paths for name in outputs):
        raise ValueError('Output would overwrite an input file')
    output_path.mkdir(parents=True, exist_ok=True)
    for name, content in outputs.items():
        with (output_path / name).open('w', encoding='utf-8', newline='') as handle:
            handle.write(content)
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--products', default='data/products.csv')
    parser.add_argument('--sources', default='data/sources.csv')
    parser.add_argument('--out', default='build')
    parser.add_argument('--as-of', required=True, help='Explicit YYYY-MM-DD evaluation date')
    parser.add_argument('--max-age-days', type=int, default=180)
    parser.add_argument('--strict', action='store_true', help='Return 1 if any records are quarantined')
    args = parser.parse_args(argv)
    try:
        result = run(args.products, args.sources, args.out, parse_date(args.as_of), args.max_age_days)
    except (ValueError, OSError, csv.Error, UnicodeError) as exc:
        print(f'Input/output error: {exc}', file=sys.stderr)
        return 2
    print(json.dumps(result['counts'], sort_keys=True))
    return 1 if args.strict and result['counts']['quarantined'] else 0


if __name__ == '__main__':
    sys.exit(main())
