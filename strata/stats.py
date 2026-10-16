"""Aggregate statistics over a scanned tree."""
from __future__ import annotations

import time
from collections import defaultdict
from typing import Dict, List, Tuple

from strata import classifier
from strata.models import DuplicateGroup, FileNode, ScanReport


def percentile(sorted_values: List[float], pct: float) -> float:
    """Linear-interpolation percentile of a pre-sorted list."""
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    k = (len(sorted_values) - 1) * pct
    lo = int(k)
    hi = min(lo + 1, len(sorted_values) - 1)
    frac = k - lo
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * frac


def aggregate(root: FileNode, now: float = None) -> Dict[str, object]:
    """Compute category / extension / age / size distributions."""
    if now is None:
        now = time.time()

    categories: Dict[str, int] = defaultdict(int)
    category_sizes: Dict[str, int] = defaultdict(int)
    extensions: Dict[str, int] = defaultdict(int)
    extension_sizes: Dict[str, int] = defaultdict(int)
    languages: Dict[str, int] = defaultdict(int)
    age_buckets: Dict[str, int] = {b: 0 for b in classifier.AGE_ORDER}
    size_buckets: Dict[str, int] = {b: 0 for b in classifier.SIZE_ORDER}
    sizes: List[float] = []

    for f in root.iter_files():
        sizes.append(float(f.size))
        categories[f.category] += 1
        category_sizes[f.category] += f.size
        if f.extension:
            extensions[f.extension] += 1
            extension_sizes[f.extension] += f.size
        if f.language:
            languages[f.language] += 1
        age_buckets[classifier.age_bucket(f.mtime, now)] += 1
        size_buckets[classifier.size_bucket(f.size)] += 1

    sizes.sort()
    stats = {
        "categories": dict(categories),
        "category_sizes": dict(category_sizes),
        "extensions": dict(extensions),
        "extension_sizes": dict(extension_sizes),
        "languages": dict(languages),
        "age_buckets": age_buckets,
        "size_buckets": size_buckets,
        "mean_size": (sum(sizes) / len(sizes)) if sizes else 0.0,
        "median_size": percentile(sizes, 0.5),
        "p95_size": percentile(sizes, 0.95),
        "p99_size": percentile(sizes, 0.99),
    }
    return stats


def largest_files(root: FileNode, n: int = 25) -> List[Dict[str, object]]:
    files = list(root.iter_files())
    files.sort(key=lambda f: -f.size)
    out = []
    for f in files[:n]:
        out.append({
            "path": f.path,
            "name": f.name,
            "size": f.size,
            "category": f.category,
            "extension": f.extension,
            "mtime": f.mtime,
        })
    return out


def top_level_breakdown(root: FileNode) -> List[Tuple[str, int]]:
    """Size of each immediate child of the root, largest first."""
    if not root.is_dir:
        return [(root.name, root.size)]
    return [(c.name, c.size) for c in root.sorted_children()]


def category_summary(root: FileNode) -> List[Dict[str, object]]:
    cat_sizes: Dict[str, int] = defaultdict(int)
    cat_counts: Dict[str, int] = defaultdict(int)
    for f in root.iter_files():
        cat_sizes[f.category] += f.size
        cat_counts[f.category] += 1
    rows = [
        {"category": c, "size": s, "count": cat_counts[c]}
        for c, s in cat_sizes.items()
    ]
    rows.sort(key=lambda r: -r["size"])
    return rows


def build_report(root: FileNode, abs_root: str, scan_seconds: float,
                 duplicates: List[DuplicateGroup] = None,
                 hashed: bool = False,
                 errors: List[str] = None,
                 include_tree: bool = True) -> ScanReport:
    agg = aggregate(root)
    dups = duplicates or []
    report = ScanReport(
        root=abs_root,
        root_name=root.name,
        total_size=root.size,
        file_count=root.file_count,
        dir_count=root.dir_count,
        scan_time=scan_seconds,
        scanned_at=time.time(),
        hashed=hashed,
        categories=agg["categories"],
        category_sizes=agg["category_sizes"],
        extensions=agg["extensions"],
        extension_sizes=agg["extension_sizes"],
        languages=agg["languages"],
        largest_files=largest_files(root),
        duplicates=[d.to_dict() for d in dups],
        duplicate_waste=sum(d.wasted_bytes for d in dups),
        age_buckets=agg["age_buckets"],
        size_buckets=agg["size_buckets"],
        errors=errors or [],
    )
    if include_tree:
        report.tree = root.to_dict()
    return report
