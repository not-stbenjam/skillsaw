"""Contained Cursor glob expansion with each selector state visited once."""

from __future__ import annotations

import fnmatch
import os
import sys
from pathlib import Path

from skillsaw.paths import contained_resolve, safe_is_dir, safe_is_symlink
from skillsaw.timeouts import RegexTimeout, regex_timeout


def contained_glob(root: Path, pattern: str) -> set[Path]:
    """Match pathlib's component globs without repeated recursive traversals.

    A repeated ``**/name/`` can reach the same directory and selector through
    many routes. Memoizing that pair makes expansion proportional to the
    reachable paths times the pattern length, rather than their combinations.
    Directory symlinks are followed only by ordinary selectors, like pathlib;
    every candidate is contained before it can be enumerated.
    """
    parts = Path(pattern).parts
    if any("**" in part and part != "**" for part in parts):
        return set()  # pathlib rejects partial recursive selectors too.
    # pathlib only began honoring trailing separators in Python 3.11.
    directory_only = sys.version_info >= (3, 11) and pattern.endswith(
        tuple(sep for sep in (os.sep, os.altsep) if sep)
    )
    pending = [(root, 0)]
    visited = set()
    children = {}
    matches = set()

    def entries(directory: Path) -> tuple[Path, ...]:
        if directory not in children:
            try:
                children[directory] = tuple(
                    path
                    for path in directory.iterdir()
                    if contained_resolve(path, root) is not None
                )
            except (OSError, ValueError):
                children[directory] = ()
        return children[directory]

    while pending:
        path, index = pending.pop()
        if (path, index) in visited:
            continue
        visited.add((path, index))
        if index == len(parts):
            if not directory_only or safe_is_dir(path):
                matches.add(path)
            continue
        if not safe_is_dir(path):
            continue
        part = parts[index]
        if part == "**":
            pending.append((path, index + 1))
            for child in entries(path):
                if safe_is_dir(child) and not safe_is_symlink(child):
                    pending.append((child, index))
                elif index == len(parts) - 1 and not directory_only and sys.version_info >= (3, 13):
                    # Python 3.13 extended a terminal ** to files and symlinks.
                    matches.add(child)
        else:
            for child in entries(path):
                try:
                    with regex_timeout(0.02):
                        matched = fnmatch.fnmatch(child.name, part)
                except (RegexTimeout, RecursionError):
                    matched = False
                if matched:
                    pending.append((child, index + 1))
    return matches
