"""Classify files into categories and recognize special directories."""
from __future__ import annotations

import time
from typing import Dict, Tuple

# Extension -> (category, language)
EXTENSION_MAP: Dict[str, Tuple[str, str]] = {
    # code
    ".py": ("code", "python"), ".pyw": ("code", "python"),
    ".js": ("code", "javascript"), ".mjs": ("code", "javascript"),
    ".cjs": ("code", "javascript"),
    ".ts": ("code", "typescript"), ".tsx": ("code", "typescript"),
    ".jsx": ("code", "javascript"),
    ".java": ("code", "java"), ".kt": ("code", "kotlin"),
    ".c": ("code", "c"), ".h": ("code", "c"),
    ".cpp": ("code", "cpp"), ".cc": ("code", "cpp"), ".cxx": ("code", "cpp"),
    ".hpp": ("code", "cpp"), ".hh": ("code", "cpp"),
    ".cs": ("code", "csharp"), ".go": ("code", "go"), ".rs": ("code", "rust"),
    ".rb": ("code", "ruby"), ".php": ("code", "php"),
    ".swift": ("code", "swift"), ".scala": ("code", "scala"),
    ".sh": ("code", "shell"), ".bash": ("code", "shell"),
    ".zsh": ("code", "shell"), ".ps1": ("code", "powershell"),
    ".lua": ("code", "lua"), ".pl": ("code", "perl"),
    ".r": ("code", "r"), ".dart": ("code", "dart"),
    ".sql": ("code", "sql"), ".proto": ("code", "protobuf"),
    # web / markup
    ".html": ("web", "html"), ".htm": ("web", "html"),
    ".css": ("web", "css"), ".scss": ("web", "css"), ".sass": ("web", "css"),
    ".less": ("web", "css"), ".vue": ("web", "vue"), ".svelte": ("web", "svelte"),
    ".xml": ("data", "xml"), ".svg": ("image", "svg"),
    # data / config
    ".json": ("data", "json"), ".yaml": ("data", "yaml"), ".yml": ("data", "yaml"),
    ".toml": ("data", "toml"), ".ini": ("config", "ini"), ".cfg": ("config", "ini"),
    ".conf": ("config", "config"), ".properties": ("config", "config"),
    ".csv": ("data", "csv"), ".tsv": ("data", "tsv"),
    ".env": ("config", "env"), ".lock": ("config", "lock"),
    # docs
    ".md": ("docs", "markdown"), ".markdown": ("docs", "markdown"),
    ".rst": ("docs", "rst"), ".txt": ("docs", "text"),
    ".pdf": ("docs", "pdf"), ".doc": ("docs", "word"), ".docx": ("docs", "word"),
    ".xls": ("docs", "excel"), ".xlsx": ("docs", "excel"),
    ".ppt": ("docs", "slides"), ".pptx": ("docs", "slides"),
    ".epub": ("docs", "ebook"),
    # images
    ".png": ("image", "png"), ".jpg": ("image", "jpeg"), ".jpeg": ("image", "jpeg"),
    ".gif": ("image", "gif"), ".bmp": ("image", "bmp"), ".webp": ("image", "webp"),
    ".ico": ("image", "icon"), ".tiff": ("image", "tiff"), ".heic": ("image", "heic"),
    ".raw": ("image", "raw"),
    # audio
    ".mp3": ("audio", "mp3"), ".wav": ("audio", "wav"), ".flac": ("audio", "flac"),
    ".aac": ("audio", "aac"), ".ogg": ("audio", "ogg"), ".m4a": ("audio", "m4a"),
    ".wma": ("audio", "wma"),
    # video
    ".mp4": ("video", "mp4"), ".mkv": ("video", "mkv"), ".avi": ("video", "avi"),
    ".mov": ("video", "mov"), ".wmv": ("video", "wmv"), ".flv": ("video", "flv"),
    ".webm": ("video", "webm"), ".m4v": ("video", "m4v"),
    # archives / packages
    ".zip": ("archive", "zip"), ".tar": ("archive", "tar"), ".gz": ("archive", "gzip"),
    ".tgz": ("archive", "gzip"), ".bz2": ("archive", "bzip2"), ".xz": ("archive", "xz"),
    ".7z": ("archive", "7z"), ".rar": ("archive", "rar"),
    ".jar": ("archive", "jar"), ".war": ("archive", "war"),
    ".deb": ("archive", "deb"), ".rpm": ("archive", "rpm"),
    # binary / executable / disk images
    ".exe": ("binary", "exe"), ".msi": ("binary", "msi"),
    ".dll": ("binary", "dll"), ".so": ("binary", "shared-object"),
    ".dylib": ("binary", "dylib"), ".bin": ("binary", "bin"),
    ".wasm": ("binary", "wasm"), ".dmg": ("binary", "dmg"),
    ".iso": ("binary", "iso"), ".img": ("binary", "img"),
    ".class": ("binary", "java-class"), ".pyc": ("binary", "pyc"),
    ".o": ("binary", "object"), ".a": ("binary", "archive-lib"),
    ".lib": ("binary", "lib"), ".pdb": ("binary", "pdb"),
    # fonts
    ".ttf": ("font", "ttf"), ".otf": ("font", "otf"), ".woff": ("font", "woff"),
    ".woff2": ("font", "woff2"), ".eot": ("font", "eot"),
}

# Filenames that are meaningful even without an extension.
SPECIAL_FILES: Dict[str, Tuple[str, str]] = {
    "dockerfile": ("config", "docker"),
    "makefile": ("code", "make"),
    "rakefile": ("code", "ruby"),
    "license": ("docs", "text"),
    "readme": ("docs", "markdown"),
    ".gitignore": ("config", "git"),
    ".gitattributes": ("config", "git"),
    ".dockerignore": ("config", "docker"),
}

# Directories that are dependency/build caches — usually safe to regenerate.
CACHE_DIRS = {
    "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache",
    ".ruff_cache", ".tox", ".gradle", "target", "build", "dist",
    ".next", ".nuxt", ".cache", ".turbo", ".parcel-cache",
    "venv", ".venv", "env", ".env", "virtualenv",
    ".eggs", "*.egg-info",
}

# VCS / metadata dirs we never descend into or recommend deleting blindly.
SKIP_DIRS = {".git", ".hg", ".svn"}

# Directories that are clearly development dependency trees (high reclaim).
DEV_DIR_LABELS = {
    "node_modules": "Node.js dependencies",
    "venv": "Python virtualenv",
    ".venv": "Python virtualenv",
    "env": "Python virtualenv",
    "__pycache__": "Python bytecode cache",
    ".pytest_cache": "pytest cache",
    ".mypy_cache": "mypy cache",
    ".ruff_cache": "ruff cache",
    "target": "Rust/Java build output",
    "build": "build output",
    "dist": "build distribution",
    ".gradle": "Gradle cache",
}

TEMP_SUFFIXES = {".tmp", ".temp", ".log", ".bak", ".swp", ".swo",
                 ".part", ".crdownload", ".download", ".old", ".orig", "~"}


def classify(name: str, is_dir: bool) -> Tuple[str, str, str]:
    """Return (category, language, extension) for a file or directory name."""
    if is_dir:
        return ("dir", "", "")
    lower = name.lower()
    if lower in SPECIAL_FILES:
        cat, lang = SPECIAL_FILES[lower]
        return (cat, lang, "")
    dot = lower.rfind(".")
    if dot >= 0:
        ext = lower[dot:]
        if ext in EXTENSION_MAP:
            cat, lang = EXTENSION_MAP[ext]
            return (cat, lang, ext[1:])
        return ("other", "", ext[1:])
    return ("other", "", "")


def is_cache_dir(name: str) -> bool:
    if name in CACHE_DIRS:
        return True
    if name.endswith(".egg-info"):
        return True
    return False


def is_skip_dir(name: str) -> bool:
    return name in SKIP_DIRS


def is_temp_file(name: str) -> bool:
    lower = name.lower()
    for suf in TEMP_SUFFIXES:
        if lower.endswith(suf):
            return True
    return lower.endswith("~") or lower.startswith("~")


# ---------------------------------------------------------------------------
# Age bucketing
# ---------------------------------------------------------------------------

def age_bucket(mtime: float, now: float = None) -> str:
    """Bucket a modification time into a human age range."""
    if now is None:
        now = time.time()
    days = (now - mtime) / 86400.0
    if days < 7:
        return "last_7_days"
    if days < 30:
        return "last_30_days"
    if days < 90:
        return "last_90_days"
    if days < 180:
        return "last_180_days"
    if days < 365:
        return "last_year"
    return "over_a_year"


AGE_ORDER = ["last_7_days", "last_30_days", "last_90_days",
             "last_180_days", "last_year", "over_a_year"]


def size_bucket(size: int) -> str:
    """Bucket a file by size."""
    if size < 1024:
        return "<1KB"
    if size < 10 * 1024:
        return "1-10KB"
    if size < 100 * 1024:
        return "10-100KB"
    if size < 1024 * 1024:
        return "100KB-1MB"
    if size < 10 * 1024 * 1024:
        return "1-10MB"
    if size < 100 * 1024 * 1024:
        return "10-100MB"
    if size < 1024 * 1024 * 1024:
        return "100MB-1GB"
    return ">1GB"


SIZE_ORDER = ["<1KB", "1-10KB", "10-100KB", "100KB-1MB", "1-10MB",
              "10-100MB", "100MB-1GB", ">1GB"]
