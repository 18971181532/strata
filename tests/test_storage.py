"""Tests for persistent storage."""
import os
import unittest
from strata.scanner import Scanner
from strata.stats import build_report
from strata import storage
from tests.helpers import make_tree, cleanup


class TestStorage(unittest.TestCase):
    def setUp(self):
        self.root = make_tree({
            "a.py": "x" * 100,
            "lib/b.js": "y" * 50,
        })
        self.tree = Scanner().scan(self.root)

    def tearDown(self):
        cleanup(self.root)

    def test_save_report(self):
        report = build_report(self.tree, self.root, 0.1)
        ddir = storage.save_report(report, self.root)
        self.assertTrue(os.path.isdir(ddir))
        self.assertTrue(storage.report_exists(self.root))

    def test_load_report(self):
        report = build_report(self.tree, self.root, 0.1)
        storage.save_report(report, self.root)
        loaded = storage.load_report(self.root)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.file_count, 2)

    def test_load_missing(self):
        self.assertIsNone(storage.load_report(self.root))

    def test_load_with_tree(self):
        report = build_report(self.tree, self.root, 0.1)
        storage.save_report(report, self.root)
        tree = storage.load_tree(self.root)
        self.assertIsNotNone(tree)
        self.assertEqual(tree.file_count, 2)
        self.assertIn("lib", tree.children)

    def test_delete(self):
        report = build_report(self.tree, self.root, 0.1)
        storage.save_report(report, self.root)
        self.assertTrue(storage.delete_data(self.root))
        self.assertFalse(storage.report_exists(self.root))

    def test_delete_missing(self):
        self.assertFalse(storage.delete_data(self.root))

    def test_atomic_overwrite(self):
        report = build_report(self.tree, self.root, 0.1)
        storage.save_report(report, self.root)
        report.total_size = 999
        storage.save_report(report, self.root)
        loaded = storage.load_report(self.root)
        self.assertEqual(loaded.total_size, 999)


if __name__ == "__main__":
    unittest.main()
