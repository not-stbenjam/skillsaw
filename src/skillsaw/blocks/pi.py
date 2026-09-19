"""Pi package metadata, project settings, and native resources."""

from dataclasses import dataclass
from typing import ClassVar

from .frontmatter import FrontmatteredBlock
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
class PiSkillBlock(FrontmatteredBlock):
    """Pi skill dialect, including flat Markdown and optional names.

    Deliberately not SkillBlock: Pi allows a missing name and does not
    require the name to match the directory. Portable authoring checks must
    not rewrite valid Pi metadata into another host's convention.
    """

    category: str = "skill"


@dataclass(eq=False)
class PiExtensionNode(LintTarget):
    """Extension source is recorded, never imported or executed."""


@dataclass(eq=False)
class PiThemeBlock(JsonConfigBlock):
    """Theme data is structured configuration, never agent prose."""
