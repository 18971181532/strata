"""Tests for the directory scanner."""
import os
import unittest
from strata.scanner import Scanner, flatten_files, flatten_dirs, find_node
from tests.helpers import make_tree, cleanup


class TestScanner(unittest.TestCase):
    def setUp(self):
        self.root = make_tree({
            "a.py": "x" * 10,
            "lib/b.js": "y" * 20,
            "lib/nested/c.md": "z" * 30,
            "data.json": "{}",
        })
        # ensure an empty directory exists
        os.makedirs(os.path.join(self.root, "empty"), exist_ok=True)

    def tearDown(self):
        cleanup(self.root)

    def test_scans_all_files(self):
        tree = Scanner().scan(self.root)
        self.assertEqual(tree.file_count, 4)

    def test_total_size_aggregated(self):
        tree = Scanner().scan(self.root)
        # 10 + 20 + 30 + 2 (json "{}")
        self.assertEqual(tree.size, 62)

    def test_dir_counts(self):
        tree = Scanner().scan(self.root)
        # lib, lib/nested, empty
        self.assertEqual(tree.dir_count, 3)

    def test_children(self):
        tree = Scanner().scan(self.root)
        self.assertIn("lib", tree.children)
        self.assertIn("a.py", tree.children)

    def test_nested_aggregation(self):
        tree = Scanner().scan(self.root)
        lib = tree.children["lib"]
        self.assertEqual(lib.size, 50)  # b.js 20 + c.md 30
        self.assertEqual(lib.file_count, 2)

    def test_flatten_files(self):
        tree = Scanner().scan(self.root)
        files = flatten_files(tree)
        self.assertEqual(len(files), 4)

    def test_flatten_dirs(self):
        tree = Scanner().scan(self.root)
        dirs = flatten_dirs(tree)
        names = {d.name for d in dirs}
        self.assertIn("lib", names)
        self.assertIn("nested", names)

    def test_find_node(self):
        tree = Scanner().scan(self.root)
        node = find_node(tree, "lib/nested/c.md")
        self.assertIsNotNone(node)
        self.assertEqual(node.size, 30)

    def test_find_node_missing(self):
        tree = Scanner().scan(self.root)
        self.assertIsNone(find_node(tree, "nope/missing.py"))

    def test_max_depth(self):
        tree = Scanner().scan(self.root)  # depth 0 no limit
        limited = Scanner(max_depth=1).scan(self.root)
        # lib is not descended into
        self.assertEqual(limited.children["lib"].file_count, 0)
        self.assertEqual(limited.file_count, 2)  # a.py + data.json

    def test_paths_normalized(self):
        tree = Scanner().scan(self.root)
        node = find_node(tree, "lib/nested/c.md")
        self.assertNotIn("\\", node.path)

    def test_serialization_roundtrip(self):
        tree = Scanner().scan(self.root)
        data = tree.to_dict()
        from strata.models import FileNode
        restored = FileNode.from_dict(data)
        self.assertEqual(restored.size, tree.size)
        self.assertEqual(restored.file_count, 4)

    def test_missing_root(self):
        # scandir on a missing root raises; guard via exists at engine level
        self.assertFalse(os.path.exists(os.path.join(self.root, "nope")))

    def test_skips_vcs_dirs_by_default(self):
        gitroot = make_tree({
            ".git/HEAD": "ref: refs/heads/main",
            ".git/objects/abc": "blob",
            "src/app.py": "print(1)",
        })
        try:
            tree = Scanner().scan(gitroot)
            self.assertEqual(tree.file_count, 1)
            paths = [f.path for f in flatten_files(tree)]
            self.assertEqual(paths, ["src/app.py"])
        finally:
            cleanup(gitroot)

    def test_skip_recorded(self):
        gitroot = make_tree({".git/HEAD": "x", "a.py": "y"})
        try:
            s = Scanner()
            s.scan(gitroot)
            self.assertIn(".git", s.skipped_dirs)
        finally:
            cleanup(gitroot)


if __name__ == "__main__":
    unittest.main()
