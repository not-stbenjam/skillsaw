"""Optional checks for literal repository-local Pi resource declarations."""

from skillsaw.blocks.pi import PiPackageBlock, PiSettingsBlock
from skillsaw.context import RepositoryType
from skillsaw.discovery.pi import local_path
from skillsaw.formats.pi import RESOURCE_FIELDS, REMOTE_PREFIXES, string_list
from skillsaw.rule import Rule, Severity


class PiResourcePathsRule(Rule):
    """Find missing local paths when linting a fully assembled Pi package."""

    since = "0.20.0"
    default_enabled = False
    repo_types = frozenset({RepositoryType.PI, RepositoryType.PI_PACKAGE})

    @property
    def rule_id(self):
        return "pi-resource-paths"

    @property
    def description(self):
        return "Literal Pi resource paths should exist in the assembled checkout"

    def default_severity(self):
        return Severity.WARNING

    def check(self, context):
        violations = []
        for cls in (PiPackageBlock, PiSettingsBlock):
            for block in context.lint_tree.find(cls):
                data = block.raw_data
                if not data or block.parse_error:
                    continue
                settings = isinstance(block, PiSettingsBlock)
                config = data if settings else data.get("pi")
                if not isinstance(config, dict):
                    continue
                entries = [
                    (key, entry)
                    for key in RESOURCE_FIELDS
                    if string_list(config.get(key))
                    for entry in config[key]
                ]
                if settings and isinstance(config.get("packages"), list):
                    for item in config["packages"]:
                        source = item.get("source") if isinstance(item, dict) else item
                        if isinstance(source, str):
                            entries.append(("packages", source))
                missing = []
                for key, entry in entries:
                    if entry.startswith(("!", "+", "-", "~", *REMOTE_PREFIXES)) or any(
                        c in entry for c in "*?${}"
                    ):
                        continue
                    path = local_path(block.path.parent, entry, context.root_path)
                    if (
                        path is not None
                        and not context.is_path_excluded(path)
                        and not path.exists()
                    ):
                        missing.append(f"{key}: {entry!r}")
                if missing:
                    violations.append(
                        self.violation(
                            "Missing local Pi resources: "
                            + "; ".join(missing[:5])
                            + ". Paths are relative to this file; build or install bundled resources before checking, or configure rule exclusions.",
                            block=block,
                        )
                    )
        return violations
