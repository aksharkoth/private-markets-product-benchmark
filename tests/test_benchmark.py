import copy
import csv
import io
import tempfile
import unittest
from datetime import date
from pathlib import Path

import benchmark as b

ROOT = Path(__file__).resolve().parents[1]
CUTOFF = date(2026, 10, 9)


class BenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.rows = b.read_table(ROOT / 'data/products.csv', b.PRODUCT_FIELDS)
        self.sources = b.validate_sources(b.read_table(ROOT / 'data/sources.csv', b.SOURCE_FIELDS), CUTOFF)

    def validate_one(self, **changes):
        row = dict(self.rows[0], **changes)
        return b.validate_products([row], self.sources, CUTOFF, 180)

    def test_fixture_counts_and_exact_comparison(self):
        accepted, issues = b.validate_products(self.rows, self.sources, CUTOFF, 180)
        self.assertEqual(len(accepted), 5)
        self.assertEqual({item['code'] for item in issues}, {'stale', 'numeric', 'unknown_source'})
        groups = b.summarize(accepted)
        self.assertEqual(len(groups), 4)
        comparable = [row for row in groups if row['count'] == '2']
        self.assertEqual(len(comparable), 1)
        self.assertEqual(comparable[0]['median_fee_bps'], '137.5')
        self.assertEqual(comparable[0]['spread_bps'], '25')
        self.assertTrue(all(row['median_fee_bps'] == '' for row in groups if row['count'] == '1'))

    def test_all_duplicate_occurrences_are_quarantined(self):
        accepted, issues = b.validate_products([self.rows[0], dict(self.rows[0])], self.sources, CUTOFF, 180)
        self.assertEqual(accepted, [])
        self.assertEqual([row['code'] for row in issues], ['duplicate', 'duplicate'])
        self.assertEqual([row['row_number'] for row in issues], ['2', '3'])

    def test_missing_unknown_and_control_characters(self):
        for field, value, code in [
            ('product_name', '', 'missing'),
            ('strategy', 'unmapped', 'category'),
            ('product_name', 'bad\nname', 'control_character'),
            ('source_id', 'absent', 'unknown_source'),
        ]:
            with self.subTest(field=field, value=value):
                accepted, issues = self.validate_one(**{field: value})
                self.assertFalse(accepted)
                self.assertIn(code, {issue['code'] for issue in issues})

    def test_numeric_edges_and_zero(self):
        for value in ('NaN', 'Infinity', '-1', 'not-a-number'):
            with self.subTest(value=value):
                accepted, issues = self.validate_one(management_fee_pct=value)
                self.assertFalse(accepted)
                self.assertIn('numeric', {issue['code'] for issue in issues})
        accepted, issues = self.validate_one(management_fee_pct='0', min_subscription='0')
        self.assertFalse(issues)
        self.assertEqual(accepted[0]['management_fee_bps'], '0')
        accepted, issues = self.validate_one(min_subscription='-5')
        self.assertFalse(accepted)
        self.assertEqual(issues[0]['field'], 'min_subscription')

    def test_date_edges_and_source_chronology(self):
        for value, code in [('2026-10-10', 'future'), ('2026-02-30', 'date'), ('20260930', 'date')]:
            with self.subTest(value=value):
                accepted, issues = self.validate_one(as_of=value)
                self.assertFalse(accepted)
                self.assertIn(code, {item['code'] for item in issues})
        accepted, issues = b.validate_products([self.rows[0]], self.sources, CUTOFF, 9)
        self.assertEqual(len(accepted), 1)
        accepted, issues = b.validate_products([self.rows[0]], self.sources, CUTOFF, 8)
        self.assertEqual(issues[0]['code'], 'stale')
        accepted, issues = self.validate_one(as_of='2026-10-01')
        self.assertIn('source_timing', {item['code'] for item in issues})
        with self.assertRaises(ValueError):
            b.validate_products([], self.sources, CUTOFF, -1)

    def test_each_cohort_dimension_prevents_pooling(self):
        records, _ = self.validate_one()
        base = records[0]
        alternatives = {
            'strategy': 'real_assets', 'vehicle': 'drawdown', 'currency': 'EUR',
            'fee_basis': 'invested_capital', 'liquidity': 'monthly',
            'investor_segment': 'institutional',
        }
        for field, value in alternatives.items():
            with self.subTest(field=field):
                other = dict(base, product_id='OTHER', **{field: value})
                groups = b.summarize([base, other])
                self.assertEqual(len(groups), 2)
                self.assertTrue(all(group['median_fee_bps'] == '' for group in groups))

    def test_source_registry_rejects_duplicates_and_non_synthetic(self):
        row = dict(self.sources['F01'])
        with self.assertRaises(ValueError):
            b.validate_sources([row, row], CUTOFF)
        with self.assertRaises(ValueError):
            b.validate_sources([dict(row, kind='public')], CUTOFF)
        with self.assertRaises(ValueError):
            b.validate_sources([dict(row, published_on='2026-10-10')], CUTOFF)

    def test_csv_and_html_output_safety(self):
        text = b.csv_text(('name',), [{'name': '=1+1'}, {'name': ' @SUM(A1)'}, {'name': 'ordinary'}])
        rows = list(csv.DictReader(io.StringIO(text)))
        self.assertEqual(rows[0]['name'], "'=1+1")
        self.assertEqual(rows[1]['name'], "' @SUM(A1)")
        self.assertEqual(rows[2]['name'], 'ordinary')
        table = b.html_table(('name',), [{'name': '<script>alert(1)</script>'}])
        self.assertNotIn('<script>', table)
        self.assertIn('&lt;script&gt;', table)

    def test_malformed_tables(self):
        for text in ('x\n1\n', 'product_id,product_id\na,b\n', 'product_id\na,b\n', 'product_id,x\na\n'):
            with self.subTest(text=text), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / 'bad.csv'
                path.write_text(text, encoding='utf-8')
                with self.assertRaises(ValueError):
                    b.read_table(path, ('product_id',))

    def test_empty_data_has_no_invented_statistics(self):
        self.assertEqual(b.validate_products([], self.sources, CUTOFF, 180), ([], []))
        self.assertEqual(b.summarize([]), [])


if __name__ == '__main__':
    unittest.main()
