"""Tests for aggregation statistics."""
import time
import unittest
from strata.scanner import Scanner
from strata.stats import (
    percentile, aggregate, largest_files, category_summary,
    top_level_breakdown, build_report,
)
from tests.helpers import make_tree, cleanup


class TestPercentile(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(percentile([], 0.5), 0.0)

    def test_single(self):
        self.assertEqual(percentile([42.0], 0.5), 42.0)

    def test_median(self):
        self.assertEqual(percentile([1, 2, 3, 4, 5], 0.5), 3)

    def test_p95(self):
        vals = list(range(1, 101))
        self.assertGreaterEqual(percentile(vals, 0.95), 95)


class TestAggregate(unittest.TestCase):
    def setUp(self):
        now = time.time()
        self.root = make_tree({
            "a.py": "print(1)",
            "b.py": "import os\n" * 10,
            "notes.md": "# title\n",
            "pic.png": b"\x89PNG" * 100,
        })
        self.tree = Scanner().scan(self.root)

    def tearDown(self):
        cleanup(self.root)

    def test_categories(self):
        agg = aggregate(self.tree)
        self.assertEqual(agg["categories"]["code"], 2)
        self.assertEqual(agg["categories"]["docs"], 1)
        self.assertEqual(agg["categories"]["image"], 1)

    def test_extensions(self):
        agg = aggregate(self.tree)
        self.assertEqual(agg["extensions"]["py"], 2)
        self.assertEqual(agg["extensions"]["md"], 1)

    def test_category_sizes(self):
        agg = aggregate(self.tree)
        # image is largest
        self.assertGreater(agg["category_sizes"]["image"],
                           agg["category_sizes"]["code"])

    def test_languages(self):
        agg = aggregate(self.tree)
        self.assertEqual(agg["languages"]["python"], 2)

    def test_size_buckets(self):
        agg = aggregate(self.tree)
        self.assertEqual(sum(agg["size_buckets"].values()), 4)

    def test_age_buckets(self):
        agg = aggregate(self.tree)
        self.assertEqual(sum(agg["age_buckets"].values()), 4)

    def test_mean_median(self):
        agg = aggregate(self.tree)
        self.assertGreater(agg["mean_size"], 0)
        self.assertGreater(agg["median_size"], 0)


class TestLargestAndBreakdown(unittest.TestCase):
    def setUp(self):
        self.root = make_tree({
            "small.txt": "x",
            "big.bin": "z" * 5000,
            "mid.dat": "y" * 500,
        })
        self.tree = Scanner().scan(self.root)

    def tearDown(self):
        cleanup(self.root)

    def test_largest_sorted(self):
        files = largest_files(self.tree, n=2)
        self.assertEqual(files[0]["name"], "big.bin")
        self.assertEqual(files[1]["name"], "mid.dat")

    def test_category_summary(self):
        rows = category_summary(self.tree)
        self.assertTrue(all("size" in r for r in rows))

    def test_top_level_breakdown(self):
        rows = top_level_breakdown(self.tree)
        self.assertEqual(rows[0][0], "big.bin")


class TestBuildReport(unittest.TestCase):
    def setUp(self):
        self.root = make_tree({"a.py": "x" * 100, "b.md": "y" * 20})
        self.tree = Scanner().scan(self.root)

    def tearDown(self):
        cleanup(self.root)

    def test_report_fields(self):
        report = build_report(self.tree, self.root, 0.1)
        self.assertEqual(report.file_count, 2)
        self.assertEqual(report.total_size, 120)
        self.assertIsNotNone(report.tree)
        self.assertIn("categories", report.to_dict())

    def test_report_no_tree(self):
        report = build_report(self.tree, self.root, 0.1, include_tree=False)
        self.assertIsNone(report.tree)

    def test_report_roundtrip(self):
        report = build_report(self.tree, self.root, 0.1)
        data = report.to_dict()
        from strata.models import ScanReport
        restored = ScanReport.from_dict(data)
        self.assertEqual(restored.file_count, 2)


if __name__ == "__main__":
    unittest.main()
