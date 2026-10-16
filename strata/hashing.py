"""Three-stage duplicate detection.

Hashing every file fully is expensive, so Strata narrows candidates in
stages:

1. group by exact size (different sizes can never be identical),
2. among same-size groups, compare a cheap "head+tail" partial hash,
3. only files that survive both get a full content hash.

This makes duplicate detection nearly free when there are few duplicates
while remaining exact (never a false positive from partial hashing).
"""
from __future__ import annotations

import hashlib
import os
from collections import defaultdict
from typing import Dict, List, Tuple

from strata.models import DuplicateGroup, FileNode

HEAD = 64 * 1024          # first 64 KiB
TAIL = 64 * 1024          # last 64 KiB
SMALL_LIMIT = 128 * 1024  # files smaller than 2*HEAD are just fully hashed


def _read_partial(path: str, size: int) -> bytes:
    """Read the head and tail of a file (or the whole file if small)."""
    with open(path, "rb") as fh:
        if size <= HEAD + TAIL:
            return fh.read()
        head = fh.read(HEAD)
        fh.seek(max(HEAD, size - TAIL))
        tail = fh.read(TAIL)
        return head + b"\x00STRATA_SPLIT\x00" + tail


def _read_full(path: str) -> bytes:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.digest()


def fingerprint_files(abs_root: str, files: List[FileNode]):
    """Annotate file nodes with a full ``hash`` only when they are part of
    a same-size + same-partial-fingerprint collision.

    Returns the list of DuplicateGroup found.
    """
    # Stage 1: group by size.
    by_size: Dict[int, List[FileNode]] = defaultdict(list)
    for f in files:
        if f.size > 0:
            by_size[f.size].append(f)

    size_groups = [g for g in by_size.values() if len(g) > 1]

    # Stage 2: partial hash within each size group.
    partial_groups: List[Tuple[int, List[FileNode]]] = []
    for group in size_groups:
        buckets: Dict[bytes, List[FileNode]] = defaultdict(list)
        for node in group:
            abs_path = os.path.join(abs_root, node.path.replace("/", os.sep))
            try:
                if node.size <= SMALL_LIMIT:
                    fp = hashlib.sha256(_read_partial(abs_path, node.size)).digest()
                else:
                    fp = hashlib.sha256(_read_partial(abs_path, node.size)).digest()
                buckets[fp].append(node)
            except OSError:
                continue
        for nodes in buckets.values():
            if len(nodes) > 1:
                partial_groups.append((group[0].size, nodes))

    # Stage 3: full hash to confirm.
    dup_groups: List[DuplicateGroup] = []
    for size, nodes in partial_groups:
        full_buckets: Dict[str, List[FileNode]] = defaultdict(list)
        for node in nodes:
            abs_path = os.path.join(abs_root, node.path.replace("/", os.sep))
            try:
                digest = _read_full(abs_path)
            except OSError:
                continue
            node.hash = digest.hex()
            full_buckets[node.hash].append(node)
        for h, same in full_buckets.items():
            if len(same) > 1:
                dup_groups.append(DuplicateGroup(
                    hash=h,
                    size=size,
                    paths=sorted(n.path for n in same),
                ))

    dup_groups.sort(key=lambda g: -g.wasted_bytes)
    return dup_groups


def single_file_hash(path: str, block_size: int = 1024 * 1024) -> str:
    """Return the SHA-256 hex digest of a single file."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(block_size), b""):
            h.update(chunk)
    return h.hexdigest()
