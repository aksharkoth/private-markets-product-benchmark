import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def invoke(self, output, *extra):
        return subprocess.run(
            [sys.executable, str(ROOT / 'benchmark.py'), '--as-of', '2026-10-09', '--out', str(output), *extra],
            cwd=ROOT, capture_output=True, text=True, check=False,
        )

    def test_end_to_end_reproducible_outputs_and_input_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            first, second = Path(tmp) / 'first', Path(tmp) / 'second'
            result = self.invoke(first)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(self.invoke(second).returncode, 0)
            names = {'accepted.csv', 'issues.csv', 'cohorts.csv', 'dashboard.html', 'review.md', 'manifest.json'}
            self.assertEqual({path.name for path in first.iterdir()}, names)
            for name in names:
                self.assertEqual((first / name).read_bytes(), (second / name).read_bytes())
            manifest = json.loads((first / 'manifest.json').read_text(encoding='utf-8'))
            self.assertEqual(manifest['counts'], {'input': 8, 'accepted': 5, 'quarantined': 3, 'findings': 3, 'cohorts': 4})
            expected = hashlib.sha256((ROOT / 'data/products.csv').read_bytes()).hexdigest()
            self.assertEqual(manifest['inputs']['products_sha256'], expected)
            self.assertIn('Independent educational project', (first / 'dashboard.html').read_text(encoding='utf-8'))

    def test_strict_returns_one_but_retains_review_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'strict'
            result = self.invoke(output, '--strict')
            self.assertEqual(result.returncode, 1)
            self.assertTrue((output / 'issues.csv').exists())

    def test_input_failure_has_no_new_output_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'failed'
            result = self.invoke(output, '--products', str(Path(tmp) / 'absent.csv'))
            self.assertEqual(result.returncode, 2)
            self.assertIn('Input/output error', result.stderr)
            self.assertFalse(output.exists())

    def test_invalid_parameters_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            for flags in [('--as-of', '2026-02-30'), ('--max-age-days', '-1')]:
                with self.subTest(flags=flags):
                    result = self.invoke(Path(tmp) / 'out', *flags)
                    self.assertEqual(result.returncode, 2)
                    self.assertFalse((Path(tmp) / 'out').exists())

    def test_empty_product_file_runs_without_fake_peers(self):
        with tempfile.TemporaryDirectory() as tmp:
            header = (ROOT / 'data/products.csv').read_text(encoding='utf-8').splitlines()[0]
            products = Path(tmp) / 'empty.csv'
            products.write_text(header + '\n', encoding='utf-8')
            output = Path(tmp) / 'out'
            result = self.invoke(output, '--products', str(products), '--strict')
            self.assertEqual(result.returncode, 0, result.stderr)
            counts = json.loads(result.stdout)
            self.assertEqual(counts['input'], 0)
            self.assertEqual(counts['cohorts'], 0)


if __name__ == '__main__':
    unittest.main()
