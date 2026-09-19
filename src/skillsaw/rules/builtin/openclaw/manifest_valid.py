"""Validate the native OpenClaw manifest's stable loading contract."""

from skillsaw.context import RepositoryContext
from skillsaw.formats.openclaw import read_manifest
from skillsaw.lint_target import OpenClawPluginConfigNode
from skillsaw.paths import contained_resolve, safe_resolve
from skillsaw.repository_types import RepositoryType
from skillsaw.rule import Rule, RuleViolation, Severity
from typing import List


class OpenClawManifestValidRule(Rule):
    """Check native manifest syntax, identity, and configuration schema."""

    since = "0.21.0"
    repo_types = frozenset({RepositoryType.OPENCLAW_PLUGIN})
    default_enabled = False

    @property
    def rule_id(self) -> str:
        return "openclaw-manifest-valid"

    @property
    def description(self) -> str:
        return "Native OpenClaw manifests must declare an id and object configSchema"

    def default_severity(self) -> Severity:
        return Severity.ERROR

    def check(self, context: RepositoryContext) -> List[RuleViolation]:
        violations = []
        for node in context.lint_tree.find(OpenClawPluginConfigNode):
            root = safe_resolve(node.plugin_dir)
            if root is None or contained_resolve(node.path, root) is None:
                violations.append(
                    self.violation("Manifest escapes the plugin directory", file_path=node.path)
                )
                continue
            data, error = read_manifest(node.path)
            if error:
                violations.append(
                    self.violation(f"Invalid native manifest: {error}", file_path=node.path)
                )
                continue
            if not isinstance(data, dict):
                violations.append(self.violation("Manifest must be an object", file_path=node.path))
                continue
            identifier = data.get("id")
            if not isinstance(identifier, str) or not identifier.strip():
                violations.append(
                    self.violation("Declare a non-empty string 'id'", file_path=node.path)
                )
            elif identifier.strip().lower() == "node-mcp":
                violations.append(
                    self.violation(
                        "Plugin id 'node-mcp' is reserved by OpenClaw core", file_path=node.path
                    )
                )
            if not isinstance(data.get("configSchema"), dict):
                violations.append(
                    self.violation(
                        "Declare an object 'configSchema' ({} is valid)", file_path=node.path
                    )
                )
        return violations
