"""Shared wall-clock budget for untrusted pattern matching."""

import signal
import threading
from contextlib import contextmanager
from typing import Iterator


class RegexTimeout(Exception):
    """Raised when a regex operation exceeds its wall-clock budget."""


@contextmanager
def regex_timeout(seconds: float) -> Iterator[None]:
    """Bound the wall-clock time of regex work inside the ``with`` body.

    Config-supplied patterns (``.skillsaw.yaml``) run against untrusted file
    bodies with Python's backtracking ``re`` engine, so a catastrophic pattern
    can hang lint indefinitely (issue #316).  This wraps such work with a
    ``SIGALRM`` timer that raises :class:`RegexTimeout`; CPython checks for
    pending signals inside the matching loop, so an in-progress ``re.search``
    is actually interrupted.

    The timer requires ``SIGALRM`` and the main thread, so it is a **no-op**
    on platforms without ``SIGALRM`` (e.g. Windows) or when called off the main
    thread — callers must treat the timeout as best-effort hardening for the
    CI (POSIX) threat, not a hard guarantee everywhere.
    """
    if (
        seconds <= 0
        or not hasattr(signal, "SIGALRM")
        or threading.current_thread() is not threading.main_thread()
    ):
        yield
        return

    def _handle(signum, frame):
        raise RegexTimeout(f"regex exceeded {seconds:g}s budget")

    previous = signal.signal(signal.SIGALRM, _handle)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)
