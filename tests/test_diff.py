"""Tests for scan diffing."""
import unittest
from strata.scanner import Scanner
from strata.diff import diff_trees, summarize_diff, ScanDiff
from tests.helpers import make_tree, cleanup


class TestDiff(unittest.TestCase):
    def setUp(self):
        self.root = make_tree({
            "a.txt": "x" * 100,
            "b.txt": "y" * 50,
            "c.txt": "z" * 20,
        })

    def tearDown(self):
        cleanup(self.root)

    def _rescan(self):
        return Scanner().scan(self.root)

    def test_identical(self):
        before = self._rescan()
        after = self._rescan()
        d = diff_trees(before, after)
        self.assertEqual(d.net_delta, 0)
        self.assertEqual(d.added, [])
        self.assertEqual(d.removed, [])

    def test_added_file(self):
        before = self._rescan()
        with open(self.root + "/new.txt", "w") as fh:
            fh.write("w" * 30)
        after = self._rescan()
        d = diff_trees(before, after)
        paths = [c.path for c in d.added]
        self.assertIn("new.txt", paths)
        self.assertEqual(d.net_delta, 30)

    def test_removed_file(self):
        import os
        before = self._rescan()
        os.unlink(self.root + "/c.txt")
        after = self._rescan()
        d = diff_trees(before, after)
        paths = [c.path for c in d.removed]
        self.assertIn("c.txt", paths)
        self.assertEqual(d.net_delta, -20)

    def test_grew_file(self):
        before = self._rescan()
        with open(self.root + "/b.txt", "w") as fh:
            fh.write("y" * 90)
        after = self._rescan()
        d = diff_trees(before, after)
        grew = [c for c in d.grew if c.path == "b.txt"]
        self.assertEqual(len(grew), 1)
        self.assertEqual(grew[0].delta, 40)

    def test_shrank_file(self):
        before = self._rescan()
        with open(self.root + "/b.txt", "w") as fh:
            fh.write("y" * 10)
        after = self._rescan()
        d = diff_trees(before, after)
        shrank = [c for c in d.shrank if c.path == "b.txt"]
        self.assertEqual(len(shrank), 1)

    def test_counts(self):
        before = self._rescan()
        with open(self.root + "/new.txt", "w") as fh:
            fh.write("w")
        after = self._rescan()
        d = diff_trees(before, after)
        self.assertEqual(d.files_before, 3)
        self.assertEqual(d.files_after, 4)

    def test_serializable(self):
        d = ScanDiff()
        data = d.to_dict()
        self.assertIn("net_delta", data)

    def test_summarize(self):
        before = self._rescan()
        with open(self.root + "/new.txt", "w") as fh:
            fh.write("w" * 70)
        after = self._rescan()
        summary = summarize_diff(diff_trees(before, after))
        self.assertEqual(summary["added_bytes"], 70)
        self.assertEqual(summary["added_count"], 1)


if __name__ == "__main__":
    unittest.main()
