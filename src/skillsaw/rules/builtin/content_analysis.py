"""Shared content analysis utilities for instruction file rules.

These detectors work across all instruction formats (Copilot, AGENTS.md, CLAUDE.md, etc.).
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class Match:
    """A pattern match with location and context."""

    text: str
    line: int
    column: int
    suggestion: Optional[str] = None


@dataclass
class DeadRef:
    """A reference to a non-existent file or command."""

    ref: str
    ref_type: str  # "file" or "command"
    line: int
    column: int


@dataclass
class PositionIssue:
    """A critical instruction that is poorly positioned."""

    text: str
    line: int
    total_lines: int
    recommendation: str


_WEAK_PATTERNS = [
    (re.compile(r"\btry to\b", re.IGNORECASE), "Use a direct imperative instead"),
    (re.compile(r"\bwhere possible\b", re.IGNORECASE), "Specify the exact conditions"),
    (re.compile(r"\bwhen possible\b", re.IGNORECASE), "Specify the exact conditions"),
    (re.compile(r"\bif possible\b", re.IGNORECASE), "Specify the exact conditions"),
    (re.compile(r"\bbe careful\b", re.IGNORECASE), "State the specific constraint"),
    (re.compile(r"\bplease\b", re.IGNORECASE), "Use direct imperatives without 'please'"),
    (re.compile(r"\bconsider\b", re.IGNORECASE), "State a concrete rule instead"),
    (re.compile(r"\bshould probably\b", re.IGNORECASE), "Use 'MUST' or remove"),
    (re.compile(r"\bmight want to\b", re.IGNORECASE), "Use a direct imperative instead"),
    (re.compile(r"\bideally\b", re.IGNORECASE), "State the requirement directly"),
    (re.compile(r"\bit would be nice\b", re.IGNORECASE), "State a concrete rule instead"),
    (re.compile(r"\bavoid if you can\b", re.IGNORECASE), "Use 'NEVER' or state the exception"),
]


def weak_language_detector(text: str) -> List[Match]:
    """Detect weak/hedging language in instruction text."""
    matches = []
    for line_num, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("#"):
            continue
        for pattern, suggestion in _WEAK_PATTERNS:
            for m in pattern.finditer(line):
                matches.append(
                    Match(
                        text=m.group(),
                        line=line_num,
                        column=m.start() + 1,
                        suggestion=suggestion,
                    )
                )
    return matches


_FILE_REF_RE = re.compile(
    r"(?:`|\b)(\.?\.?/[\w./-]+(?:\.\w+)?|[\w./-]+\.(?:py|js|ts|tsx|jsx|go|rs|rb|java|sh|yaml|yml|json|toml|md|txt|cfg|ini|css|html|xml|sql))\b`?"
)

_URL_PREFIX_RE = re.compile(r"https?://\S*$")


def dead_ref_scanner(text: str, repo_root: Path) -> List[DeadRef]:
    """Scan text for file path references and verify they exist."""
    refs = []
    for line_num, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("#"):
            continue
        for m in _FILE_REF_RE.finditer(line):
            ref_path = m.group(1)
            prefix = line[: m.start(1)]
            if _URL_PREFIX_RE.search(prefix):
                continue
            if "*" in ref_path or "?" in ref_path:
                continue
            candidate = repo_root / ref_path
            if not candidate.exists():
                refs.append(
                    DeadRef(
                        ref=ref_path,
                        ref_type="file",
                        line=line_num,
                        column=m.start(1) + 1,
                    )
                )
    return refs


_COMMAND_REF_RE = re.compile(r"`((?:npm|npx|yarn|pnpm|make|go|cargo|pip|python|dotnet)\s[^`]+)`")


def dead_command_scanner(text: str, repo_root: Path) -> List[DeadRef]:
    """Scan text for command/script references and verify they exist."""
    refs = []
    package_json = _load_package_json_scripts(repo_root)
    makefile_targets = _load_makefile_targets(repo_root)

    for line_num, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("#"):
            continue
        for m in _COMMAND_REF_RE.finditer(line):
            cmd_str = m.group(1)
            parts = cmd_str.split()
            if len(parts) < 2:
                continue

            runner = parts[0]
            target = parts[1]

            if runner in ("npm", "npx", "yarn", "pnpm") and target == "run" and len(parts) > 2:
                target = parts[2]
                if package_json is not None and target not in package_json:
                    refs.append(
                        DeadRef(
                            ref=cmd_str, ref_type="command", line=line_num, column=m.start(1) + 1
                        )
                    )
            elif runner == "make":
                if makefile_targets is not None and target not in makefile_targets:
                    refs.append(
                        DeadRef(
                            ref=cmd_str, ref_type="command", line=line_num, column=m.start(1) + 1
                        )
                    )
    return refs


def _load_package_json_scripts(repo_root: Path) -> Optional[dict]:
    """Load scripts from package.json, return None if not found."""
    pj = repo_root / "package.json"
    if not pj.exists():
        return None
    try:
        import json

        data = json.loads(pj.read_text(encoding="utf-8"))
        return data.get("scripts", {})
    except (json.JSONDecodeError, IOError):
        return None


def _load_makefile_targets(repo_root: Path) -> Optional[set]:
    """Load targets from Makefile, return None if not found."""
    makefile = repo_root / "Makefile"
    if not makefile.exists():
        return None
    try:
        content = makefile.read_text(encoding="utf-8")
        targets = set()
        for line in content.splitlines():
            m = re.match(r"^([a-zA-Z_][\w.-]*)\s*:", line)
            if m:
                targets.add(m.group(1))
        return targets
    except IOError:
        return None


_TAUTOLOGY_PATTERNS = [
    re.compile(r"\byou are an AI\b", re.IGNORECASE),
    re.compile(r"\byou are a language model\b", re.IGNORECASE),
    re.compile(r"\byou are a helpful assistant\b", re.IGNORECASE),
    re.compile(r"\brespond in (?:the )?(?:same )?language\b", re.IGNORECASE),
    re.compile(r"\bwrite code that works\b", re.IGNORECASE),
    re.compile(r"\bfollow best practices\b", re.IGNORECASE),
    re.compile(r"\bwrite clean code\b", re.IGNORECASE),
    re.compile(r"\buse meaningful (?:variable )?names\b", re.IGNORECASE),
    re.compile(r"\bhandle errors\b", re.IGNORECASE),
    re.compile(r"\bdon'?t introduce bugs\b", re.IGNORECASE),
    re.compile(r"\bmake sure (?:the )?code compiles\b", re.IGNORECASE),
    re.compile(r"\bwrite readable code\b", re.IGNORECASE),
]


def tautological_detector(text: str) -> List[Match]:
    """Detect self-evident instructions that add no value."""
    matches = []
    for line_num, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("#"):
            continue
        for pattern in _TAUTOLOGY_PATTERNS:
            for m in pattern.finditer(line):
                matches.append(
                    Match(
                        text=m.group(),
                        line=line_num,
                        column=m.start() + 1,
                        suggestion="Remove — this is self-evident and wastes context tokens",
                    )
                )
    return matches


_CRITICAL_RE = re.compile(r"\b(MUST|NEVER|ALWAYS|CRITICAL|REQUIRED|MANDATORY)\b")


def critical_position_analyzer(text: str) -> List[PositionIssue]:
    """Detect critical instructions buried in the middle of content."""
    lines = text.splitlines()
    total = len(lines)
    if total < 10:
        return []

    issues = []
    top_zone = max(1, total // 4)
    bottom_zone = total - top_zone

    for line_num, line in enumerate(lines, 1):
        if line.lstrip().startswith("#"):
            continue
        if _CRITICAL_RE.search(line) and top_zone < line_num < bottom_zone:
            issues.append(
                PositionIssue(
                    text=line.strip(),
                    line=line_num,
                    total_lines=total,
                    recommendation="Move critical instructions to the top or bottom of the file where they are more visible",
                )
            )
    return issues
