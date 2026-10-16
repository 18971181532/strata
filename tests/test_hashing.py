"""Tests for three-stage duplicate detection."""
import os
import unittest
from strata.scanner import Scanner
from strata.hashing import fingerprint_files, single_file_hash
from tests.helpers import make_tree, cleanup, write_file


CONTENT_A = "the quick brown fox jumps over the lazy dog\n" * 50
CONTENT_B = "completely different content for a unique file\n" * 40
CONTENT_C = "x" * 200000  # large file (> 128KB)


class TestHashing(unittest.TestCase):
    def setUp(self):
        self.root = make_tree({
            "a.txt": CONTENT_A,
            "copy_a.txt": CONTENT_A,
            "subdir/a_again.txt": CONTENT_A,
            "b.txt": CONTENT_B,
            "big1.bin": CONTENT_C,
            "big2.bin": CONTENT_C,
        })

    def tearDown(self):
        cleanup(self.root)

    def test_detects_small_duplicates(self):
        tree = Scanner().scan(self.root)
        files = list(tree.iter_files())
        groups = fingerprint_files(self.root, files)
        paths = {p for g in groups for p in g.paths}
        self.assertIn("a.txt", paths)
        self.assertIn("copy_a.txt", paths)
        self.assertIn("subdir/a_again.txt", paths)

    def test_detects_large_duplicates(self):
        tree = Scanner().scan(self.root)
        files = list(tree.iter_files())
        groups = fingerprint_files(self.root, files)
        paths = {p for g in groups for p in g.paths}
        self.assertIn("big1.bin", paths)
        self.assertIn("big2.bin", paths)

    def test_unique_not_flagged(self):
        tree = Scanner().scan(self.root)
        files = list(tree.iter_files())
        groups = fingerprint_files(self.root, files)
        for g in groups:
            self.assertNotIn("b.txt", g.paths)

    def test_wasted_bytes(self):
        tree = Scanner().scan(self.root)
        files = list(tree.iter_files())
        groups = fingerprint_files(self.root, files)
        # group of 3 small duplicates
        small = next(g for g in groups if g.size == len(CONTENT_A.encode()))
        self.assertEqual(small.count, 3)
        self.assertEqual(small.wasted_bytes, len(CONTENT_A.encode()) * 2)

    def test_group_sorted_by_waste(self):
        tree = Scanner().scan(self.root)
        files = list(tree.iter_files())
        groups = fingerprint_files(self.root, files)
        wastes = [g.wasted_bytes for g in groups]
        self.assertEqual(wastes, sorted(wastes, reverse=True))

    def test_hashes_assigned(self):
        tree = Scanner().scan(self.root)
        files = list(tree.iter_files())
        fingerprint_files(self.root, files)
        dupes = [f for f in files if f.hash]
        self.assertGreaterEqual(len(dupes), 5)

    def test_no_false_positive_different_same_size(self):
        # same size but different content must not group together
        root = make_tree({
            "x.txt": "a" * 1000,
            "y.txt": "b" * 1000,
        })
        try:
            tree = Scanner().scan(root)
            groups = fingerprint_files(root, list(tree.iter_files()))
            self.assertEqual(groups, [])
        finally:
            cleanup(root)

    def test_single_file_hash_stable(self):
        tree = Scanner().scan(self.root)
        p1 = os.path.join(self.root, "a.txt")
        p2 = os.path.join(self.root, "copy_a.txt")
        self.assertEqual(single_file_hash(p1), single_file_hash(p2))


if __name__ == "__main__":
    unittest.main()
