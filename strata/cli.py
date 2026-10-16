"""Command-line interface for Strata."""
from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional

from strata import __version__, storage
from strata.diff import diff_trees, summarize_diff
from strata.engine import StrataEngine
from strata.format import bar, human_size, time_ago
from strata.recommender import total_reclaimable
from strata.scanner import find_node


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="strata",
        description="Strata — map disk usage, find duplicates & clean up.")
    parser.add_argument("--version", action="version",
                        version=f"strata {__version__}")
    sub = parser.add_subparsers(dest="command")

    p_scan = sub.add_parser("scan", help="scan a directory and save a report")
    p_scan.add_argument("path")
    p_scan.add_argument("--no-hash", action="store_true",
                        help="skip duplicate detection (faster)")
    p_scan.add_argument("--json", action="store_true")

    p_report = sub.add_parser("report", help="show a saved report summary")
    p_report.add_argument("path", nargs="?", default=".")
    p_report.add_argument("--json", action="store_true")

    p_dupes = sub.add_parser("dupes", help="list duplicate files")
    p_dupes.add_argument("path", nargs="?", default=".")
    p_dupes.add_argument("--json", action="store_true")

    p_big = sub.add_parser("big", help="list the largest files")
    p_big.add_argument("path", nargs="?", default=".")
    p_big.add_argument("-n", type=int, default=20)
    p_big.add_argument("--json", action="store_true")

    p_clean = sub.add_parser("clean",
                             help="show cleanup recommendations (no deletion)")
    p_clean.add_argument("path", nargs="?", default=".")
    p_clean.add_argument("--threshold-mb", type=int, default=50)
    p_clean.add_argument("--json", action="store_true")

    p_diff = sub.add_parser("diff", help="compare against a previous scan")
    p_diff.add_argument("path", nargs="?", default=".")
    p_diff.add_argument("--json", action="store_true")

    p_serve = sub.add_parser("serve", help="run the web dashboard")
    p_serve.add_argument("path", nargs="?", default=".")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8850)
    p_serve.add_argument("--no-hash", action="store_true")
    p_serve.add_argument("--rebuild", action="store_true")

    return parser


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _engine(path: str) -> StrataEngine:
    eng = StrataEngine(path)
    report = eng.load()
    if report is None:
        print(f"No saved scan for {path}; scanning now ...", file=sys.stderr)
        eng.scan()
    return eng


def _header(title: str) -> str:
    return ("=" * 58 + f"\n  STRATA — {title}\n" + "=" * 58)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_scan(args) -> int:
    import os
    if not os.path.exists(args.path):
        print(f"error: path not found: {args.path}", file=sys.stderr)
        return 1
    eng = StrataEngine(args.path)
    report = eng.scan(hash_files=not args.no_hash)

    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
        return 0

    print(_header("Scan"))
    print(f"  Root:       {report.root}")
    print(f"  Files:      {report.file_count}")
    print(f"  Dirs:       {report.dir_count}")
    print(f"  Total size: {human_size(report.total_size)}")
    print(f"  Scan time:  {report.scan_time:.2f}s")
    print(f"  Duplicates: {len(report.duplicates)} groups, "
          f"{human_size(report.duplicate_waste)} wasted")
    print("\n  By category:")
    cats = sorted(report.category_sizes.items(), key=lambda kv: -kv[1])
    for cat, size in cats[:12]:
        frac = size / report.total_size if report.total_size else 0
        print(f"    {cat:<10} {bar(frac)} {human_size(size):>9}  "
              f"{report.categories.get(cat, 0)}")
    print(f"\n  Report saved to {storage.data_dir(args.path)}")
    return 0


def cmd_report(args) -> int:
    import os
    if not os.path.exists(args.path):
        print(f"error: path not found: {args.path}", file=sys.stderr)
        return 1
    eng = StrataEngine(args.path)
    report = eng.load()
    if report is None:
        print("no saved scan found. Run 'strata scan' first.",
              file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
        return 0
    print(_header("Report"))
    print(f"  Root:       {report.root}")
    print(f"  Files:      {report.file_count}")
    print(f"  Total size: {human_size(report.total_size)}")
    print(f"  Scanned:    {time_ago(report.scanned_at)} ago")
    print("\n  Largest files:")
    for f in report.largest_files[:10]:
        print(f"    {human_size(f['size']):>9}  {f['path']}")
    return 0


def cmd_dupes(args) -> int:
    eng = _engine(args.path)
    if not eng.report:
        return 1
    groups = eng.report.duplicates
    if args.json:
        print(json.dumps({"groups": groups}, ensure_ascii=False, indent=2))
        return 0
    print(_header("Duplicates"))
    if not groups:
        print("  No duplicate files found.")
        return 0
    total = 0
    for g in groups:
        total += g["wasted_bytes"]
        print(f"\n  {human_size(g['size'])} x{g['count']}  "
              f"wastes {human_size(g['wasted_bytes'])}")
        for p in g["paths"]:
            print(f"    - {p}")
    print(f"\n  Total reclaimable: {human_size(total)}")
    return 0


def cmd_big(args) -> int:
    eng = _engine(args.path)
    if not eng.report:
        return 1
    files = eng.report.largest_files[:args.n]
    if args.json:
        print(json.dumps({"files": files}, ensure_ascii=False, indent=2))
        return 0
    print(_header(f"Top {len(files)} largest files"))
    for f in files:
        print(f"  {human_size(f['size']):>9}  {time_ago(f['mtime']):>4}  "
              f"{f['path']}")
    return 0


def cmd_clean(args) -> int:
    eng = _engine(args.path)
    if eng.tree is None:
        return 1
    threshold = args.threshold_mb * 1024 * 1024
    recs = eng.recommendations(large_threshold=threshold)
    reclaimable = total_reclaimable(recs)
    if args.json:
        print(json.dumps({
            "recommendations": [r.to_dict() for r in recs],
            "estimated_reclaimable": reclaimable,
        }, ensure_ascii=False, indent=2))
        return 0
    print(_header("Cleanup Recommendations"))
    print("  (dry-run — Strata never deletes anything)\n")
    if not recs:
        print("  Nothing to clean up.")
        return 0
    for r in recs[:30]:
        size = human_size(r.reclaimable) if r.reclaimable else "—"
        print(f"  [{r.kind:<10}] {size:>9}  {r.path}")
        print(f"               {r.reason}")
    print(f"\n  Estimated reclaimable: {human_size(reclaimable)}")
    return 0


def cmd_diff(args) -> int:
    import os
    if not os.path.exists(args.path):
        print(f"error: path not found: {args.path}", file=sys.stderr)
        return 1
    before_tree = storage.load_tree(args.path)
    if before_tree is None:
        print("no previous scan to diff; run 'strata scan' twice.",
              file=sys.stderr)
        return 1
    # Re-scan current state without persisting yet.
    eng = StrataEngine(args.path)
    scanner = __import__("strata.scanner", fromlist=["Scanner"]).Scanner()
    after_tree = scanner.scan(args.path)
    d = diff_trees(before_tree, after_tree)
    if args.json:
        print(json.dumps(d.to_dict(), ensure_ascii=False, indent=2))
        return 0
    print(_header("Scan Diff"))
    sign = "+" if d.net_delta >= 0 else ""
    print(f"  Size: {human_size(d.size_before)} -> "
          f"{human_size(d.size_after)} ({sign}{human_size(d.net_delta)})")
    print(f"  Files: {d.files_before} -> {d.files_after}")
    if d.grew:
        print("\n  Grew:")
        for c in d.grew[:10]:
            print(f"    +{human_size(c.delta):>9}  {c.path}")
    if d.added:
        print("\n  Added:")
        for c in d.added[:10]:
            print(f"    +{human_size(c.size_after):>9}  {c.path}")
    if d.removed:
        print("\n  Removed:")
        for c in d.removed[:10]:
            print(f"    -{human_size(c.size_before):>9}  {c.path}")
    return 0


def cmd_serve(args) -> int:
    from strata.server import serve
    return serve(args.path, host=args.host, port=args.port,
                 hash_files=not args.no_hash, rebuild=args.rebuild)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    handlers = {
        "scan": cmd_scan,
        "report": cmd_report,
        "dupes": cmd_dupes,
        "big": cmd_big,
        "clean": cmd_clean,
        "diff": cmd_diff,
        "serve": cmd_serve,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
