"""Persistent scan reports under ``.strata/``."""
from __future__ import annotations

import json
import os
import tempfile
from typing import Optional

from strata.models import FileNode, ScanReport

DATA_DIRNAME = ".strata"
REPORT_FILE = "report.json"
TREE_FILE = "tree.json"


def data_dir(root: str) -> str:
    return os.path.join(root, DATA_DIRNAME)


def report_exists(root: str) -> bool:
    return os.path.exists(os.path.join(data_dir(root), REPORT_FILE))


def _atomic_write(path: str, payload: str) -> None:
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def save_report(report: ScanReport, root: str) -> str:
    """Persist the report. Tree is stored separately to keep report small."""
    ddir = data_dir(root)
    os.makedirs(ddir, exist_ok=True)

    tree = report.tree
    report.tree = None
    try:
        _atomic_write(os.path.join(ddir, REPORT_FILE),
                      json.dumps(report.to_dict(), ensure_ascii=False))
        if tree is not None:
            _atomic_write(os.path.join(ddir, TREE_FILE),
                          json.dumps(tree, ensure_ascii=False))
    finally:
        report.tree = tree
    return ddir


def load_report(root: str, with_tree: bool = False) -> Optional[ScanReport]:
    rpath = os.path.join(data_dir(root), REPORT_FILE)
    if not os.path.exists(rpath):
        return None
    with open(rpath, "r", encoding="utf-8") as fh:
        report = ScanReport.from_dict(json.load(fh))
    if with_tree:
        tpath = os.path.join(data_dir(root), TREE_FILE)
        if os.path.exists(tpath):
            with open(tpath, "r", encoding="utf-8") as fh:
                report.tree = json.load(fh)
    return report


def load_tree(root: str) -> Optional[FileNode]:
    report = load_report(root, with_tree=True)
    if report is None or report.tree is None:
        return None
    return FileNode.from_dict(report.tree)


def delete_data(root: str) -> bool:
    ddir = data_dir(root)
    if not os.path.exists(ddir):
        return False
    for fn in (REPORT_FILE, TREE_FILE):
        p = os.path.join(ddir, fn)
        if os.path.exists(p):
            os.unlink(p)
    try:
        os.rmdir(ddir)
    except OSError:
        pass
    return True
