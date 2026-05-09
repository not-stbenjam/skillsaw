"""
Builtin linting rules for Claude Code plugins
"""

from .plugin_structure import (
    PluginJsonRequiredRule,
    PluginJsonValidRule,
    PluginNamingRule,
    PluginReadmeRule,
)

from .command_format import (
    CommandNamingRule,
    CommandFrontmatterRule,
    CommandSectionsRule,
    CommandNameFormatRule,
)

from .marketplace import (
    MarketplaceJsonValidRule,
    MarketplaceRegistrationRule,
)

from .skills import (
    SkillFrontmatterRule,
)

from .agents import (
    AgentFrontmatterRule,
)

from .hooks import (
    HooksJsonValidRule,
)

from .mcp import (
    McpValidJsonRule,
    McpProhibitedRule,
)

from .rules_dir import (
    RulesValidRule,
)

from .agentskills import (
    AgentSkillValidRule,
    AgentSkillNameRule,
    AgentSkillDescriptionRule,
    AgentSkillStructureRule,
    AgentSkillEvalsRequiredRule,
    AgentSkillEvalsRule,
)

from .openclaw import (
    OpenclawMetadataRule,
)

from .instruction_files import (
    InstructionFileValidRule,
    InstructionImportsValidRule,
    AgentsMdStructureRule,
)

from .copilot_instructions import (
    CopilotInstructionsValidRule,
    CopilotDotInstructionsValidRule,
)

from .context_budget import (
    ContextBudgetRule,
)

from .cursor import (
    CursorMdcValidRule,
    CursorRulesDeprecatedRule,
)

from .apm import (
    ApmManifestValidRule,
    ApmTargetValidRule,
    ApmTypeValidRule,
    ApmDependenciesValidRule,
    ApmCompilationValidRule,
    ApmMcpTransportRule,
    ApmLockfileConsistencyRule,
    ApmReadmePresentRule,
    ApmEntryPointRule,
    ApmNameConflictRule,
    ApmFieldTypesRule,
    ApmDeprecatedFieldsRule,
)

# All builtin rules
BUILTIN_RULES = [
    # Plugin structure
    PluginJsonRequiredRule,
    PluginJsonValidRule,
    PluginNamingRule,
    PluginReadmeRule,
    # Command format
    CommandNamingRule,
    CommandFrontmatterRule,
    CommandSectionsRule,
    CommandNameFormatRule,
    # Marketplace
    MarketplaceJsonValidRule,
    MarketplaceRegistrationRule,
    # Skills
    SkillFrontmatterRule,
    # Agents
    AgentFrontmatterRule,
    # Hooks
    HooksJsonValidRule,
    # MCP
    McpValidJsonRule,
    McpProhibitedRule,
    # Rules directory
    RulesValidRule,
    # Agentskills
    AgentSkillValidRule,
    AgentSkillNameRule,
    AgentSkillDescriptionRule,
    AgentSkillStructureRule,
    AgentSkillEvalsRequiredRule,
    AgentSkillEvalsRule,
    # Openclaw
    OpenclawMetadataRule,
    # Instruction files
    InstructionFileValidRule,
    InstructionImportsValidRule,
    # Copilot instructions
    CopilotInstructionsValidRule,
    CopilotDotInstructionsValidRule,
    AgentsMdStructureRule,
    # Context budget
    ContextBudgetRule,
    # Cursor rules
    CursorMdcValidRule,
    CursorRulesDeprecatedRule,
    # APM
    ApmManifestValidRule,
    ApmTargetValidRule,
    ApmTypeValidRule,
    ApmDependenciesValidRule,
    ApmCompilationValidRule,
    ApmMcpTransportRule,
    ApmLockfileConsistencyRule,
    ApmReadmePresentRule,
    ApmEntryPointRule,
    ApmNameConflictRule,
    ApmFieldTypesRule,
    ApmDeprecatedFieldsRule,
]


__all__ = [
    "BUILTIN_RULES",
    # Export individual rules too
    "PluginJsonRequiredRule",
    "PluginJsonValidRule",
    "PluginNamingRule",
    "PluginReadmeRule",
    "CommandNamingRule",
    "CommandFrontmatterRule",
    "CommandSectionsRule",
    "CommandNameFormatRule",
    "MarketplaceJsonValidRule",
    "MarketplaceRegistrationRule",
    "SkillFrontmatterRule",
    "AgentFrontmatterRule",
    "HooksJsonValidRule",
    "McpValidJsonRule",
    "McpProhibitedRule",
    "RulesValidRule",
    "AgentSkillValidRule",
    "AgentSkillNameRule",
    "AgentSkillDescriptionRule",
    "AgentSkillStructureRule",
    "AgentSkillEvalsRequiredRule",
    "AgentSkillEvalsRule",
    "OpenclawMetadataRule",
    "InstructionFileValidRule",
    "InstructionImportsValidRule",
    "CopilotInstructionsValidRule",
    "CopilotDotInstructionsValidRule",
    "AgentsMdStructureRule",
    "ContextBudgetRule",
    "CursorMdcValidRule",
    "CursorRulesDeprecatedRule",
    "ApmManifestValidRule",
    "ApmTargetValidRule",
    "ApmTypeValidRule",
    "ApmDependenciesValidRule",
    "ApmCompilationValidRule",
]
