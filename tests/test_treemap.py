"""Tests for the squarified treemap and sunburst layouts."""
import unittest
from strata.treemap import squarify, treemap_nodes, sunburst, _worst_ratio
from strata.models import FileNode


def area(rect):
    return rect[2] * rect[3]


class TestSquarify(unittest.TestCase):
    def test_single_item_fills_rect(self):
        tiles = squarify([("a", 100.0)], (0, 0, 100, 100))
        self.assertEqual(len(tiles), 1)
        name, rect = tiles[0]
        self.assertEqual(name, "a")
        self.assertAlmostEqual(area(rect), 10000.0, places=3)

    def test_proportional_areas(self):
        items = [("a", 3.0), ("b", 2.0), ("c", 1.0)]
        tiles = squarify(items, (0, 0, 120, 100))
        total = 120 * 100
        by_name = {n: r for n, r in tiles}
        for name, weight in items:
            expected = total * weight / 6.0
            self.assertAlmostEqual(area(by_name[name]), expected, places=1)

    def test_tiles_within_bounds(self):
        items = [(f"f{i}", float(i + 1)) for i in range(10)]
        tiles = squarify(items, (0, 0, 300, 200))
        for _, (x, y, w, h) in tiles:
            self.assertGreaterEqual(x, 0)
            self.assertGreaterEqual(y, 0)
            self.assertLessEqual(x + w, 300.0 + 1e-6)
            self.assertLessEqual(y + h, 200.0 + 1e-6)
            self.assertGreater(w, 0)
            self.assertGreater(h, 0)

    def test_no_overlap(self):
        # Tiles should not overlap (checked with a coarse grid sample).
        items = [(f"f{i}", float(i + 1) ** 2) for i in range(7)]
        tiles = squarify(items, (0, 0, 100, 100))
        for i in range(len(tiles)):
            for j in range(i + 1, len(tiles)):
                _, a = tiles[i]
                _, b = tiles[j]
                # overlap if interiors intersect
                ox = min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0])
                oy = min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1])
                self.assertFalse(ox > 0.5 and oy > 0.5,
                                 f"tiles overlap: {tiles[i]} {tiles[j]}")

    def test_zero_weights_ignored(self):
        tiles = squarify([("a", 5.0), ("b", 0.0), ("c", 3.0)],
                         (0, 0, 100, 100))
        names = {n for n, _ in tiles}
        self.assertNotIn("b", names)
        self.assertEqual(len(tiles), 2)

    def test_empty(self):
        self.assertEqual(squarify([], (0, 0, 100, 100)), [])

    def test_worst_ratio_better_for_balanced(self):
        # a single tile that exactly fills a square side gives ratio 1.0
        self.assertAlmostEqual(_worst_ratio([100.0], 10.0), 1.0,
                               places=2)

    def test_equal_items_are_squareish(self):
        items = [(f"f{i}", 1.0) for i in range(4)]
        tiles = squarify(items, (0, 0, 100, 100))
        for _, rect in tiles:
            ar = max(rect[2] / rect[3], rect[3] / rect[2])
            self.assertLess(ar, 1.2)  # 4 equal tiles tile the square nicely


def _make_tree():
    root = FileNode(path="root", name="root", is_dir=True)
    a = FileNode(path="a", name="a", is_dir=True, size=60, file_count=2)
    f1 = FileNode(path="a/f1.txt", name="f1.txt", is_dir=False,
                  size=40, category="docs")
    f2 = FileNode(path="a/f2.py", name="f2.py", is_dir=False,
                  size=20, category="code")
    a.children = {"f1.txt": f1, "f2.py": f2}
    b = FileNode(path="b.txt", name="b.txt", is_dir=False,
                 size=40, category="docs")
    root.children = {"a": a, "b.txt": b}
    root.size = 100
    root.file_count = 3
    return root


class TestHierarchicalTreemap(unittest.TestCase):
    def test_depth_1_aggregates_dir(self):
        root = _make_tree()
        rects = treemap_nodes(root, (0, 0, 100, 100), max_depth=1)
        names = {r["name"] for r in rects}
        self.assertIn("a", names)
        self.assertIn("b.txt", names)
        # a is rendered as a single aggregated tile at depth 1
        a = next(r for r in rects if r["name"] == "a")
        self.assertTrue(a["is_dir"])

    def test_depth_2_expands_dir(self):
        root = _make_tree()
        rects = treemap_nodes(root, (0, 0, 100, 100), max_depth=2)
        names = {r["name"] for r in rects}
        self.assertIn("f1.txt", names)
        self.assertIn("f2.py", names)
        self.assertIn("b.txt", names)

    def test_area_preserved(self):
        root = _make_tree()
        rects = treemap_nodes(root, (0, 0, 100, 100), max_depth=2)
        total_area = sum(r["w"] * r["h"] for r in rects)
        self.assertAlmostEqual(total_area, 10000.0, places=0)


class TestSunburst(unittest.TestCase):
    def test_root_sector(self):
        root = _make_tree()
        sectors = sunburst(root, 0.3, 0.6, max_depth=2)
        names = {s["name"] for s in sectors}
        self.assertIn("root", names)
        self.assertIn("a", names)
        self.assertIn("b.txt", names)

    def test_angles_ordered(self):
        root = _make_tree()
        sectors = sunburst(root, 0.3, 0.6, max_depth=2)
        root_sector = next(s for s in sectors if s["name"] == "root")
        self.assertAlmostEqual(root_sector["a1"] - root_sector["a0"],
                               6.283185307179586, places=3)

    def test_sector_proportional(self):
        root = _make_tree()
        sectors = sunburst(root, 0.3, 0.6, max_depth=1)
        a = next(s for s in sectors if s["name"] == "a")
        b = next(s for s in sectors if s["name"] == "b.txt")
        # a is 60% of size, b is 40%
        self.assertGreater(a["a1"] - a["a0"], b["a1"] - b["a0"])


if __name__ == "__main__":
    unittest.main()
