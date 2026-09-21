"""Pi package metadata, project settings, and native resources."""

from dataclasses import dataclass, field
from typing import ClassVar

from .frontmatter import FrontmatteredBlock
from .pi_frontmatter import parse_pi_frontmatter
from .json_config import JsonConfigBlock
from ..lint_target import LintTarget


@dataclass(eq=False)
class PiPackageNode(LintTarget):
    """Container for one Pi package."""


@dataclass(eq=False)
class PiPackageBlock(JsonConfigBlock):
    """package.json containing Pi resource declarations."""

    strict_json: ClassVar[bool] = True
    duplicate_keys_fatal: ClassVar[bool] = False


@dataclass(eq=False)
class PiSettingsBlock(JsonConfigBlock):
    """Project .pi/settings.json; only resource settings are validated."""

    strict_json: ClassVar[bool] = True
    duplicate_keys_fatal: ClassVar[bool] = False


@dataclass(eq=False)
class PiPromptBlock(FrontmatteredBlock):
    """A prompt template, loaded on demand."""

    category: str = "command"


@dataclass(eq=False)
class PiSkillNode(LintTarget):
    """A directory-style Pi skill: SKILL.md plus its bundled support files.

    Pi loads a skill directory the way Agent Skills does, so the
    ``references/`` prose is agent context and the bundled files are
    subject to the same reachability check. Deliberately not SkillNode:
    the ``agentskill-*`` authoring rules read that container and would
    hold Pi's optional-name dialect to another host's convention.
    """

    def tree_label(self) -> str:
        return f"{self.path.name}/ [pi skill]"


@dataclass(eq=False)
class PiSkillBlock(FrontmatteredBlock):
    """Pi skill dialect, including flat Markdown and optional names.

    Deliberately not SkillBlock: Pi allows a missing name and does not
    require the name to match the directory. Portable authoring checks must
    not rewrite valid Pi metadata into another host's convention.
    """

    category: str = "skill"
    _pi_key_lines: dict = field(default_factory=dict, init=False, repr=False)

    def _parse_frontmatter_content(self, content):
        parsed = parse_pi_frontmatter(content)
        self._pi_key_lines = parsed.key_lines
        return parsed[:5]

    def key_line(self, key):
        self._ensure_parsed()
        return self._pi_key_lines.get(key)

    def line_map(self):
        self._ensure_parsed()
        return dict(self._pi_key_lines)


@dataclass(eq=False)
class PiExtensionNode(LintTarget):
    """Extension source is recorded, never imported or executed."""


@dataclass(eq=False)
class PiThemeBlock(JsonConfigBlock):
    """Theme data is structured configuration, never agent prose."""
