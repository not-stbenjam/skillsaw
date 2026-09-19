"""Native Cursor plugin configuration and prose nodes."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar

from skillsaw.lint_target import LintTarget
from .frontmatter import FrontmatteredBlock, CursorRuleBlock, BodyContent
from .json_config import JsonConfigBlock, CursorHooksBlock, CursorMcpBlock, _InlineJsonPayload


@dataclass(eq=False)
class CursorAgentBlock(FrontmatteredBlock):
    category: str = "agent"


@dataclass(eq=False)
class CursorPluginNode(LintTarget):
    def tree_label(self):
        return f"{self.path.name}/ [cursor plugin]"

    def provenance_dir(self):
        return self.path


@dataclass(eq=False)
class CursorMarketplaceBlock(JsonConfigBlock):
    strict_json: ClassVar[bool] = True
    duplicate_keys_fatal: ClassVar[bool] = False

    def tree_label(self):
        return "marketplace.json [cursor]"


@dataclass(eq=False)
class CursorPluginBlock(JsonConfigBlock):
    strict_json: ClassVar[bool] = True
    duplicate_keys_fatal: ClassVar[bool] = False
    plugin_dir: Path | None = None
    effective_data: dict = field(default_factory=dict)
    component_sources: dict[str, Path] = field(default_factory=dict)

    def tree_label(self):
        return "plugin.json [cursor]"


@dataclass(eq=False)
class CursorPluginHooksBlock(CursorHooksBlock):
    """Plugin hooks omit the project-only required version field."""

    duplicate_keys_fatal: ClassVar[bool] = False


@dataclass(eq=False)
class CursorInlineHooksBlock(_InlineJsonPayload, CursorPluginHooksBlock):
    inline_data: Any = None

    def tree_label(self) -> str:
        return f"{self.path.name} (inline Cursor hooks)"


@dataclass(eq=False)
class CursorPluginMcpBlock(CursorMcpBlock):
    duplicate_keys_fatal: ClassVar[bool] = False


@dataclass(eq=False)
class CursorInlineMcpBlock(_InlineJsonPayload, CursorPluginMcpBlock):
    inline_data: Any = None

    def tree_label(self) -> str:
        return f"{self.path.name} (inline Cursor MCP)"


@dataclass(eq=False)
class CursorRuleValidationBlock(CursorRuleBlock):
    """Cursor's parser view of prose already owned by another block."""

    def _build_children(self) -> None:
        super()._build_children()
        self.children = [child for child in self.children if not isinstance(child, BodyContent)]

    def estimate_tokens(self) -> int:
        return 0

    def tree_label(self) -> str:
        return f"{self.path.name} (Cursor rule validation)"
