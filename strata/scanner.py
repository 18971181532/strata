"""Directory scanner: builds the FileNode tree and aggregates sizes."""
from __future__ import annotations

import os
import time
from typing import List, Optional

from strata import classifier
from strata.models import FileNode


class Scanner:
    """Walks a root and produces a FileNode tree with subtree totals."""

    def __init__(self, follow_symlinks: bool = False,
                 include_hidden: bool = True,
                 max_depth: Optional[int] = None,
                 skip_dirs=None):
        self.follow_symlinks = follow_symlinks
        self.include_hidden = include_hidden
        self.max_depth = max_depth
        # VCS / metadata internals are managed by their tools and must never
        # appear as cleanup candidates; skip them by default.
        self.skip_dirs = (classifier.SKIP_DIRS if skip_dirs is None
                          else set(skip_dirs))
        self.errors: List[str] = []
        self.file_count = 0
        self.dir_count = 0
        self.skipped_dirs: List[str] = []

    # ------------------------------------------------------------------
    def scan(self, root: str) -> FileNode:
        root = os.path.abspath(root)
        root_name = os.path.basename(root.rstrip(os.sep)) or root
        start = time.time()
        self.errors = []
        self.file_count = 0
        self.dir_count = 0
        tree = self._walk(root, rel="", name=root_name, depth=0)
        self._scan_seconds = time.time() - start
        return tree

    # ------------------------------------------------------------------
    def _walk(self, abs_path: str, rel: str, name: str, depth: int) -> FileNode:
        try:
            st = os.stat(abs_path)
        except OSError as exc:
            self.errors.append(f"{rel or name}: {exc}")
            return FileNode(path=rel or name, name=name, is_dir=False,
                            error=str(exc), depth=depth)

        is_dir = os.path.isdir(abs_path)
        node = FileNode(
            path=rel or name,
            name=name,
            is_dir=is_dir,
            mtime=st.st_mtime,
            depth=depth,
        )

        if not is_dir:
            cat, lang, ext = classifier.classify(name, False)
            node.size = st.st_size
            node.category = cat
            node.language = lang
            node.extension = ext
            node.file_count = 1
            self.file_count += 1
            return node

        # Directory
        self.dir_count += 1
        if self.max_depth is not None and depth >= self.max_depth:
            return node

        try:
            entries = list(os.scandir(abs_path))
        except OSError as exc:
            self.errors.append(f"{rel or name}: {exc}")
            node.error = str(exc)
            return node

        total_size = 0
        total_files = 0
        total_dirs = 0
        for entry in entries:
            if not self.include_hidden and entry.name.startswith("."):
                continue
            if entry.is_dir(follow_symlinks=False) and \
                    classifier.is_skip_dir(entry.name):
                child_rel = entry.name if not rel else f"{rel}/{entry.name}"
                self.skipped_dirs.append(child_rel)
                continue
            child_rel = entry.name if not rel else f"{rel}/{entry.name}"
            # VCS internals are scanned for size but we still descend to
            # account for them; classifier marks them only by name.
            child = self._walk(entry.path, child_rel, entry.name, depth + 1)
            node.children[entry.name] = child
            total_size += child.size
            total_files += child.file_count
            total_dirs += child.dir_count + (1 if child.is_dir else 0)

        node.size = total_size
        node.file_count = total_files
        node.dir_count = total_dirs
        return node


def flatten_files(root: FileNode) -> List[FileNode]:
    """Return every file node under the tree root."""
    return list(root.iter_files())


def flatten_dirs(root: FileNode) -> List[FileNode]:
    """Return every directory node (including root)."""
    out = []

    def visit(n: FileNode):
        if n.is_dir:
            out.append(n)
            for c in n.children.values():
                visit(c)

    visit(root)
    return out


def find_node(root: FileNode, rel_path: str) -> Optional[FileNode]:
    """Locate a node in the tree by its relative path."""
    if not rel_path or rel_path in ("", ".", root.path):
        return root
    parts = [p for p in rel_path.replace("\\", "/").split("/") if p]
    node = root
    for part in parts:
        if not node.is_dir or part not in node.children:
            return None
        node = node.children[part]
    return node
