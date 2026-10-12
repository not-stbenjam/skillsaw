"""Generator sources are instructions; their configuration is not prose."""

from dataclasses import dataclass, field
from typing import ClassVar, Optional, Tuple

from skillsaw.formats.generators import parse_rulesync_frontmatter
from skillsaw.lint_target import LintTarget
from skillsaw.utils import read_toml

from .base import FileContentBlock
from .frontmatter import FrontmatteredBlock
from .json_config import JsonConfigBlock


@dataclass(eq=False)
class RulerRuleBlock(FileContentBlock):
    """Ruler concatenates rule Markdown verbatim, including apparent frontmatter."""

    category: str = "instruction"


@dataclass(eq=False)
class RulesyncRuleBlock(FrontmatteredBlock):
    """The body and description are authored instructions, targets/globs are data."""

    category: str = "instruction"
    content_lintable_fields: Tuple[str, ...] = ("description",)

    @property
    def raw_data(self):
        self._ensure_parsed()
        return self._fm_parsed[0]

    def _parse_frontmatter_content(self, content):
        return parse_rulesync_frontmatter(content)


@dataclass(eq=False)
class RulerConfigBlock(LintTarget):
    _parsed: Optional[tuple] = field(default=None, init=False, repr=False)

    def _ensure_parsed(self):
        if self._parsed is None:
            self._parsed = read_toml(self.path)

    @property
    def raw_data(self):
        self._ensure_parsed()
        return self._parsed[0]

    @property
    def parse_error(self):
        self._ensure_parsed()
        return self._parsed[1]

    def tree_label(self):
        return f"{self.path.name} (ruler config)"


@dataclass(eq=False)
class RulesyncConfigBlock(JsonConfigBlock):
    category: str = "rulesync config"
    jsonc: ClassVar[bool] = True
    # jsonc-parser, used by the released config loader, keeps the last key.
    duplicate_keys_fatal: ClassVar[bool] = False
