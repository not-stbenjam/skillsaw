"""Report ignored or unavailable OpenClaw package resources."""

from skillsaw.context import RepositoryContext
from skillsaw.diagnostics import safe_display
from skillsaw.formats.openclaw import read_manifest, contained_file
from skillsaw.lint_target import OpenClawConfigNode, OpenClawPackageConfigNode
from skillsaw.paths import contained_resolve, safe_resolve, safe_is_dir, safe_is_file
from skillsaw.repository_types import RepositoryType
from skillsaw.rule import Rule, RuleViolation, Severity
from typing import List
from skillsaw.formats.openclaw import read_package, runtime_extensions


class OpenClawResourcesRule(Rule):
    """Inspect declared skills and optionally built runtime entrypoints."""

    since = "0.21.0"
    repo_types = frozenset({RepositoryType.OPENCLAW_PLUGIN})
    default_enabled = False
    config_schema = {
        "check-skills-exist": {
            "type": "bool",
            "default": True,
            "description": "Report declared skill roots that are not existing directories",
        },
        "check-entrypoints-exist": {
            "type": "bool",
            "default": False,
            "description": "Report declared entrypoints that are not existing files; enable after building",
        },
    }

    @property
    def rule_id(self) -> str:
        return "openclaw-resources"

    @property
    def description(self) -> str:
        return "OpenClaw resources should resolve inside their package and exist when loaded"

    def default_severity(self) -> Severity:
        return Severity.WARNING

    def check(self, context: RepositoryContext) -> List[RuleViolation]:
        violations = []
        check_entries = self.setting("check-entrypoints-exist")
        check_skills = self.setting("check-skills-exist")
        for node in context.lint_tree.find(OpenClawConfigNode):
            root = safe_resolve(node.plugin_dir)
            if root is None or not contained_file(node.plugin_dir, node.path.name):
                continue
            package = isinstance(node, OpenClawPackageConfigNode)
            data, error = read_package(node.path) if package else read_manifest(node.path)
            if error or not isinstance(data, dict):
                continue
            if package:
                metadata = data.get("openclaw")
                if not isinstance(metadata, dict):
                    continue
                runtime, runtime_error = runtime_extensions(metadata)
                declarations = [
                    (
                        "openclaw.extensions",
                        metadata.get("extensions"),
                        check_entries and not runtime and not runtime_error,
                    ),
                    ("openclaw.runtimeExtensions", runtime, check_entries and not runtime_error),
                ]
            else:
                declarations = [("skills", data.get("skills"), check_skills)]
            for field, values, check_exists in declarations:
                if values is None:
                    continue
                if not isinstance(values, list):
                    if not package:
                        violations.append(
                            self.violation(
                                "'skills' must be an array of non-empty paths; OpenClaw ignores this value",
                                file_path=node.path,
                            )
                        )
                    continue
                problems = []
                for raw in values:
                    if not isinstance(raw, str) or not raw.strip():
                        if not package:
                            problems.append("non-string or empty path is ignored")
                        continue
                    target = contained_resolve(node.plugin_dir / raw.strip(), root)
                    if target is None:
                        problems.append(f"{safe_display(raw)!r} escapes the plugin directory")
                    elif not package and check_exists and not safe_is_dir(target):
                        problems.append(
                            f"{safe_display(raw)!r} is not an existing skill directory; install dependencies if provided by a package"
                        )
                    elif package and check_exists and not safe_is_file(target):
                        problems.append(
                            f"{safe_display(raw)!r} is not an existing runtime file; build the package first"
                        )
                if field == "openclaw.extensions" and values == []:
                    problems.append("empty extension list disables entrypoint discovery")
                if problems:
                    violations.append(
                        self.violation(
                            f"'{field}': " + "; ".join(dict.fromkeys(problems)), file_path=node.path
                        )
                    )
        return violations
