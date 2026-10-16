"""Tests for cleanup recommendations."""
import time
import unittest
from strata.scanner import Scanner
from strata.recommender import (
    recommend_duplicates, recommend_caches, recommend_large_files,
    recommend_old_files, recommend_temp_files, recommend_empty_dirs,
    build_recommendations, total_reclaimable,
)
from strata.models import DuplicateGroup
from tests.helpers import make_tree, cleanup


class TestDuplicateRecommendations(unittest.TestCase):
    def test_group(self):
        g = DuplicateGroup(hash="abc", size=100,
                           paths=["a.txt", "b.txt", "c.txt"])
        recs = recommend_duplicates([g])
        self.assertEqual(recs[0].kind, "duplicate")
        self.assertEqual(recs[0].reclaimable, 200)
        self.assertEqual(recs[0].confidence, 0.99)


class TestCacheRecommendations(unittest.TestCase):
    def setUp(self):
        self.root = make_tree({
            "node_modules/pkg/index.js": "x" * 500,
            "src/app.py": "y" * 10,
            "__pycache__/m.cpython.pyc": "z" * 200,
        })
        self.tree = Scanner().scan(self.root)

    def tearDown(self):
        cleanup(self.root)

    def test_flags_node_modules(self):
        recs = recommend_caches(self.tree)
        kinds = {(r.kind, r.path) for r in recs}
        paths = [r.path for r in recs]
        self.assertIn("node_modules", paths)
        self.assertIn("__pycache__", paths)

    def test_reclaimable_size(self):
        recs = recommend_caches(self.tree)
        nm = next(r for r in recs if r.path == "node_modules")
        self.assertEqual(nm.reclaimable, 500)


class TestLargeFiles(unittest.TestCase):
    def setUp(self):
        self.root = make_tree({
            "small.txt": "x",
            "huge.bin": "z" * (60 * 1024),
        })
        self.tree = Scanner().scan(self.root)

    def tearDown(self):
        cleanup(self.root)

    def test_flags_large(self):
        recs = recommend_large_files(self.tree, threshold=50 * 1024)
        paths = [r.path for r in recs]
        self.assertIn("huge.bin", paths)
        self.assertNotIn("small.txt", paths)

    def test_low_confidence(self):
        recs = recommend_large_files(self.tree, threshold=50 * 1024)
        self.assertEqual(recs[0].confidence, 0.5)


class TestOldFiles(unittest.TestCase):
    def test_old_file_flagged(self):
        now = time.time()
        self.root = make_tree({"recent.txt": "new", "old.txt": "ancient"})
        import os
        os.utime(os.path.join(self.root, "old.txt"),
                 (now - 400 * 86400, now - 400 * 86400))
        try:
            tree = Scanner().scan(self.root)
            recs = recommend_old_files(tree, now=now)
            paths = [r.path for r in recs]
            self.assertIn("old.txt", paths)
            self.assertNotIn("recent.txt", paths)
        finally:
            cleanup(self.root)


class TestTempAndEmpty(unittest.TestCase):
    def setUp(self):
        self.root = make_tree({
            "doc.txt.bak": "backup",
            "real.txt": "content",
            "download.crdownload": "partial",
        })
        import os
        os.makedirs(os.path.join(self.root, "emptydir"), exist_ok=True)
        self.tree = Scanner().scan(self.root)

    def tearDown(self):
        cleanup(self.root)

    def test_temp_files(self):
        recs = recommend_temp_files(self.tree)
        paths = [r.path for r in recs]
        self.assertIn("doc.txt.bak", paths)
        self.assertIn("download.crdownload", paths)
        self.assertNotIn("real.txt", paths)

    def test_empty_dirs(self):
        recs = recommend_empty_dirs(self.tree)
        paths = [r.path for r in recs]
        self.assertIn("emptydir", paths)


class TestBuildRecommendations(unittest.TestCase):
    def setUp(self):
        self.root = make_tree({
            "node_modules/a.js": "x" * 300,
            "dup.txt": "same" * 20,
            "dup2.txt": "same" * 20,
            "app.py": "code",
        })
        self.tree = Scanner().scan(self.root)

    def tearDown(self):
        cleanup(self.root)

    def test_sorted_by_impact(self):
        recs = build_recommendations(self.tree, [])
        sizes = [r.reclaimable for r in recs]
        self.assertEqual(sizes, sorted(sizes, reverse=True))

    def test_total_reclaimable_no_double_count(self):
        groups = [DuplicateGroup(
            hash="h", size=80, paths=["dup.txt", "dup2.txt"])]
        recs = build_recommendations(self.tree, groups)
        total = total_reclaimable(recs)
        # Should be positive and finite, not double-counted
        self.assertGreater(total, 0)
        self.assertLessEqual(total, self.tree.size)

    def test_includes_duplicates(self):
        groups = [DuplicateGroup(
            hash="h", size=80, paths=["dup.txt", "dup2.txt"])]
        recs = build_recommendations(self.tree, groups)
        self.assertTrue(any(r.kind == "duplicate" for r in recs))


if __name__ == "__main__":
    unittest.main()
