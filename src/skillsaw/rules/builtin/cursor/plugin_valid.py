"""Validate Cursor native manifests and component references."""

from skillsaw.blocks.cursor import CursorPluginBlock
from skillsaw.formats import cursor
from skillsaw.formats.cursor_schema import validator
from skillsaw.paths import safe_exists, safe_is_file
from skillsaw.repository_types import RepositoryType
from skillsaw.rule import Rule, Severity
from skillsaw.diagnostics import safe_display


class CursorPluginValidRule(Rule):
    since = "0.21.0"
    repo_types = frozenset({RepositoryType.CURSOR_PLUGIN, RepositoryType.CURSOR_MARKETPLACE})

    @property
    def rule_id(self):
        return "cursor-plugin-json-valid"

    @property
    def description(self):
        return "Cursor plugin manifests must declare valid metadata and contained components"

    def default_severity(self):
        return Severity.ERROR

    def check(self, context):
        violations = []
        seen = set()
        for block in context.lint_tree.find(CursorPluginBlock):
            if block.path not in seen:
                seen.add(block.path)
                if block.parse_error or block.raw_data is None:
                    violations.append(
                        self.violation(
                            f"Invalid Cursor manifest: {block.parse_error or 'expected a JSON object'}",
                            file_path=block.path,
                        )
                    )
                # Even malformed native JSON leaves catalog components active.
                # Marketplace-only entries have no standalone manifest.
                elif block.path.name == "plugin.json":
                    errors = list(validator("plugin").iter_errors(block.raw_data))
                    for error in errors:
                        location = ".".join(str(p) for p in error.absolute_path) or "manifest"
                        violations.append(
                            self.violation(
                                f"{safe_display(location)}: {safe_display(error.message)}",
                                file_path=block.path,
                            )
                        )
            data = block.effective_data
            for field in (*cursor.COMPONENT_EXTENSIONS, "hooks", "mcpServers"):
                if field not in data:
                    continue
                source_path = block.component_sources.get(field, block.path)
                raw = data[field]
                for item in raw if isinstance(raw, list) else [raw]:
                    if not isinstance(item, str):
                        continue  # schema owns field shapes
                    if cursor.safe_component(block.plugin_dir, item) is None:
                        violations.append(
                            self.violation(
                                f"'{field}' path {safe_display(repr(item))} must stay inside the plugin (no absolute paths or '..')",
                                file_path=source_path,
                            )
                        )
                        continue
                    paths = cursor.component_paths(block.plugin_dir, {field: item}, field)
                    if not any(safe_exists(p) for p in paths):
                        violations.append(
                            self.violation(
                                f"'{field}' path {safe_display(repr(item))} matches no component; correct the path or remove the override",
                                file_path=source_path,
                            )
                        )
                    elif field in ("hooks", "mcpServers") and not all(
                        safe_is_file(p) for p in paths
                    ):
                        violations.append(
                            self.violation(
                                f"'{field}' must reference a configuration file",
                                file_path=source_path,
                            )
                        )
        return violations
