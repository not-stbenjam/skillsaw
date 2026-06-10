"""Content unlinked internal reference rule"""

import re
from collections import defaultdict
from pathlib import Path, PurePath
from typing import Dict, List

from skillsaw.rule import AutofixConfidence, AutofixResult, Rule, RuleViolation, Severity
from skillsaw.context import RepositoryContext
from skillsaw.markdown_doc import MarkdownDoc
from skillsaw.rules.builtin.content_analysis import (
    gather_all_content_blocks,
)


class ContentUnlinkedInternalReferenceRule(Rule):
    """Detect bare path-like strings that are not wrapped in markdown link syntax"""

    autofix_confidence = AutofixConfidence.SAFE

    formats = None
    since = "0.9.0"
    repo_types = None

    config_schema = {
        "patterns": {
            "type": "list",
            "default": ["./**/*.*", "references/**/*.md"],
            "description": "Glob patterns for path-like strings to flag when unlinked",
        },
    }

    # Match path-like strings: contain / and a file extension, or start with ./
    _PATH_LIKE_RE = re.compile(
        r"(?<!\()"  # not preceded by ( (would be inside link syntax)
        r"(?:"
        r"\./[\w./_-]+"  # starts with ./
        r"|"
        r"[\w._-]+(?:/[\w._-]+)+\.[\w]{1,10}"  # contains / and has extension
        r")"
        r"(?!\))"  # not followed by ) (would be inside link syntax)
    )

    # Detect URLs so we can skip path-like fragments inside them
    _URL_RE = re.compile(r"https?://[^\s)]+")

    @property
    def rule_id(self) -> str:
        return "content-unlinked-internal-reference"

    @property
    def description(self) -> str:
        return "Detect bare path-like strings not wrapped in markdown link syntax"

    def default_severity(self) -> Severity:
        return Severity.INFO

    def _is_inside_url(self, text: str, match_start: int, match_end: int) -> bool:
        """Check if a match position falls inside a URL."""
        for url_match in self._URL_RE.finditer(text):
            if url_match.start() <= match_start and match_end <= url_match.end():
                return True
        return False

    def check(self, context: RepositoryContext) -> List[RuleViolation]:
        root = context.root_path.resolve()
        patterns = self.config.get("patterns", self.config_schema["patterns"]["default"])
        violations = []
        for cf in gather_all_content_blocks(context):
            md = cf.markdown
            if md is None:
                continue
            raw_body = cf.read_body(strip_code_blocks=False)
            if not raw_body:
                continue
            body_lines = raw_body.split("\n")

            for seg in md.text_segments():
                bl = md.body_line(seg.file_line)
                if bl < 1 or bl > len(body_lines):
                    continue
                full_line = body_lines[bl - 1]
                if not full_line.strip():
                    continue
                if re.match(r"^\s*@\S", full_line):
                    continue
                for match in self._PATH_LIKE_RE.finditer(seg.text):
                    path_str = match.group(0)
                    if self._is_inside_url(seg.text, match.start(), match.end()):
                        continue
                    if not any(PurePath(path_str).match(p) for p in patterns):
                        continue
                    resolved = (cf.path.parent / path_str).resolve()
                    file_exists = False
                    try:
                        resolved.relative_to(root)
                        file_exists = resolved.exists()
                    except ValueError:
                        pass
                    msg = f"Unlinked path reference: '{path_str}' — consider wrapping in link syntax [{path_str}]({path_str})"
                    if file_exists:
                        msg += " (file exists, autofixable)"
                    violations.append(self.violation(msg, block=cf, line=bl))

            # Also check code spans where the entire content is a path (exact content case)
            for cs in md.code_spans():
                content = cs.content.strip()
                if not content or "/" not in content:
                    continue
                m = self._PATH_LIKE_RE.match(content)
                if not m or m.end() != len(content):
                    continue
                path_str = content
                if not any(PurePath(path_str).match(p) for p in patterns):
                    continue
                bl = md.body_line(cs.file_line)
                if bl < 1 or bl > len(body_lines):
                    continue
                full_line = body_lines[bl - 1]
                if re.match(r"^\s*@\S", full_line):
                    continue
                resolved = (cf.path.parent / path_str).resolve()
                file_exists = False
                try:
                    resolved.relative_to(root)
                    file_exists = resolved.exists()
                except ValueError:
                    pass
                msg = f"Unlinked path reference: '{path_str}' — consider wrapping in link syntax [{path_str}]({path_str})"
                if file_exists:
                    msg += " (file exists, autofixable)"
                violations.append(self.violation(msg, block=cf, line=bl))

        return violations

    def fix(
        self, context: RepositoryContext, violations: List[RuleViolation], **kwargs: object
    ) -> List[AutofixResult]:
        fixes_by_file: Dict[Path, List[tuple]] = defaultdict(list)
        for v in violations:
            if not v.file_path or "autofixable" not in v.message:
                continue
            path_str = v.message.split("'")[1]
            fixes_by_file[v.file_path].append((path_str, v))

        results: List[AutofixResult] = []
        for fpath, replacements in fixes_by_file.items():
            try:
                content = fpath.read_text(encoding="utf-8")
            except OSError:
                continue
            md = MarkdownDoc(content)
            edits = []
            violations_fixed = []
            used_positions = set()

            for path_str, v in replacements:
                target_line = v.file_line
                if target_line is None:
                    continue

                found = False
                # Try text segments first (bare paths)
                for seg in md.text_segments():
                    if seg.file_line != target_line:
                        continue
                    for match in self._PATH_LIKE_RE.finditer(seg.text):
                        if match.group(0) != path_str:
                            continue
                        col = seg.col_start + match.start()
                        col_end = seg.col_start + match.end()
                        pos_key = (target_line, col)
                        if pos_key in used_positions:
                            continue
                        used_positions.add(pos_key)
                        edits.append((target_line, col, col_end, f"[{path_str}]({path_str})"))
                        violations_fixed.append(v)
                        found = True
                        break
                    if found:
                        break

                if found:
                    continue

                # Try code spans (exact content → wrap backticks in link)
                for cs in md.code_spans():
                    if cs.file_line != target_line:
                        continue
                    if cs.content.strip() != path_str:
                        continue
                    pos_key = (target_line, cs.col_start)
                    if pos_key in used_positions:
                        continue
                    used_positions.add(pos_key)
                    link_text = f"{cs.markup}{cs.content}{cs.markup}"
                    edits.append(
                        (target_line, cs.col_start, cs.col_end, f"[{link_text}]({path_str})")
                    )
                    violations_fixed.append(v)
                    break

            if edits:
                fixed = MarkdownDoc.splice(content, edits)
                results.append(
                    AutofixResult(
                        rule_id=self.rule_id,
                        file_path=fpath,
                        confidence=AutofixConfidence.SAFE,
                        original_content=content,
                        fixed_content=fixed,
                        description=f"Wrap {len(violations_fixed)} bare path(s) in markdown link syntax",
                        violations_fixed=violations_fixed,
                    )
                )
        return results
