# Examples

This folder collects common Strata workflows.

## 1. Find wasted space in a project

```bash
strata scan ~/code/my-project
strata serve ~/code/my-project
```

Open the treemap, click into the largest rectangles, and switch to the
**Cleanup** tab for a ranked, dry-run list of caches and duplicates.

## 2. Scriptable JSON

```bash
# Largest files as JSON
strata big ~/code -n 50 --json > biggest.json

# All duplicate groups
strata dupes ~/code --json > dupes.json

# Cleanup recommendations with a 100 MB large-file threshold
strata clean ~/code --threshold-mb 100 --json > clean.json
```

## 3. Watch a folder grow

```bash
strata scan ~/build --no-hash
# ... build runs, artifacts appear ...
strata diff ~/build
```

`diff` reports added, removed, grown and shrunk files plus the net byte
delta between the previous and current scan.

## 4. Quick disk census without hashing

Hashing is what makes duplicate detection exact, but on very large trees
you can skip it for a fast first pass:

```bash
strata scan /mnt/external --no-hash
strata report /mnt/external
```

## 5. Embedded in Python

```python
from strata.engine import StrataEngine
from strata.treemap import treemap_nodes

eng = StrataEngine("/home/me/project")
report = eng.scan()

print("duplicate waste:", report.duplicate_waste)

for rec in eng.recommendations(large_threshold=100 * 1024 * 1024):
    if rec.confidence >= 0.8:
        print(rec.kind, rec.path, rec.reclaimable)

# Render-ready tiles for a 1000x1000 canvas
tiles = treemap_nodes(eng.tree, (0, 0, 1000, 1000), max_depth=2)
```

Strata never deletes files — every suggestion is advisory.
