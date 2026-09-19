"""Validate Pi package manifests and resource-related project settings."""

from typing import List

from skillsaw.blocks.pi import PiPackageBlock, PiSettingsBlock
from skillsaw.context import RepositoryContext, RepositoryType
from skillsaw.formats.pi import RESOURCE_FIELDS, string_list
from skillsaw.rule import Rule, RuleViolation, Severity


class PiConfigValidRule(Rule):
    """Validate resource declarations without imposing an npm or settings schema."""

    since = "0.21.0"
    repo_types = frozenset({RepositoryType.PI, RepositoryType.PI_PACKAGE})

    @property
    def rule_id(self) -> str:
        return "pi-config-valid"

    @property
    def description(self) -> str:
        return "Pi package and project resource declarations must have valid types"

    def default_severity(self) -> Severity:
        # Current Pi ignores malformed manifest fields rather than crashing.
        return Severity.WARNING

    def check(self, context: RepositoryContext) -> List[RuleViolation]:
        violations = []
        for cls in (PiPackageBlock, PiSettingsBlock):
            for block in context.lint_tree.find(cls):
                data = block.raw_data
                if block.parse_error or not isinstance(data, dict):
                    violations.append(
                        self.violation(
                            "Expected a JSON object"
                            + (f": {block.parse_error}" if block.parse_error else ""),
                            block=block,
                        )
                    )
                    continue
                settings = isinstance(block, PiSettingsBlock)
                config = data if settings else data.get("pi", {})
                if not isinstance(config, dict):
                    violations.append(
                        self.violation(
                            "package.json 'pi' must be an object; declare resource arrays inside it",
                            block=block,
                        )
                    )
                    continue
                bad = []

                def lists(mapping, prefix):
                    for key in RESOURCE_FIELDS:
                        if key in mapping and not string_list(mapping[key]):
                            bad.append(f"{prefix}{key} (expected an array of strings)")

                lists(config, "" if settings else "pi.")
                if settings and "packages" in config:
                    packages = config["packages"]
                    if not isinstance(packages, list):
                        bad.append("packages (expected an array)")
                    else:
                        for index, entry in enumerate(packages):
                            prefix = f"packages[{index}]"
                            if isinstance(entry, str):
                                if not entry.strip():
                                    bad.append(f"{prefix} (expected a nonempty source)")
                            elif isinstance(entry, dict):
                                if (
                                    not isinstance(entry.get("source"), str)
                                    or not entry["source"].strip()
                                ):
                                    bad.append(f"{prefix}.source (expected a nonempty string)")
                                lists(entry, prefix + ".")
                                if "autoload" in entry and not isinstance(entry["autoload"], bool):
                                    bad.append(f"{prefix}.autoload (expected a boolean)")
                            else:
                                bad.append(f"{prefix} (expected a source string or object)")
                if bad:
                    detail = "; ".join(bad[:5])
                    if len(bad) > 5:
                        detail += f"; and {len(bad) - 5} more"
                    violations.append(
                        self.violation(f"Invalid Pi resource declarations: {detail}", block=block)
                    )
        return violations
