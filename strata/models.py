"""Data models for Strata."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# File tree
# ---------------------------------------------------------------------------

@dataclass
class FileNode:
    """A file or directory in the scanned tree.

    For directories, ``size`` and ``file_count`` are the post-order
    aggregates of the whole subtree.
    """
    path: str                       # path relative to scan root, "/" separators
    name: str
    is_dir: bool
    size: int = 0
    mtime: float = 0.0
    extension: str = ""
    category: str = "other"
    language: str = ""
    file_count: int = 0
    dir_count: int = 0
    depth: int = 0
    hash: Optional[str] = None
    error: Optional[str] = None
    children: Dict[str, "FileNode"] = field(default_factory=dict)

    # -- serialization ------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "path": self.path,
            "name": self.name,
            "is_dir": self.is_dir,
            "size": self.size,
            "mtime": self.mtime,
            "extension": self.extension,
            "category": self.category,
            "language": self.language,
            "file_count": self.file_count,
            "dir_count": self.dir_count,
            "depth": self.depth,
        }
        if self.hash:
            data["hash"] = self.hash
        if self.error:
            data["error"] = self.error
        if self.is_dir:
            data["children"] = [c.to_dict() for c in
                                sorted(self.children.values(),
                                       key=lambda n: -n.size)]
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FileNode":
        node = cls(
            path=data["path"],
            name=data["name"],
            is_dir=data["is_dir"],
            size=data.get("size", 0),
            mtime=data.get("mtime", 0.0),
            extension=data.get("extension", ""),
            category=data.get("category", "other"),
            language=data.get("language", ""),
            file_count=data.get("file_count", 0),
            dir_count=data.get("dir_count", 0),
            depth=data.get("depth", 0),
            hash=data.get("hash"),
            error=data.get("error"),
        )
        for child in data.get("children", []):
            c = cls.from_dict(child)
            node.children[c.name] = c
        return node

    # -- convenience --------------------------------------------------------
    def iter_files(self):
        """Yield every file node in this subtree (depth-first)."""
        if not self.is_dir:
            yield self
            return
        for child in self.children.values():
            yield from child.iter_files()

    def sorted_children(self) -> List["FileNode"]:
        return sorted(self.children.values(), key=lambda n: -n.size)


# ---------------------------------------------------------------------------
# Duplicates & recommendations
# ---------------------------------------------------------------------------

@dataclass
class DuplicateGroup:
    """A set of identical files (same content hash)."""
    hash: str
    size: int
    paths: List[str] = field(default_factory=list)

    @property
    def wasted_bytes(self) -> int:
        """Bytes reclaimable by keeping one copy."""
        return self.size * (len(self.paths) - 1)

    @property
    def count(self) -> int:
        return len(self.paths)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hash": self.hash,
            "size": self.size,
            "count": self.count,
            "wasted_bytes": self.wasted_bytes,
            "paths": self.paths,
        }


@dataclass
class Recommendation:
    """A cleanup suggestion."""
    kind: str                 # duplicate | large_file | old_file | cache | temp | empty_dir | dev_dir
    path: str
    reclaimable: int
    confidence: float         # 0..1
    reason: str
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "kind": self.kind,
            "path": self.path,
            "reclaimable": self.reclaimable,
            "confidence": round(self.confidence, 3),
            "reason": self.reason,
        }
        if self.extra:
            d["extra"] = self.extra
        return d


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

@dataclass
class ScanReport:
    root: str
    root_name: str
    total_size: int = 0
    file_count: int = 0
    dir_count: int = 0
    scan_time: float = 0.0
    scanned_at: float = 0.0
    hashed: bool = False
    categories: Dict[str, int] = field(default_factory=dict)
    category_sizes: Dict[str, int] = field(default_factory=dict)
    extensions: Dict[str, int] = field(default_factory=dict)
    extension_sizes: Dict[str, int] = field(default_factory=dict)
    languages: Dict[str, int] = field(default_factory=dict)
    largest_files: List[Dict[str, Any]] = field(default_factory=list)
    duplicates: List[Dict[str, Any]] = field(default_factory=list)
    duplicate_waste: int = 0
    age_buckets: Dict[str, int] = field(default_factory=dict)
    size_buckets: Dict[str, int] = field(default_factory=dict)
    tree: Optional[Dict[str, Any]] = None
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "root": self.root,
            "root_name": self.root_name,
            "total_size": self.total_size,
            "file_count": self.file_count,
            "dir_count": self.dir_count,
            "scan_time": self.scan_time,
            "scanned_at": self.scanned_at,
            "hashed": self.hashed,
            "categories": self.categories,
            "category_sizes": self.category_sizes,
            "extensions": self.extensions,
            "extension_sizes": self.extension_sizes,
            "languages": self.languages,
            "largest_files": self.largest_files,
            "duplicates": self.duplicates,
            "duplicate_waste": self.duplicate_waste,
            "age_buckets": self.age_buckets,
            "size_buckets": self.size_buckets,
            "tree": self.tree,
            "errors": self.errors,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScanReport":
        return cls(**{k: v for k, v in data.items()
                      if k in cls.__dataclass_fields__})
