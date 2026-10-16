"""End-to-end tests for the engine and CLI."""
import json
import os
import sys
import unittest
from io import StringIO

from strata.engine import StrataEngine
from strata.cli import build_parser, main
from tests.helpers import make_tree, cleanup


SAMPLE = {
    "app.py": "import os\nimport json\n" + "print('hello')\n" * 20,
    "lib/utils.py": "def helper(): pass\n" * 15,
    "app_copy.py": "import os\nimport json\n" + "print('hello')\n" * 20,
    "README.md": "# App\nA sample project\n" * 10,
    "node_modules/pkg/index.js": "module.exports = {};\n" * 30,
    "data/large.bin": "x" * (60 * 1024),
}


class TestEngine(unittest.TestCase):
    def setUp(self):
        self.root = make_tree(SAMPLE)

    def tearDown(self):
        cleanup(self.root)

    def test_scan(self):
        eng = StrataEngine(self.root)
        report = eng.scan()
        self.assertEqual(report.file_count, 6)
        self.assertGreater(report.total_size, 60 * 1024)

    def test_persists(self):
        eng = StrataEngine(self.root)
        eng.scan()
        self.assertTrue(os.path.isdir(os.path.join(self.root, ".strata")))

    def test_load(self):
        eng = StrataEngine(self.root)
        eng.scan()
        eng2 = StrataEngine(self.root)
        report = eng2.load()
        self.assertIsNotNone(report)
        self.assertEqual(report.file_count, 6)

    def test_duplicates_detected(self):
        eng = StrataEngine(self.root)
        report = eng.scan()
        groups = report.duplicates
        paths = {p for g in groups for p in g["paths"]}
        self.assertIn("app.py", paths)
        self.assertIn("app_copy.py", paths)

    def test_no_hash(self):
        eng = StrataEngine(self.root)
        report = eng.scan(hash_files=False)
        self.assertFalse(report.hashed)
        self.assertEqual(report.duplicates, [])

    def test_recommendations(self):
        eng = StrataEngine(self.root)
        eng.scan()
        recs = eng.recommendations()
        paths = [r.path for r in recs]
        self.assertIn("node_modules", paths)

    def test_missing_root(self):
        eng = StrataEngine(os.path.join(self.root, "nope"))
        with self.assertRaises(FileNotFoundError):
            eng.scan()

    def test_scan_twice_no_rescan(self):
        eng = StrataEngine(self.root)
        eng.scan()
        eng2 = StrataEngine(self.root)
        report = eng2.ensure()
        self.assertEqual(report.file_count, 6)


class TestCLI(unittest.TestCase):
    def setUp(self):
        self.root = make_tree(SAMPLE)

    def tearDown(self):
        cleanup(self.root)

    def _run(self, argv):
        old = sys.stdout
        sys.stdout = StringIO()
        try:
            code = main(argv)
            out = sys.stdout.getvalue()
        finally:
            sys.stdout = old
        return code, out

    def test_parser(self):
        parser = build_parser()
        args = parser.parse_args(["scan", "/tmp"])
        self.assertEqual(args.command, "scan")
        args = parser.parse_args(["serve", "/tmp", "--port", "9999"])
        self.assertEqual(args.port, 9999)

    def test_scan_then_report(self):
        code, out = self._run(["scan", self.root])
        self.assertEqual(code, 0)
        self.assertIn("STRATA", out)
        self.assertIn("Files", out)

        code, out = self._run(["report", self.root])
        self.assertEqual(code, 0)
        self.assertIn("Largest", out)

    def test_scan_json(self):
        code, out = self._run(["scan", "--json", self.root])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["file_count"], 6)

    def test_dupes(self):
        self._run(["scan", self.root])
        code, out = self._run(["dupes", self.root])
        self.assertEqual(code, 0)
        self.assertIn("app.py", out)

    def test_big(self):
        self._run(["scan", self.root])
        code, out = self._run(["big", self.root, "-n", "3"])
        self.assertEqual(code, 0)
        self.assertIn("large.bin", out)

    def test_clean(self):
        self._run(["scan", self.root])
        code, out = self._run(["clean", self.root])
        self.assertEqual(code, 0)
        self.assertIn("node_modules", out)
        self.assertIn("reclaimable", out.lower())

    def test_clean_json(self):
        self._run(["scan", self.root])
        code, out = self._run(["clean", "--json", self.root])
        data = json.loads(out)
        self.assertIn("recommendations", data)
        self.assertGreater(data["estimated_reclaimable"], 0)

    def test_scan_missing(self):
        code, _ = self._run(["scan", "/nonexistent/xyz/12345"])
        self.assertEqual(code, 1)

    def test_report_without_scan(self):
        empty = make_tree({})
        try:
            code, _ = self._run(["report", empty])
            self.assertEqual(code, 1)
        finally:
            cleanup(empty)

    def test_no_command(self):
        code, _ = self._run([])
        self.assertEqual(code, 0)

    def test_version(self):
        parser = build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(["--version"])


if __name__ == "__main__":
    unittest.main()
