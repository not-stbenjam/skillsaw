"""Cached native OpenClaw discovery, independent of forced format selection."""

from pathlib import Path
from typing import TYPE_CHECKING, List, Optional, Sequence, Tuple

from .discovery.openclaw import discover_plugins
from .repository_types import RepositoryType

if TYPE_CHECKING:
    from .discovery.detect import RepositoryScan


class RepositoryOpenClawMixin:
    """Use the shared scan; keep exclusions live when they change after init."""

    if TYPE_CHECKING:
        root_path: Path
        exclude_patterns: List[str]

        def _repository_scan(self) -> "RepositoryScan": ...

        def is_path_excluded(self, path: Path) -> bool: ...

    def _init_openclaw(self, repo_types: Optional[Sequence[RepositoryType]]) -> None:
        self._openclaw_forced = (
            repo_types is not None and RepositoryType.OPENCLAW_PLUGIN in repo_types
        )
        self._openclaw_cache: Optional[List[Path]] = None
        self._openclaw_excludes: Optional[Tuple[str, ...]] = None

    def openclaw_plugin_roots(self) -> List[Path]:
        patterns = tuple(self.exclude_patterns)
        if self._openclaw_cache is None or patterns != self._openclaw_excludes:
            scan = self._repository_scan()
            self._openclaw_cache = discover_plugins(
                scan.openclaw_manifest_files, scan.package_json_files, self.is_path_excluded
            )
            if self._openclaw_forced and not self.is_path_excluded(self.root_path):
                self._openclaw_cache = sorted(set(self._openclaw_cache) | {self.root_path})
            self._openclaw_excludes = patterns
        return self._openclaw_cache
