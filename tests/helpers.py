"""Shared test helpers for building temporary directory trees."""
import os
import shutil
import tempfile


def make_tree(files: dict, dirs: dict = None) -> str:
    """Create a temp directory.

    ``files`` maps relative path -> content (str) or bytes.
    ``dirs`` maps relative directory path -> ignored (ensures empty dirs).
    Returns the temp root.
    """
    tmp = tempfile.mkdtemp(prefix="strata_test_")
    for rel, content in files.items():
        full = os.path.join(tmp, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(full), exist_ok=True)
        if isinstance(content, bytes):
            with open(full, "wb") as fh:
                fh.write(content)
        else:
            # newline="" prevents \n -> \r\n translation on Windows so
            # byte sizes match across platforms.
            with open(full, "w", encoding="utf-8", newline="") as fh:
                fh.write(content)
    for rel in (dirs or {}):
        os.makedirs(os.path.join(tmp, rel.replace("/", os.sep)), exist_ok=True)
    return tmp


def cleanup(path: str) -> None:
    shutil.rmtree(path, ignore_errors=True)


def write_file(root: str, rel: str, content: str, size: int = None) -> str:
    """Write a file, optionally padding it to an exact byte size."""
    full = os.path.join(root, rel.replace("/", os.sep))
    os.makedirs(os.path.dirname(full), exist_ok=True)
    if size is not None:
        content = (content + ("x" * size))[:size]
    with open(full, "w", encoding="utf-8", newline="") as fh:
        fh.write(content)
    return full


def set_mtime(path: str, mtime: float) -> None:
    os.utime(path, (mtime, mtime))
