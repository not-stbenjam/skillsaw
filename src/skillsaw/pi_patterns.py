"""Bounded matching for Pi resource globs and ignore files.

``pathspec`` and ``wcmatch`` are imported where they are used: discovery
imports this module on every run, and only a repository declaring Pi
resources ever matches a pattern.
"""

import re
from functools import lru_cache
from typing import TYPE_CHECKING, Iterable, Optional, Sequence

from .timeouts import RegexTimeout, regex_timeout

if TYPE_CHECKING:
    from pathspec import GitIgnoreSpec

_PATTERN_SECONDS = 0.02
_MAX_PATTERN_LENGTH = 1024
_MAX_IGNORE_PATTERNS = 4096
# Timeouts after which a pattern (or one walk's ignore rules) stops matching.
_MAX_TIMEOUTS = 3


class _Glob:
    """One pattern's compiled matcher and its timeout history.

    Cached per pattern, so a deterministic compile failure is paid once and a
    pattern that keeps exceeding the budget stops costing a timeout per path.
    """

    __slots__ = ("compiled", "failed", "timeouts")

    def __init__(self, pattern: str):
        self.compiled = None
        self.failed = not pattern or len(pattern) > _MAX_PATTERN_LENGTH
        self.timeouts = 0


@lru_cache(maxsize=256)
def _compile_glob(pattern: str) -> _Glob:
    return _Glob(pattern)


def reset_pattern_state() -> None:
    """Forget compiled patterns and their timeout history before a new run."""
    _compile_glob.cache_clear()


def _globmatch(value: str, pattern: str, fallback: bool = False) -> bool:
    """Match *value* against a Pi glob within the regex budget.

    *fallback* answers for a pattern that cannot be evaluated — it fails to
    compile or exceeds the budget: callers matching an inclusion pass
    ``True`` so such a pattern cannot hide the resources it names, and
    exclusions keep ``False`` so it cannot hide them either. The budget is
    wall-clock, so a timeout is retried until the pattern has timed out a few
    times: a spurious timeout on a loaded runner does not change a
    well-behaved pattern's result, and a pattern that keeps timing out is
    retired to the fallback.
    """
    cached = _compile_glob(pattern)
    while not cached.failed and cached.timeouts < _MAX_TIMEOUTS:
        try:
            if cached.compiled is None:
                from wcmatch import glob

                with regex_timeout(_PATTERN_SECONDS):
                    cached.compiled = glob.compile(
                        pattern, flags=glob.GLOBSTAR | glob.BRACE | glob.EXTGLOB, limit=256
                    )
            with regex_timeout(_PATTERN_SECONDS):
                return cached.compiled.match(value)
        except (RegexTimeout, RecursionError):
            cached.timeouts += 1
        except Exception:
            # wcmatch exposes expansion-limit exceptions through private
            # modules. Keep failures local to this pattern; a failed compile
            # is final.
            if cached.compiled is None:
                cached.failed = True
            return fallback
    return fallback


def _ignore_spec(patterns: Sequence = ()) -> "GitIgnoreSpec":
    from pathspec import GitIgnoreSpec

    return GitIgnoreSpec(list(patterns[-_MAX_IGNORE_PATTERNS:]), backend="simple")


def _ignore_patterns(lines: Iterable[str]) -> list:
    from pathspec import GitIgnoreSpec

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


def _ignored(ignore: "GitIgnoreSpec", value: str) -> Optional[bool]:
    """Match *value* against *ignore*; ``None`` means the budget ran out."""
    try:
        with regex_timeout(_PATTERN_SECONDS):
            return ignore.match_file(value)
    except (RecursionError, RegexTimeout):
        return None
    except (ValueError, re.error):
        return False
