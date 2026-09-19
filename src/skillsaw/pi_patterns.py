"""Bounded matching for Pi resource globs and ignore files."""

import re
from functools import lru_cache
from typing import Iterable

from pathspec import GitIgnoreSpec
from wcmatch import glob

from .timeouts import RegexTimeout, regex_timeout

_FLAGS = glob.GLOBSTAR | glob.BRACE | glob.EXTGLOB
_PATTERN_SECONDS = 0.02
_MAX_PATTERN_LENGTH = 1024
_MAX_IGNORE_PATTERNS = 4096


@lru_cache(maxsize=256)
def _compile_glob(pattern: str):
    if not pattern or len(pattern) > _MAX_PATTERN_LENGTH:
        return None
    with regex_timeout(_PATTERN_SECONDS):
        return glob.compile(pattern, flags=_FLAGS, limit=256)


def _globmatch(value: str, pattern: str) -> bool:
    try:
        compiled = _compile_glob(pattern)
        with regex_timeout(_PATTERN_SECONDS):
            return compiled.match(value) if compiled is not None else False
    except Exception:
        # wcmatch exposes expansion-limit exceptions through private modules.
        # Keep failures local to this pattern; failed compilations are not cached.
        return False


def _ignore_patterns(lines: Iterable[str]) -> list:
    patterns = []
    for index, line in enumerate(lines):
        if index >= _MAX_IGNORE_PATTERNS:
            break
        if len(line) > _MAX_PATTERN_LENGTH:
            continue
        try:
            with regex_timeout(_PATTERN_SECONDS):
                patterns.extend(GitIgnoreSpec.from_lines([line], backend="simple").patterns)
        except (ValueError, re.error, RecursionError, RegexTimeout):
            # GitIgnorePatternError (including the legacy GitWildMatch spelling)
            # derives from ValueError. A bad line must not suppress valid siblings.
            continue
    return patterns


def _ignored(ignore: GitIgnoreSpec, value: str) -> bool:
    try:
        with regex_timeout(_PATTERN_SECONDS):
            return ignore.match_file(value)
    except (ValueError, re.error, RecursionError, RegexTimeout):
        return False
