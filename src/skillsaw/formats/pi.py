"""Pi's authored resource contract (upstream 36b60d2, 2026-09-18).

See https://pi.dev/docs/latest/packages and packages/coding-agent/src/core/{pi-manifest,
package-manager,skills}.ts in https://github.com/earendil-works/pi.
"""

RESOURCE_FIELDS = ("extensions", "skills", "prompts", "themes")
TOOL_DIR_NAME = ".pi"
REMOTE_PREFIXES = ("npm:", "git:", "https://", "http://", "ssh://", "git://")


def string_list(value: object) -> bool:
    """Pi accepts an entire resource field only when every item is a string."""
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def settings_resources(settings: dict) -> dict:
    """Apply Pi's legacy skills migration without mutating cached settings.

    settings-manager.ts migrates only the top-level settings object; package
    manifests and package selectors retain the array-only resource contract.
    """
    skills = settings.get("skills")
    if not isinstance(skills, dict):
        return settings
    effective = settings.copy()
    directories = skills.get("customDirectories")
    if isinstance(directories, list) and directories:
        effective["skills"] = directories
    else:
        effective.pop("skills")
    return effective
