"""Cached stateful views over the repository's discovery walks."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Set, TYPE_CHECKING, Tuple

from .discovery import claude as claude_discovery
from .discovery import detect as detect_discovery
from .repository_types import RepositoryType

if TYPE_CHECKING:
    from .discovery.detect import RepositoryScan
    from .repository_provenance import PluginProvenance


class RepositoryScanMixin:
    """Repository scan orchestration shared by format-specific mixins.

    Two walks live here: the single-pass repository scan the tool-directory
    and instruction-file lookups read, and skill discovery, which takes the
    ecosystems' plugin roots and ownership predicates from the host and
    returns the skill list every rule reads. Both are filesystem work rather
    than orchestration, which is why they sit beside each other here instead
    of in ``RepositoryContext``.
    """

    _INSTRUCTION_FILENAMES: Tuple[str, ...]

    if TYPE_CHECKING:
        root_path: Path
        instruction_files: List[Path]
        repo_types: Set[RepositoryType]
        exclude_patterns: List[str]
        _pi_package_forced: bool
        _pi_packages_cache: Tuple[Tuple[str, ...], List[Path]]
        plugins: List[Path]
        codex_plugins: List[Path]

        def grok_plugin_roots(self) -> List[Path]: ...

        antigravity_plugins: List[Path]

        def antigravity_plugin_roots(self) -> List[Path]: ...

        _scan: Optional[RepositoryScan]

        def is_path_excluded(self, path: Path) -> bool: ...

        def agent_plugin_roots(self) -> List[Path]: ...

        def provenance(self, plugin_dir: Path) -> PluginProvenance: ...

        def in_apm_compiled_dir(self, path: Path) -> bool: ...

        def _should_skip_dir(self, item: Path) -> bool: ...

        def _contained_plugin_claim_boundary(self, parent: Path) -> Optional[Path]: ...

        def _contained_plugin_claims_possible(self) -> bool: ...

        def _is_containment_plugin(self, path: Path) -> bool: ...

    def pi_discovery_roots(self) -> List[Path]:
        """Declared packages plus an explicitly selected conventional root."""
        roots = self.pi_package_roots()
        if self._pi_package_forced and self.root_path not in roots:
            roots.append(self.root_path)
        return roots

    def pi_package_roots(self) -> List[Path]:
        """Cached, declaration-invariant Pi package claims from the shared scan."""
        from .discovery.pi import package_roots

        key = tuple(self.exclude_patterns)
        cached = getattr(self, "_pi_packages_cache", None)
        if cached is None or cached[0] != key:
            roots = package_roots(
                self.root_path,
                self._repository_scan().package_json_files,
                (p / "settings.json" for p in self.agent_tool_dirs(".pi")),
                self.is_path_excluded,
            )
            self._pi_packages_cache = (key, roots)
        return list(self._pi_packages_cache[1])

    def _discover_instruction_files(self) -> List[Path]:
        """Discover root and nested instruction files read by supported tools.

        Includes root conventions, Copilot ``*.instructions.md`` files, and
        Devin's documented names at nested project levels. The work shares
        one filesystem walk with :meth:`agent_tool_dirs`.
        """
        return list(self._repository_scan().instruction_files)

    def _repository_scan(self) -> RepositoryScan:
        """Return the cached single-pass walk of the repository."""
        if self._scan is None:
            self._scan = detect_discovery.scan_repository(
                self.root_path, self._INSTRUCTION_FILENAMES
            )
        return self._scan

    def agent_tool_dirs(self, name: str) -> List[Path]:
        """Return every non-excluded directory called *name* in the repository.

        Two kinds of caller, one walk. Editor tools — Cursor (``.cursor``),
        Copilot/VS Code (``.github``), Cline (``.clinerules``), Devin
        (``.devin``/``.windsurf``), OpenCode (``.opencode``) — read
        customizations from the nearest enclosing directory, so a monorepo
        package may carry its own alongside the root. Ecosystem markers
        (``.grok-plugin``) are the same shape of question: a plugin or a
        catalog in a package is found here rather than by a second
        traversal.
        """
        return [
            path
            for path in self._repository_scan().tool_dirs.get(name, ())
            if not self.is_path_excluded(path)
        ]

    def legacy_editor_files(self, name: str) -> List[Path]:
        """Every non-excluded *name* legacy editor file in the repository."""
        return [
            path
            for path in self._repository_scan().legacy_editor_files.get(name, ())
            if not self.is_path_excluded(path)
        ]

    def promptfoo_named_files(self) -> List[Path]:
        """Promptfoo conventionally named files from the shared repository walk."""
        return list(self._repository_scan().promptfoo_named_files)

    def promptfoo_eval_files(self, evals_dir: Path) -> List[Path]:
        """YAML candidates beneath one lexical ``evals/`` directory."""
        return list(self._repository_scan().promptfoo_eval_files.get(evals_dir, ()))

    def _detect_tool_type_values(self) -> set[str]:
        """``RepositoryType`` values for the tools this repository configures.

        Values rather than members: discovery stays state-free and imports
        nothing from ``context``, which owns the enum.
        """
        return detect_discovery.tool_types(
            self.root_path,
            self.instruction_files,
            self.is_path_excluded,
            self._repository_scan().tool_dirs,
            self._repository_scan().legacy_editor_files,
            self._repository_scan().skills_lock_files,
        )

    #: Alias for the one definition in discovery. Two copies of "which
    #: directories does a walk prune" are how a checkout starts being walked
    #: differently by two callers that both believe they agree.
    _WALK_SKIP_DIRS = detect_discovery.WALK_SKIP_DIRS

    def _discover_skills(self) -> List[Path]:
        """Discover Agent Skills through the state-free Claude discovery seam."""
        from .formats.codex_manifest import portable_manifest

        recursive_agent_plugins = [
            plugin
            for plugin in self.agent_plugin_roots()
            if (provenance := self.provenance(plugin)).claude
            or (provenance.codex and portable_manifest(plugin) is None)
        ]
        skills = claude_discovery.discover_skills(
            self.root_path,
            agentskills=RepositoryType.AGENTSKILLS in self.repo_types,
            # A plugins/* layout can cause legacy Claude discovery to list an
            # Agent-only sibling. Only an actual Claude declaration permits
            # recursive Claude skill discovery for a portable package.
            plugins=[
                plugin
                for plugin in self.plugins
                if not self.provenance(plugin).agent_plugin or self.provenance(plugin).claude
            ],
            codex_plugins=[p for p in self.codex_plugins if portable_manifest(p) is None],
            # Config and catalog declarations retain custom skill paths
            # under unrelated --type overrides, just like their tree nodes.
            grok_plugins=self.grok_plugin_roots(),
            # The claim union, not the gated discovery list: a plugin a
            # ``plugins.json`` registry names has a container and its hooks
            # and MCP file either way, and its ``skills/`` must not vanish
            # because an unrelated ``--type`` switched generic Agent Skills
            # discovery off. Excluded roots are already dropped.
            antigravity_plugins=self.antigravity_plugin_roots(),
            # Declaration-invariant roots keep portable skills visible under
            # an unrelated ``--type`` override while still enforcing their
            # fixed immediate-child discovery semantics.
            agent_plugins=self.agent_plugin_roots(),
            recursive_agent_plugins=recursive_agent_plugins,
            in_apm_compiled_dir=self.in_apm_compiled_dir,
            should_skip=self._should_skip_dir,
            claim_boundary=self._contained_plugin_claim_boundary,
            containment_claims_possible=self._contained_plugin_claims_possible,
            is_containment_plugin=self._is_containment_plugin,
            # Devin/Windsurf, Grok Build and Antigravity each read the
            # nearest enclosing tool directory, so a monorepo package carries
            # its own ``skills/``. ``CONVENTIONAL_SKILL_DIRS`` covers only the
            # root-relative spelling and the generic walk skips hidden
            # directories, so the nested roots are handed over from the walk
            # that already found them — the same tuple detection reads.
            additional_skill_dirs=(
                directory / "skills"
                for name in detect_discovery.NESTED_TOOL_SKILL_DIRS
                for directory in self.agent_tool_dirs(name)
            ),
            is_excluded=self.is_path_excluded,
        )

        # Pi owns selection inside its packages and .pi/skills. A dual package
        # retains other consumers' discovery as well as Pi's own resources.
        pi_roots = [
            p for p in self.pi_discovery_roots() if not (self.provenance(p).ecosystems - {"pi"})
        ]
        from .discovery.pi import project_resources

        native_skills = set()
        for directory in self.agent_tool_dirs(".pi"):
            native_skills.update(
                project_resources(directory, "skills", self.root_path, self.is_path_excluded)
            )

        def owned_by_pi(path: Path) -> bool:
            if path / "SKILL.md" in native_skills:
                return True
            if not any(path.is_relative_to(root) for root in pi_roots):
                return False
            # A Pi package does not own another tool's customization root or
            # an independently declared nested package. Keep those consumers.
            for ancestor in (path, *path.parents):
                if ancestor.name.startswith(".") and ancestor.name != ".pi":
                    return False
                if self.provenance(ancestor).ecosystems - {"pi"}:
                    return False
                if ancestor in pi_roots:
                    return True
            return False

        return [p for p in skills if not owned_by_pi(p)]
