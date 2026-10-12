"""State-free, contained probes for an explicit Codex root-to-cwd chain."""

from __future__ import annotations

import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Tuple

from skillsaw.paths import Resolver, contained_resolve, relative_to_str

from .excludes import is_root_or_ancestor_excluded


@dataclass(frozen=True)
class InstructionCandidate:
    path: Path
    issue: Optional[str] = None
    resolved_path: Optional[Path] = None


def project_directories(root: Path, cwd: str, *, resolve: Resolver) -> Tuple[Path, ...]:
    directory = contained_resolve(root / cwd, root, resolve)
    if directory is None or not directory.is_dir():
        raise ValueError("Codex cwd must be an existing directory inside the requested root")
    directories = [directory]
    while directories[-1] != root:
        directories.append(directories[-1].parent)
    return tuple(reversed(directories))


def probe_file(
    path: Path, root: Path, *, resolve: Resolver, is_excluded: Callable[[Path], bool]
) -> Optional[InstructionCandidate]:
    """None means absent/non-file; uncertainty stops precedence, never falls through."""
    label = relative_to_str(path, root) or str(path)
    if is_root_or_ancestor_excluded(path, root, is_excluded):
        return InstructionCandidate(path, f"{label}: excluded from the requested authoring scope")
    resolved = contained_resolve(path, root, resolve)
    if resolved is None:
        return InstructionCandidate(path, f"{label}: unresolved or outside the requested root")
    if resolved != path and is_root_or_ancestor_excluded(resolved, root, is_excluded):
        return InstructionCandidate(path, f"{label}: excluded from the requested authoring scope")
    try:
        mode = path.stat().st_mode
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as error:
        return InstructionCandidate(path, f"{label}: cannot inspect file ({error})")
    return InstructionCandidate(path, resolved_path=resolved) if stat.S_ISREG(mode) else None


def select_instructions(
    directories: Tuple[Path, ...],
    names: Tuple[str, ...],
    *,
    resolve: Resolver,
    is_excluded: Callable[[Path], bool],
) -> Tuple[InstructionCandidate, ...]:
    """Select the first regular file in each directory without testing its content."""
    selected = []
    for directory in directories:
        for name in names:
            candidate = probe_file(
                directory / name, directories[0], resolve=resolve, is_excluded=is_excluded
            )
            if candidate is not None:
                selected.append(candidate)
                break
    return tuple(selected)
