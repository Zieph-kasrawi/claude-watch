#!/usr/bin/env python3
"""Resolve where /watch files a watched video: the research library.

The research library is one directory holding two layers:

  <library>/wiki/              the compiled wiki; wiki/SCHEMA.md governs it
  <library>/raw/transcripts/   immutable raw transcripts, one file per video

Its location is a single setting, WATCH_RESEARCH_LIBRARY_DIRECTORY, read from
the environment first and then from ~/.config/watch/.env. Whoever owns the
library later repoints this one value and nothing else changes.

The lookup fails closed: unset, missing, or without wiki/SCHEMA.md means
"no research library configured", and /watch saves nothing.

Usage:
  research_library.py   print the library directory and exit 0,
                        or explain on stderr and exit 1
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from setup import _read_env_key  # noqa: E402

RESEARCH_LIBRARY_SETTING = "WATCH_RESEARCH_LIBRARY_DIRECTORY"
WIKI_SCHEMA_RELATIVE_PATH = Path("wiki") / "SCHEMA.md"


def resolve_research_library_directory() -> Path | None:
    """Return the configured research library, or None when it is unusable."""
    configured = _read_env_key(RESEARCH_LIBRARY_SETTING)
    if not configured:
        return None
    library = Path(configured).expanduser()
    if not (library / WIKI_SCHEMA_RELATIVE_PATH).is_file():
        return None
    return library


def main() -> int:
    library = resolve_research_library_directory()
    if library is None:
        sys.stderr.write(
            f"[watch] no research library configured: set {RESEARCH_LIBRARY_SETTING} "
            f"in ~/.config/watch/.env to a directory containing {WIKI_SCHEMA_RELATIVE_PATH}\n"
        )
        return 1
    print(library)
    return 0


if __name__ == "__main__":
    sys.exit(main())
