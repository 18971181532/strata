"""Tests for the classifier."""
import time
import unittest
from strata.classifier import (
    classify, is_cache_dir, is_skip_dir, is_temp_file,
    age_bucket, size_bucket, AGE_ORDER, SIZE_ORDER,
)


class TestClassify(unittest.TestCase):
    def test_python(self):
        cat, lang, ext = classify("main.py", False)
        self.assertEqual(cat, "code")
        self.assertEqual(lang, "python")
        self.assertEqual(ext, "py")

    def test_typescript(self):
        cat, lang, _ = classify("App.tsx", False)
        self.assertEqual(cat, "code")
        self.assertEqual(lang, "typescript")

    def test_image(self):
        cat, _, ext = classify("photo.png", False)
        self.assertEqual(cat, "image")
        self.assertEqual(ext, "png")

    def test_archive(self):
        cat, _, _ = classify("bundle.zip", False)
        self.assertEqual(cat, "archive")

    def test_binary(self):
        cat, _, _ = classify("app.exe", False)
        self.assertEqual(cat, "binary")

    def test_special_dockerfile(self):
        cat, lang, _ = classify("Dockerfile", False)
        self.assertEqual(cat, "config")
        self.assertEqual(lang, "docker")

    def test_unknown(self):
        cat, _, ext = classify("file.xyz", False)
        self.assertEqual(cat, "other")
        self.assertEqual(ext, "xyz")

    def test_no_extension(self):
        cat, _, ext = classify("README", False)
        self.assertEqual(cat, "docs")

    def test_directory(self):
        cat, _, _ = classify("src", True)
        self.assertEqual(cat, "dir")

    def test_case_insensitive(self):
        cat, _, _ = classify("PHOTO.PNG", False)
        self.assertEqual(cat, "image")


class TestSpecialDirs(unittest.TestCase):
    def test_cache_dirs(self):
        self.assertTrue(is_cache_dir("node_modules"))
        self.assertTrue(is_cache_dir("__pycache__"))
        self.assertTrue(is_cache_dir(".venv"))
        self.assertFalse(is_cache_dir("src"))

    def test_egg_info(self):
        self.assertTrue(is_cache_dir("mypkg.egg-info"))

    def test_skip_dirs(self):
        self.assertTrue(is_skip_dir(".git"))
        self.assertFalse(is_skip_dir(".github"))

    def test_temp_files(self):
        self.assertTrue(is_temp_file("download.crdownload"))
        self.assertTrue(is_temp_file("notes.txt.bak"))
        self.assertTrue(is_temp_file("~draft"))
        self.assertFalse(is_temp_file("main.py"))


class TestBuckets(unittest.TestCase):
    def test_age_buckets(self):
        now = time.time()
        day = 86400
        self.assertEqual(age_bucket(now - day, now), "last_7_days")
        self.assertEqual(age_bucket(now - day * 10, now), "last_30_days")
        self.assertEqual(age_bucket(now - day * 200, now), "last_year")
        self.assertEqual(age_bucket(now - day * 400, now), "over_a_year")

    def test_age_order_complete(self):
        self.assertEqual(len(AGE_ORDER), 6)

    def test_size_buckets(self):
        self.assertEqual(size_bucket(500), "<1KB")
        self.assertEqual(size_bucket(5 * 1024), "1-10KB")
        self.assertEqual(size_bucket(5 * 1024 * 1024), "1-10MB")
        self.assertEqual(size_bucket(5 * 1024 ** 3), ">1GB")

    def test_size_order_complete(self):
        self.assertEqual(len(SIZE_ORDER), 8)


if __name__ == "__main__":
    unittest.main()
