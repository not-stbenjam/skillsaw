"""
Rules for validating APM (microsoft/apm) manifest files (apm.yml)
"""

import re
from typing import List, Optional, Dict, Any

import yaml

from skillsaw.rule import Rule, RuleViolation, Severity
from skillsaw.context import RepositoryContext, RepositoryType
from skillsaw.rules.builtin.utils import read_text

SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+")

VALID_TARGETS = {
    "vscode",
    "agents",
    "copilot",
    "claude",
    "cursor",
    "opencode",
    "codex",
    "gemini",
    "windsurf",
    "all",
    "minimal",
}

VALID_TYPES = {"instructions", "skill", "hybrid", "prompts"}

VALID_MCP_TRANSPORTS = {"stdio", "sse", "http", "streamable-http"}

VALID_MCP_PACKAGES = {"npm", "pypi", "oci"}


def _find_apm_manifest(context: RepositoryContext):
    for name in ("apm.yml", "apm.yaml"):
        path = context.root_path / name
        if path.exists():
            return path
    return None


def _parse_apm_manifest(path):
    content = read_text(path)
    if content is None:
        return None, f"Failed to read {path.name}"
    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError as e:
        return None, f"Invalid YAML: {e}"
    if not isinstance(data, dict):
        return None, "Manifest must be a YAML mapping"
    return data, None


def _yaml_key_line(path, key: str) -> Optional[int]:
    content = read_text(path)
    if content is None:
        return None
    pattern = re.compile(rf"^{re.escape(key)}\s*:")
    for i, line in enumerate(content.splitlines(), 1):
        if pattern.match(line):
            return i
    return None


class ApmManifestValidRule(Rule):
    """Validate apm.yml exists and has required fields"""

    repo_types = {RepositoryType.APM_PACKAGE}

    @property
    def rule_id(self) -> str:
        return "apm-manifest-valid"

    @property
    def description(self) -> str:
        return "apm.yml must exist with required name and version fields"

    def default_severity(self) -> Severity:
        return Severity.ERROR

    def check(self, context: RepositoryContext) -> List[RuleViolation]:
        violations = []
        manifest_path = _find_apm_manifest(context)

        if manifest_path is None:
            violations.append(
                self.violation("Missing apm.yml manifest", file_path=context.root_path)
            )
            return violations

        data, error = _parse_apm_manifest(manifest_path)
        if error:
            violations.append(self.violation(error, file_path=manifest_path))
            return violations

        # name (required)
        name = data.get("name")
        if not name:
            violations.append(
                self.violation("Missing required 'name' field", file_path=manifest_path)
            )
        elif not isinstance(name, str):
            violations.append(
                self.violation(
                    "'name' must be a string",
                    file_path=manifest_path,
                    line=_yaml_key_line(manifest_path, "name"),
                )
            )

        # version (required, semver)
        version = data.get("version")
        if not version:
            violations.append(
                self.violation("Missing required 'version' field", file_path=manifest_path)
            )
        elif not isinstance(version, str):
            violations.append(
                self.violation(
                    "'version' must be a string",
                    file_path=manifest_path,
                    line=_yaml_key_line(manifest_path, "version"),
                )
            )
        elif not SEMVER_PATTERN.match(version):
            violations.append(
                self.violation(
                    f"'version' must be semver (MAJOR.MINOR.PATCH): {version!r}",
                    file_path=manifest_path,
                    line=_yaml_key_line(manifest_path, "version"),
                )
            )

        # description (optional, string)
        if "description" in data and not isinstance(data["description"], str):
            violations.append(
                self.violation(
                    "'description' must be a string",
                    file_path=manifest_path,
                    line=_yaml_key_line(manifest_path, "description"),
                )
            )

        # author (optional, string)
        if "author" in data and not isinstance(data["author"], str):
            violations.append(
                self.violation(
                    "'author' must be a string",
                    file_path=manifest_path,
                    line=_yaml_key_line(manifest_path, "author"),
                )
            )

        # license (optional, string — SPDX)
        if "license" in data and not isinstance(data["license"], str):
            violations.append(
                self.violation(
                    "'license' must be a string (SPDX identifier)",
                    file_path=manifest_path,
                    line=_yaml_key_line(manifest_path, "license"),
                )
            )

        return violations


class ApmTargetValidRule(Rule):
    """Validate the target field in apm.yml"""

    repo_types = {RepositoryType.APM_PACKAGE}

    @property
    def rule_id(self) -> str:
        return "apm-target-valid"

    @property
    def description(self) -> str:
        return "apm.yml target must use valid target values"

    def default_severity(self) -> Severity:
        return Severity.ERROR

    def check(self, context: RepositoryContext) -> List[RuleViolation]:
        violations = []
        manifest_path = _find_apm_manifest(context)
        if manifest_path is None:
            return violations

        data, error = _parse_apm_manifest(manifest_path)
        if error or data is None:
            return violations

        target = data.get("target")
        if target is None:
            return violations

        line = _yaml_key_line(manifest_path, "target")

        if isinstance(target, str):
            if target not in VALID_TARGETS:
                violations.append(
                    self.violation(
                        f"Unknown target {target!r} (valid: {', '.join(sorted(VALID_TARGETS))})",
                        file_path=manifest_path,
                        line=line,
                    )
                )
        elif isinstance(target, list):
            for item in target:
                if not isinstance(item, str):
                    violations.append(
                        self.violation(
                            "Target list items must be strings",
                            file_path=manifest_path,
                            line=line,
                        )
                    )
                    break
                if item not in VALID_TARGETS:
                    violations.append(
                        self.violation(
                            f"Unknown target {item!r} (valid: {', '.join(sorted(VALID_TARGETS))})",
                            file_path=manifest_path,
                            line=line,
                        )
                    )
            if isinstance(target, list) and "all" in target and len(target) > 1:
                violations.append(
                    self.violation(
                        "'all' target cannot be combined with other targets",
                        file_path=manifest_path,
                        line=line,
                    )
                )
        else:
            violations.append(
                self.violation(
                    "'target' must be a string or list of strings",
                    file_path=manifest_path,
                    line=line,
                )
            )

        return violations


class ApmTypeValidRule(Rule):
    """Validate the type field in apm.yml"""

    repo_types = {RepositoryType.APM_PACKAGE}

    @property
    def rule_id(self) -> str:
        return "apm-type-valid"

    @property
    def description(self) -> str:
        return "apm.yml type must be a valid package type"

    def default_severity(self) -> Severity:
        return Severity.ERROR

    def check(self, context: RepositoryContext) -> List[RuleViolation]:
        violations = []
        manifest_path = _find_apm_manifest(context)
        if manifest_path is None:
            return violations

        data, error = _parse_apm_manifest(manifest_path)
        if error or data is None:
            return violations

        pkg_type = data.get("type")
        if pkg_type is None:
            return violations

        if not isinstance(pkg_type, str):
            violations.append(
                self.violation(
                    "'type' must be a string",
                    file_path=manifest_path,
                    line=_yaml_key_line(manifest_path, "type"),
                )
            )
        elif pkg_type not in VALID_TYPES:
            violations.append(
                self.violation(
                    f"Unknown type {pkg_type!r} (valid: {', '.join(sorted(VALID_TYPES))})",
                    file_path=manifest_path,
                    line=_yaml_key_line(manifest_path, "type"),
                )
            )

        return violations


class ApmDependenciesValidRule(Rule):
    """Validate dependencies in apm.yml"""

    repo_types = {RepositoryType.APM_PACKAGE}

    @property
    def rule_id(self) -> str:
        return "apm-dependencies-valid"

    @property
    def description(self) -> str:
        return "apm.yml dependencies must have valid apm and mcp entries"

    def default_severity(self) -> Severity:
        return Severity.ERROR

    def check(self, context: RepositoryContext) -> List[RuleViolation]:
        violations = []
        manifest_path = _find_apm_manifest(context)
        if manifest_path is None:
            return violations

        data, error = _parse_apm_manifest(manifest_path)
        if error or data is None:
            return violations

        deps = data.get("dependencies")
        if deps is None:
            return violations

        if not isinstance(deps, dict):
            violations.append(
                self.violation(
                    "'dependencies' must be a mapping",
                    file_path=manifest_path,
                    line=_yaml_key_line(manifest_path, "dependencies"),
                )
            )
            return violations

        apm_deps = deps.get("apm")
        if apm_deps is not None:
            violations.extend(self._check_apm_deps(apm_deps, manifest_path))

        mcp_deps = deps.get("mcp")
        if mcp_deps is not None:
            violations.extend(self._check_mcp_deps(mcp_deps, manifest_path))

        return violations

    def _check_apm_deps(self, apm_deps, manifest_path) -> List[RuleViolation]:
        violations = []
        if not isinstance(apm_deps, list):
            violations.append(
                self.violation(
                    "'dependencies.apm' must be a list",
                    file_path=manifest_path,
                )
            )
            return violations

        for i, dep in enumerate(apm_deps):
            if isinstance(dep, str):
                continue
            if isinstance(dep, dict):
                if "git" not in dep and "path" not in dep:
                    violations.append(
                        self.violation(
                            f"dependencies.apm[{i}]: object form requires 'git' or 'path'",
                            file_path=manifest_path,
                        )
                    )
                if "alias" in dep:
                    alias = dep["alias"]
                    if isinstance(alias, str) and not re.match(r"^[a-zA-Z0-9._-]+$", alias):
                        violations.append(
                            self.violation(
                                f"dependencies.apm[{i}]: 'alias' must match [a-zA-Z0-9._-]+",
                                file_path=manifest_path,
                            )
                        )
            else:
                violations.append(
                    self.violation(
                        f"dependencies.apm[{i}]: must be a string or object",
                        file_path=manifest_path,
                    )
                )

        return violations

    def _check_mcp_deps(self, mcp_deps, manifest_path) -> List[RuleViolation]:
        violations = []
        if not isinstance(mcp_deps, list):
            violations.append(
                self.violation(
                    "'dependencies.mcp' must be a list",
                    file_path=manifest_path,
                )
            )
            return violations

        for i, dep in enumerate(mcp_deps):
            if isinstance(dep, str):
                continue
            if isinstance(dep, dict):
                violations.extend(self._check_mcp_dep_object(i, dep, manifest_path))
            else:
                violations.append(
                    self.violation(
                        f"dependencies.mcp[{i}]: must be a string or object",
                        file_path=manifest_path,
                    )
                )

        return violations

    def _check_mcp_dep_object(
        self, index: int, dep: Dict[str, Any], manifest_path
    ) -> List[RuleViolation]:
        violations = []
        prefix = f"dependencies.mcp[{index}]"

        if "name" not in dep:
            violations.append(
                self.violation(
                    f"{prefix}: missing required 'name'",
                    file_path=manifest_path,
                )
            )

        transport = dep.get("transport")
        registry = dep.get("registry", True)
        is_self_defined = registry is False

        if transport is not None:
            if not isinstance(transport, str):
                violations.append(
                    self.violation(
                        f"{prefix}: 'transport' must be a string",
                        file_path=manifest_path,
                    )
                )
            elif transport not in VALID_MCP_TRANSPORTS:
                violations.append(
                    self.violation(
                        f"{prefix}: unknown transport {transport!r} "
                        f"(valid: {', '.join(sorted(VALID_MCP_TRANSPORTS))})",
                        file_path=manifest_path,
                    )
                )

        if is_self_defined:
            if transport is None:
                violations.append(
                    self.violation(
                        f"{prefix}: self-defined server (registry: false) requires 'transport'",
                        file_path=manifest_path,
                    )
                )
            elif isinstance(transport, str):
                if transport == "stdio" and "command" not in dep:
                    violations.append(
                        self.violation(
                            f"{prefix}: stdio transport requires 'command'",
                            file_path=manifest_path,
                        )
                    )
                elif transport in ("http", "sse", "streamable-http") and "url" not in dep:
                    violations.append(
                        self.violation(
                            f"{prefix}: {transport} transport requires 'url'",
                            file_path=manifest_path,
                        )
                    )

        if "package" in dep:
            pkg = dep["package"]
            if isinstance(pkg, str) and pkg not in VALID_MCP_PACKAGES:
                violations.append(
                    self.violation(
                        f"{prefix}: unknown package type {pkg!r} "
                        f"(valid: {', '.join(sorted(VALID_MCP_PACKAGES))})",
                        file_path=manifest_path,
                    )
                )

        if "env" in dep and not isinstance(dep["env"], dict):
            violations.append(
                self.violation(
                    f"{prefix}: 'env' must be a mapping",
                    file_path=manifest_path,
                )
            )

        if "headers" in dep and not isinstance(dep["headers"], dict):
            violations.append(
                self.violation(
                    f"{prefix}: 'headers' must be a mapping",
                    file_path=manifest_path,
                )
            )

        if "tools" in dep:
            tools = dep["tools"]
            if not isinstance(tools, list):
                violations.append(
                    self.violation(
                        f"{prefix}: 'tools' must be a list",
                        file_path=manifest_path,
                    )
                )
            elif not all(isinstance(t, str) for t in tools):
                violations.append(
                    self.violation(
                        f"{prefix}: 'tools' items must be strings",
                        file_path=manifest_path,
                    )
                )

        return violations


class ApmCompilationValidRule(Rule):
    """Validate compilation config in apm.yml"""

    repo_types = {RepositoryType.APM_PACKAGE}

    VALID_STRATEGIES = {"distributed", "single-file"}

    @property
    def rule_id(self) -> str:
        return "apm-compilation-valid"

    @property
    def description(self) -> str:
        return "apm.yml compilation config must use valid values"

    def default_severity(self) -> Severity:
        return Severity.WARNING

    def check(self, context: RepositoryContext) -> List[RuleViolation]:
        violations = []
        manifest_path = _find_apm_manifest(context)
        if manifest_path is None:
            return violations

        data, error = _parse_apm_manifest(manifest_path)
        if error or data is None:
            return violations

        compilation = data.get("compilation")
        if compilation is None:
            return violations

        if not isinstance(compilation, dict):
            violations.append(
                self.violation(
                    "'compilation' must be a mapping",
                    file_path=manifest_path,
                    line=_yaml_key_line(manifest_path, "compilation"),
                )
            )
            return violations

        strategy = compilation.get("strategy")
        if strategy is not None:
            if not isinstance(strategy, str):
                violations.append(
                    self.violation(
                        "'compilation.strategy' must be a string",
                        file_path=manifest_path,
                    )
                )
            elif strategy not in self.VALID_STRATEGIES:
                violations.append(
                    self.violation(
                        f"Unknown compilation strategy {strategy!r} "
                        f"(valid: {', '.join(sorted(self.VALID_STRATEGIES))})",
                        file_path=manifest_path,
                    )
                )

        output = compilation.get("output")
        if output is not None and not isinstance(output, str):
            violations.append(
                self.violation(
                    "'compilation.output' must be a string",
                    file_path=manifest_path,
                )
            )

        for bool_field in ("resolve_links", "source_attribution"):
            val = compilation.get(bool_field)
            if val is not None and not isinstance(val, bool):
                violations.append(
                    self.violation(
                        f"'compilation.{bool_field}' must be a boolean",
                        file_path=manifest_path,
                    )
                )

        exclude = compilation.get("exclude")
        if exclude is not None:
            if not isinstance(exclude, list):
                violations.append(
                    self.violation(
                        "'compilation.exclude' must be a list",
                        file_path=manifest_path,
                    )
                )
            elif not all(isinstance(e, str) for e in exclude):
                violations.append(
                    self.violation(
                        "'compilation.exclude' items must be strings",
                        file_path=manifest_path,
                    )
                )

        target = compilation.get("target")
        if target is not None:
            if not isinstance(target, str):
                violations.append(
                    self.violation(
                        "'compilation.target' must be a string",
                        file_path=manifest_path,
                    )
                )
            elif target not in VALID_TARGETS:
                violations.append(
                    self.violation(
                        f"Unknown compilation target {target!r} "
                        f"(valid: {', '.join(sorted(VALID_TARGETS))})",
                        file_path=manifest_path,
                    )
                )

        chatmode = compilation.get("chatmode")
        if chatmode is not None and not isinstance(chatmode, str):
            violations.append(
                self.violation(
                    "'compilation.chatmode' must be a string",
                    file_path=manifest_path,
                )
            )

        placement = compilation.get("placement")
        if placement is not None:
            if not isinstance(placement, dict):
                violations.append(
                    self.violation(
                        "'compilation.placement' must be a mapping",
                        file_path=manifest_path,
                    )
                )
            else:
                min_instr = placement.get("min_instructions_per_file")
                if min_instr is not None and not isinstance(min_instr, int):
                    violations.append(
                        self.violation(
                            "'compilation.placement.min_instructions_per_file' must be an integer",
                            file_path=manifest_path,
                        )
                    )

        return violations
