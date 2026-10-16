"""High-level orchestration: scan a root and produce a report."""
from __future__ import annotations

import os
import time
from typing import List, Optional, Tuple

from strata import storage
from strata.hashing import fingerprint_files
from strata.models import (DuplicateGroup, FileNode, Recommendation,
                           ScanReport)
from strata.recommender import build_recommendations
from strata.scanner import Scanner
from strata.stats import build_report


class StrataEngine:
    def __init__(self, root: str):
        self.root = os.path.abspath(root)
        self.tree: Optional[FileNode] = None
        self.report: Optional[ScanReport] = None
        self.duplicates = []

    def scan(self, hash_files: bool = True,
             max_depth: Optional[int] = None,
             persist: bool = True) -> ScanReport:
        if not os.path.exists(self.root):
            raise FileNotFoundError(f"path not found: {self.root}")

        scanner = Scanner(max_depth=max_depth)
        tree = scanner.scan(self.root)

        dups = []
        if hash_files and tree.file_count > 0:
            files = list(tree.iter_files())
            dups = fingerprint_files(self.root, files)
        self.duplicates = dups

        report = build_report(
            tree, self.root,
            getattr(scanner, "_scan_seconds", 0.0),
            duplicates=dups,
            hashed=hash_files,
            errors=scanner.errors,
            include_tree=True,
        )
        self.tree = tree
        self.report = report

        if persist:
            storage.save_report(report, self.root)
        return report

    def load(self) -> Optional[ScanReport]:
        report = storage.load_report(self.root, with_tree=True)
        if report is not None:
            self.report = report
            # Reconstruct DuplicateGroup objects from the persisted dicts so
            # recommendation generation still includes duplicates.
            self.duplicates = [
                DuplicateGroup(
                    hash=d["hash"], size=d["size"], paths=list(d["paths"]))
                for d in report.duplicates
            ]
            if report.tree is not None:
                self.tree = FileNode.from_dict(report.tree)
        return report

    def recommendations(self,
                        large_threshold: int = 50 * 1024 * 1024
                        ) -> List[Recommendation]:
        if self.tree is None:
            self.load()
        if self.tree is None:
            return []
        return build_recommendations(self.tree, self.duplicates,
                                     large_threshold)

    def ensure(self) -> ScanReport:
        if self.report is None:
            existing = storage.load_report(self.root)
            if existing is not None:
                return self.load()
            return self.scan()
        return self.report
