"""Generate actionable cleanup recommendations."""
from __future__ import annotations

import time
from typing import List, Optional

from strata import classifier
from strata.models import FileNode, Recommendation, DuplicateGroup

# Files untouched for this long are treated as "old".
OLD_AGE_SECONDS = 365 * 24 * 3600


def recommend_duplicates(groups: List[DuplicateGroup]) -> List[Recommendation]:
    out: List[Recommendation] = []
    for g in groups:
        if g.count < 2:
            continue
        out.append(Recommendation(
            kind="duplicate",
            path=g.paths[0],
            reclaimable=g.wasted_bytes,
            confidence=0.99,
            reason=f"{g.count} identical copies, "
                   f"keep one to reclaim space",
            extra={"copies": g.count, "paths": g.paths},
        ))
    return out


def recommend_caches(root: FileNode) -> List[Recommendation]:
    """Flag dependency/build cache directories."""
    out: List[Recommendation] = []
    for node in root.sorted_children() if root.is_dir else []:
        pass  # placeholder to keep traversal explicit below

    def visit(n: FileNode):
        if not n.is_dir:
            return
        if classifier.is_cache_dir(n.name) and n.path != root.path:
            label = classifier.DEV_DIR_LABELS.get(
                n.name, "regenerable cache/build directory")
            # Caches are almost always safe to delete.
            confidence = 0.9
            if n.name in ("node_modules", "venv", ".venv", "env",
                          "target", "build", "dist"):
                confidence = 0.8
            out.append(Recommendation(
                kind="cache" if n.name not in ("node_modules", "venv",
                                               ".venv", "env") else "dev_dir",
                path=n.path,
                reclaimable=n.size,
                confidence=confidence,
                reason=f"{label} ({n.file_count} files)",
            ))
        for child in n.children.values():
            visit(child)

    visit(root)
    return out


def recommend_large_files(root: FileNode, threshold: int = 50 * 1024 * 1024,
                          limit: int = 20) -> List[Recommendation]:
    """Flag individual files over a size threshold."""
    out = []
    for f in root.iter_files():
        if f.size >= threshold:
            out.append(Recommendation(
                kind="large_file",
                path=f.path,
                reclaimable=f.size,
                confidence=0.5,
                reason=f"single file larger than {threshold // (1024*1024)}MB",
            ))
    out.sort(key=lambda r: -r.reclaimable)
    return out[:limit]


def recommend_old_files(root: FileNode, now: float = None,
                        max_age_seconds: int = OLD_AGE_SECONDS,
                        limit: int = 30) -> List[Recommendation]:
    """Flag files that have not been touched for a long time."""
    if now is None:
        now = time.time()
    out = []
    for f in root.iter_files():
        if f.size == 0:
            continue
        age = now - f.mtime
        if age >= max_age_seconds:
            years = age / (365 * 24 * 3600)
            out.append(Recommendation(
                kind="old_file",
                path=f.path,
                reclaimable=f.size,
                confidence=0.35,
                reason=f"not modified for {years:.1f} years",
            ))
    out.sort(key=lambda r: -r.reclaimable)
    return out[:limit]


def recommend_temp_files(root: FileNode) -> List[Recommendation]:
    out = []
    for f in root.iter_files():
        if classifier.is_temp_file(f.name):
            out.append(Recommendation(
                kind="temp",
                path=f.path,
                reclaimable=f.size,
                confidence=0.85,
                reason="temporary/backup/partial-download file",
            ))
    return out


def recommend_empty_dirs(root: FileNode) -> List[Recommendation]:
    out = []

    def visit(n: FileNode):
        if n.is_dir and n.path != root.path and not n.children:
            out.append(Recommendation(
                kind="empty_dir",
                path=n.path,
                reclaimable=0,
                confidence=0.7,
                reason="empty directory",
            ))
        for child in n.children.values():
            visit(child)

    visit(root)
    return out


def build_recommendations(root: FileNode,
                          groups: Optional[List[DuplicateGroup]] = None,
                          large_threshold: int = 50 * 1024 * 1024,
                          now: float = None) -> List[Recommendation]:
    recs: List[Recommendation] = []
    if groups:
        recs.extend(recommend_duplicates(groups))
    recs.extend(recommend_caches(root))
    recs.extend(recommend_large_files(root, large_threshold))
    recs.extend(recommend_old_files(root, now))
    recs.extend(recommend_temp_files(root))
    recs.extend(recommend_empty_dirs(root))
    recs.sort(key=lambda r: (-r.reclaimable, -r.confidence))
    return recs


def total_reclaimable(recs: List[Recommendation]) -> int:
    """Sum reclaimable bytes, avoiding double counting nested paths.

    Cache/dev directories already account for the files inside them, so
    any file recommendation nested inside a higher directory is skipped.
    """
    dirs = [r for r in recs if r.kind in ("cache", "dev_dir")]
    total = 0
    for r in recs:
        if r.kind in ("cache", "dev_dir", "empty_dir"):
            total += r.reclaimable
            continue
        # Skip file-level items nested inside a counted directory.
        nested = any(r.path.startswith(d.path + "/") for d in dirs)
        if nested:
            continue
        # Duplicate groups: count once per group (paths[0] is the rep).
        total += r.reclaimable
    return total
