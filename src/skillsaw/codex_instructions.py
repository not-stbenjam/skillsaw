"""Inspect selected Codex instructions through the typed lint tree."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List, Tuple

from .blocks.codex import CodexConfigBlock
from .discovery.codex_instructions import InstructionCandidate
from .formats.codex_instructions import DEFAULT_MAX_BYTES, instruction_bytes
from .lint_target import LintTarget
from .paths import relative_to_str


@dataclass(eq=False)
class CodexInstructionsNode(LintTarget):
    """A selection view referencing retained tree nodes without copying their content."""

    root_path: Path = Path(".")
    cwd: Path = Path(".")
    sources: Tuple[InstructionCandidate, ...] = ()
    max_bytes: int = DEFAULT_MAX_BYTES
    limit_source: str = "Codex default (assumed)"
    filenames: Tuple[str, ...] = ()
    fallback_source: str = "Codex default (assumed)"
    config_sources: List[InstructionCandidate] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)
    ignored_fallbacks: Tuple[str, ...] = ()

    def tree_label(self) -> str:
        return f"Codex instruction selection [cwd: {relative_to_str(self.cwd, self.root_path)}]"

    def report(self, tree: LintTarget) -> dict:
        """Read selected files represented by retained tree nodes, in lexical source order.

        Codex charges an in-scope symlink once per directory occurrence even
        though the lint tree checks its content once per physical file.
        """
        blocks = {block.resolved_path: block for block in tree.walk() if block is not self}
        config_paths = {block.resolved_path for block in tree.find(CodexConfigBlock)}
        issues = list(self.issues)
        config_sources = []
        for source in self.config_sources:
            label = relative_to_str(source.path, self.root_path) or str(source.path)
            config_sources.append(label)
            if source.resolved_path not in config_paths:
                issues.append(f"{label}: configuration is not in the retained lint tree")
        entries = []
        remaining = self.max_bytes
        charged = text_bytes = included = total = 0
        budget_known = not issues
        for source in self.sources:
            label = relative_to_str(source.path, self.root_path) or str(source.path)
            entry = {"path": label, "status": "unknown", "cumulative_bytes": None}
            issue = source.issue
            block = blocks.get(source.resolved_path) if issue is None else None
            if issue is None and block is None:
                issue = f"{label}: instruction content is not in the retained lint tree"
            if issue is None:
                try:
                    # read_text normalizes BOM/CRLF and rejects invalid UTF-8;
                    # none of those operations matches the Codex byte loader.
                    file_bytes = block.path.stat().st_size
                    data = b""
                    if budget_known and remaining > 0:
                        with block.path.open("rb") as stream:
                            data = stream.read(min(remaining, file_bytes))
                except OSError as error:
                    issue = f"{label}: cannot read instruction bytes ({error})"
                else:
                    total += file_bytes
                    entry["file_bytes"] = file_bytes
                    if budget_known:
                        usage = instruction_bytes(data, remaining, file_bytes=file_bytes)
                        entry.update(asdict(usage))
                        charged += usage.charged_bytes
                        remaining -= usage.charged_bytes
                        text_bytes += usage.text_bytes
                        included += int(usage.status in {"loaded", "truncated"})
                        entry["cumulative_bytes"] = charged
            if issue:
                issues.append(issue)
                entry["issue"] = issue
                budget_known = False
            entries.append(entry)
        separators = max(0, included - 1) * 2
        affected = [
            entry["path"]
            for entry in entries
            if entry.get("truncated")
            or (entry["status"] == "omitted" and entry.get("file_bytes", 0) > 0)
        ]
        return {
            "host": "codex",
            "loader_version": "0.162.1",
            "root": str(self.root_path),
            "cwd": str(self.cwd),
            "project_doc_max_bytes": self.max_bytes,
            "limit_source": self.limit_source,
            "candidate_filenames": list(self.filenames),
            "fallback_source": self.fallback_source,
            "config_sources": config_sources,
            "ignored_fallback_filenames": list(self.ignored_fallbacks),
            "selected": entries,
            "complete": budget_known,
            "selected_file_bytes": total if budget_known else None,
            "charged_bytes": charged if budget_known else None,
            "separator_bytes": separators if budget_known else None,
            "rendered_project_bytes": text_bytes + separators if budget_known else None,
            "affected_paths": affected,
            "issues": issues,
            "assumptions": [
                "The supplied root is the Codex project root; cwd is resolved inside it. "
                "No parent root-marker search is performed.",
                "One trusted local environment. Codex 0.162.1 skips project instructions "
                "for an untrusted project.",
                "Global, managed, profile and CLI Codex configuration is not read. "
                "Unspecified settings use in-scope project config, then assumed defaults.",
                "Global/user/thread instructions are not read and do not consume this "
                "project-file budget. Separators and lossy UTF-8 expansion are uncharged.",
            ],
        }
