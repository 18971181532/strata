# Strata — Disk Cartographer

[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Zero Dependencies](https://img.shields.io/badge/dependencies-zero-orange.svg)](#)

**Strata** maps the layers of your disk. Point it at a folder and it builds an
interactive **squarified treemap**, finds **exact duplicate files** with a
fast three-stage hashing pipeline, classifies every file by type, analyzes
age and size distributions, and produces safe, ranked cleanup
recommendations — all with the Python standard library alone, fully offline.

```
strata scan ~/code          #   map a directory, detect duplicates
strata serve ~/code         #   open the interactive treemap
```

## Why Strata?

- A plain `du` gives you a list of numbers; Strata gives you a **map you can
  click into** — every rectangle is sized by bytes and colored by type.
- Duplicate detection is **exact** (SHA-256) yet fast: files are first
  grouped by size, then a cheap head+tail fingerprint, and only collisions
  are fully hashed.
- Cleanup suggestions are **dry-run only** — Strata never deletes anything;
  it shows you what is reclaimable and why.
- See how a project **grows over time** by diffing two scans.

## Features

### Cartography
- **Squarified treemap** (Bruls–Huijing–van Wijk) — tiles sized by bytes,
  kept as close to square as possible for readability
- **Radial sunburst** — concentric rings reveal the depth of large folders
- **Click to drill down** into any directory, with breadcrumb navigation
- Adjustable rendering depth, hover tooltips

### Duplicate detection
- Stage 1: group by exact size
- Stage 2: head+tail partial fingerprint (64 KiB each)
- Stage 3: full SHA-256 to confirm — zero false positives
- Wasted-space accounting per group and overall

### Classification & analytics
- 40+ types across code, web, data, docs, image, audio, video, archives,
  binaries, fonts and config
- File-age buckets (7 days → 1+ year) and size buckets
- Median / P95 / P99 file size, category and language breakdown
- Largest-files leaderboard

### Cleanup recommendations
- Duplicate groups, regenerable caches (`node_modules`, `__pycache__`,
  virtualenvs, build output), large files, stale files, temp/partial
  downloads, empty directories
- Each suggestion carries a confidence score and reason
- Reclaimable total is computed without double-counting nested folders

### Change tracking
- `strata diff` compares the current tree to the last scan: added, removed,
  grown and shrunk files with net delta

### Engineering
- Zero third-party dependencies, pure standard library
- Atomic, crash-safe JSON snapshots in `.strata/`
- CLI with JSON output for scripting

## Quick start

```bash
pip install -e .

strata scan /path/to/map
strata serve /path/to/map --port 8850
# open http://127.0.0.1:8850
```

## CLI

```
strata scan PATH [--no-hash] [--json]   # build & save a snapshot
strata report [PATH] [--json]           # summarize a saved scan
strata dupes [PATH] [--json]            # list duplicate groups
strata big [PATH] [-n N] [--json]       # largest files
strata clean [PATH] [--threshold-mb M]  # cleanup suggestions (dry-run)
strata diff [PATH] [--json]             # changes since the last scan
strata serve [PATH] [--port 8850]       # interactive dashboard
```

## Example

```
$ strata scan ~/project
==========================================================
  STRATA — Scan
==========================================================
  Root:       /home/me/project
  Files:      1,284
  Total size: 186.4MB
  Scan time:  0.42s
  Duplicates: 7 groups, 12.3MB wasted

  By category:
    code       ████████████████ 82.1MB
    node_modules ...
```

## Architecture

```
strata/
├── scanner.py       # walk the tree, post-order size aggregation
├── hashing.py       # size -> partial -> full SHA-256 dedup
├── classifier.py    # type mapping, cache dirs, age/size buckets
├── stats.py         # aggregates, percentiles, largest files
├── treemap.py       # squarified treemap + sunburst layout
├── recommender.py   # ranked, non-destructive cleanup advice
├── diff.py          # snapshot-to-snapshot change detection
├── storage.py       # atomic JSON persistence
├── engine.py        # orchestration
├── cli.py           # scan/report/dupes/big/clean/diff/serve
├── server.py        # ThreadingHTTPServer REST API
└── web/             # zero-dependency Canvas 2D dashboard
```

### The squarified treemap

Given a rectangle and a list of weighted items, a naive strip layout
produces long, thin rectangles that are hard to read. The squarified
algorithm greedily adds items to the current row while the *worst aspect
ratio* in that row keeps improving, then starts a new row along the
shortest remaining side. The result is a tiling whose cells are as close
to square as possible while preserving exact area proportions. Strata
applies this recursively down the directory tree to a chosen depth.

### Why three-stage hashing is fast

Hashing a 10 GB photo library fully is wasteful when almost every file is
unique. Two files can only be identical if they have the same byte size,
so the vast majority are discarded immediately. A 128 KiB head+tail
fingerprint then catches almost all remaining non-duplicates, and full
hashing runs only on the small collision set — while remaining exact.

## Programmatic API

```python
from strata.engine import StrataEngine
from strata.treemap import treemap_nodes

eng = StrataEngine("/path/to/map")
report = eng.scan()
print(report.file_count, report.total_size)

for rec in eng.recommendations():
    print(rec.kind, rec.path, rec.reclaimable)

tiles = treemap_nodes(eng.tree, (0, 0, 1000, 1000), max_depth=2)
```

## Design principles

- **Zero dependencies** — standard library only.
- **Read-only** — scanning never modifies your files; cleanup is always
  advisory.
- **Local & private** — nothing leaves the machine.
- **Exact** — duplicate detection never produces a false positive.
- **Crash-safe** — snapshots are written atomically.

## License

MIT — see [LICENSE](LICENSE).
