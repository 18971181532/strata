"""Compare two scans to show growth and churn."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from strata.models import FileNode


@dataclass
class PathChange:
    path: str
    kind: str                 # added | removed | grew | shrank
    size_before: int = 0
    size_after: int = 0

    @property
    def delta(self) -> int:
        return self.size_after - self.size_before

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "kind": self.kind,
            "size_before": self.size_before,
            "size_after": self.size_after,
            "delta": self.delta,
        }


@dataclass
class ScanDiff:
    size_before: int = 0
    size_after: int = 0
    files_before: int = 0
    files_after: int = 0
    added: List[PathChange] = field(default_factory=list)
    removed: List[PathChange] = field(default_factory=list)
    grew: List[PathChange] = field(default_factory=list)
    shrank: List[PathChange] = field(default_factory=list)

    @property
    def net_delta(self) -> int:
        return self.size_after - self.size_before

    def to_dict(self) -> Dict[str, Any]:
        return {
            "size_before": self.size_before,
            "size_after": self.size_after,
            "files_before": self.files_before,
            "files_after": self.files_after,
            "net_delta": self.net_delta,
            "added": [c.to_dict() for c in self.added],
            "removed": [c.to_dict() for c in self.removed],
            "grew": [c.to_dict() for c in self.grew],
            "shrank": [c.to_dict() for c in self.shrank],
        }


def _index_files(root: FileNode) -> Dict[str, FileNode]:
    return {f.path: f for f in root.iter_files()}


def diff_trees(before: FileNode, after: FileNode,
               top: int = 50) -> ScanDiff:
    """Diff two scans at file granularity."""
    before_map = _index_files(before)
    after_map = _index_files(after)

    result = ScanDiff(
        size_before=before.size,
        size_after=after.size,
        files_before=before.file_count,
        files_after=after.file_count,
    )

    for path, node in after_map.items():
        old = before_map.get(path)
        if old is None:
            result.added.append(PathChange(
                path=path, kind="added", size_before=0,
                size_after=node.size))
        elif node.size != old.size:
            if node.size > old.size:
                result.grew.append(PathChange(
                    path=path, kind="grew",
                    size_before=old.size, size_after=node.size))
            else:
                result.shrank.append(PathChange(
                    path=path, kind="shrank",
                    size_before=old.size, size_after=node.size))

    for path, node in before_map.items():
        if path not in after_map:
            result.removed.append(PathChange(
                path=path, kind="removed", size_before=node.size,
                size_after=0))

    result.added.sort(key=lambda c: -c.size_after)
    result.removed.sort(key=lambda c: -c.size_before)
    result.grew.sort(key=lambda c: -c.delta)
    result.shrank.sort(key=lambda c: c.delta)
    result.added = result.added[:top]
    result.removed = result.removed[:top]
    result.grew = result.grew[:top]
    result.shrank = result.shrank[:top]
    return result


def summarize_diff(d: ScanDiff) -> Dict[str, Any]:
    """Compact summary suitable for quick CLI output."""
    return {
        "net_delta": d.net_delta,
        "added_bytes": sum(c.size_after for c in d.added),
        "removed_bytes": sum(c.size_before for c in d.removed),
        "grew_bytes": sum(c.delta for c in d.grew),
        "shrank_bytes": sum(c.delta for c in d.shrank),
        "added_count": len(d.added),
        "removed_count": len(d.removed),
        "changed_count": len(d.grew) + len(d.shrank),
    }
