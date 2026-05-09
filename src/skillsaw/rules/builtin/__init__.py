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

from .agents_md import (
    AgentsMdSizeLimitRule,
    AgentsMdOverrideSemanticsRule,
    AgentsMdHierarchyConsistencyRule,
    AgentsMdDeadFileRefsRule,
    AgentsMdDeadCommandRefsRule,
    AgentsMdWeakLanguageRule,
    AgentsMdNegativeOnlyRule,
    AgentsMdSectionLengthRule,
    AgentsMdStructureDeepRule,
    AgentsMdTautologicalRule,
    AgentsMdCriticalPositionRule,
    AgentsMdHookCandidateRule,
)

from .copilot_instructions import (
    CopilotInstructionsValidRule,
    CopilotDotInstructionsValidRule,
)

from .gemini import (
    GeminiImportValidRule,
    GeminiImportCircularRule,
    GeminiImportDepthRule,
    GeminiScopeFalsePositiveRule,
    GeminiHierarchyConsistencyRule,
    GeminiSizeLimitRule,
    GeminiDeadFileRefsRule,
    GeminiWeakLanguageRule,
    GeminiTautologicalRule,
    GeminiCriticalPositionRule,
)

from .context_budget import (
    ContextBudgetRule,
)

from .cursor import (
    CursorMdcValidRule,
    CursorRulesDeprecatedRule,
    CursorMdcFrontmatterRule,
    CursorActivationTypeRule,
    CursorCrlfDetectionRule,
    CursorGlobValidRule,
    CursorEmptyBodyRule,
    CursorDescriptionQualityRule,
    CursorGlobOverlapRule,
    CursorRuleSizeRule,
    CursorFrontmatterTypesRule,
    CursorDuplicateRulesRule,
    CursorAlwaysApplyOveruseRule,
)

from .kiro import (
    KiroSteeringValidRule,
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

from .content_rules import (
    ContentWeakLanguageRule,
    ContentDeadReferencesRule,
    ContentTautologicalRule,
    ContentCriticalPositionRule,
    ContentRedundantWithToolingRule,
    ContentInstructionBudgetRule,
    ContentReadmeOverlapRule,
    ContentNegativeOnlyRule,
    ContentSectionLengthRule,
    ContentContradictionRule,
    ContentHookCandidateRule,
    ContentActionabilityScoreRule,
    ContentCognitiveChunksRule,
    ContentEmbeddedSecretsRule,
    ContentCrossFileConsistencyRule,
)

from .claude_deep import (
    ClaudeMdQualityRule,
    ClaudeMdHookMigrationRule,
    ClaudeSkillQualityRule,
    ClaudeMcpSecurityRule,
    ClaudePluginSizeRule,
    ClaudeRulesOverlapRule,
    ClaudeAgentDelegationRule,
    ClaudeContextBudgetRule,
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
    # AGENTS.md rules
    AgentsMdStructureRule,
    AgentsMdSizeLimitRule,
    AgentsMdOverrideSemanticsRule,
    AgentsMdHierarchyConsistencyRule,
    AgentsMdDeadFileRefsRule,
    AgentsMdDeadCommandRefsRule,
    AgentsMdWeakLanguageRule,
    AgentsMdNegativeOnlyRule,
    AgentsMdSectionLengthRule,
    AgentsMdStructureDeepRule,
    AgentsMdTautologicalRule,
    AgentsMdCriticalPositionRule,
    AgentsMdHookCandidateRule,
    # Context budget
    ContextBudgetRule,
    # Cursor rules
    CursorMdcValidRule,
    CursorRulesDeprecatedRule,
    CursorMdcFrontmatterRule,
    CursorActivationTypeRule,
    CursorCrlfDetectionRule,
    CursorGlobValidRule,
    CursorEmptyBodyRule,
    CursorDescriptionQualityRule,
    CursorGlobOverlapRule,
    CursorRuleSizeRule,
    CursorFrontmatterTypesRule,
    CursorDuplicateRulesRule,
    CursorAlwaysApplyOveruseRule,
    # Kiro steering
    KiroSteeringValidRule,
    # Gemini
    GeminiImportValidRule,
    GeminiImportCircularRule,
    GeminiImportDepthRule,
    GeminiScopeFalsePositiveRule,
    GeminiHierarchyConsistencyRule,
    GeminiSizeLimitRule,
    GeminiDeadFileRefsRule,
    GeminiWeakLanguageRule,
    GeminiTautologicalRule,
    GeminiCriticalPositionRule,
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
    # Content intelligence
    ContentWeakLanguageRule,
    ContentDeadReferencesRule,
    ContentTautologicalRule,
    ContentCriticalPositionRule,
    ContentRedundantWithToolingRule,
    ContentInstructionBudgetRule,
    ContentReadmeOverlapRule,
    ContentNegativeOnlyRule,
    ContentSectionLengthRule,
    ContentContradictionRule,
    ContentHookCandidateRule,
    ContentActionabilityScoreRule,
    ContentCognitiveChunksRule,
    ContentEmbeddedSecretsRule,
    ContentCrossFileConsistencyRule,
    # Deep Claude Code rules
    ClaudeMdQualityRule,
    ClaudeMdHookMigrationRule,
    ClaudeSkillQualityRule,
    ClaudeMcpSecurityRule,
    ClaudePluginSizeRule,
    ClaudeRulesOverlapRule,
    ClaudeAgentDelegationRule,
    ClaudeContextBudgetRule,
]


__all__ = [
    "BUILTIN_RULES",
    # Plugin structure
    "PluginJsonRequiredRule",
    "PluginJsonValidRule",
    "PluginNamingRule",
    "PluginReadmeRule",
    # Command format
    "CommandNamingRule",
    "CommandFrontmatterRule",
    "CommandSectionsRule",
    "CommandNameFormatRule",
    # Marketplace
    "MarketplaceJsonValidRule",
    "MarketplaceRegistrationRule",
    # Skills, Agents, Hooks
    "SkillFrontmatterRule",
    "AgentFrontmatterRule",
    "HooksJsonValidRule",
    # MCP
    "McpValidJsonRule",
    "McpProhibitedRule",
    # Rules directory
    "RulesValidRule",
    # Agentskills
    "AgentSkillValidRule",
    "AgentSkillNameRule",
    "AgentSkillDescriptionRule",
    "AgentSkillStructureRule",
    "AgentSkillEvalsRequiredRule",
    "AgentSkillEvalsRule",
    # Openclaw
    "OpenclawMetadataRule",
    # Instruction files
    "InstructionFileValidRule",
    "InstructionImportsValidRule",
    # Copilot instructions
    "CopilotInstructionsValidRule",
    "CopilotDotInstructionsValidRule",
    # AGENTS.md
    "AgentsMdStructureRule",
    "AgentsMdSizeLimitRule",
    "AgentsMdOverrideSemanticsRule",
    "AgentsMdHierarchyConsistencyRule",
    "AgentsMdDeadFileRefsRule",
    "AgentsMdDeadCommandRefsRule",
    "AgentsMdWeakLanguageRule",
    "AgentsMdNegativeOnlyRule",
    "AgentsMdSectionLengthRule",
    "AgentsMdStructureDeepRule",
    "AgentsMdTautologicalRule",
    "AgentsMdCriticalPositionRule",
    "AgentsMdHookCandidateRule",
    # Context budget
    "ContextBudgetRule",
    # Cursor
    "CursorMdcValidRule",
    "CursorRulesDeprecatedRule",
    "CursorMdcFrontmatterRule",
    "CursorActivationTypeRule",
    "CursorCrlfDetectionRule",
    "CursorGlobValidRule",
    "CursorEmptyBodyRule",
    "CursorDescriptionQualityRule",
    "CursorGlobOverlapRule",
    "CursorRuleSizeRule",
    "CursorFrontmatterTypesRule",
    "CursorDuplicateRulesRule",
    "CursorAlwaysApplyOveruseRule",
    # Kiro
    "KiroSteeringValidRule",
    # Gemini
    "GeminiImportValidRule",
    "GeminiImportCircularRule",
    "GeminiImportDepthRule",
    "GeminiScopeFalsePositiveRule",
    "GeminiHierarchyConsistencyRule",
    "GeminiSizeLimitRule",
    "GeminiDeadFileRefsRule",
    "GeminiWeakLanguageRule",
    "GeminiTautologicalRule",
    "GeminiCriticalPositionRule",
    # APM
    "ApmManifestValidRule",
    "ApmTargetValidRule",
    "ApmTypeValidRule",
    "ApmDependenciesValidRule",
    "ApmCompilationValidRule",
    "ApmMcpTransportRule",
    "ApmLockfileConsistencyRule",
    "ApmReadmePresentRule",
    "ApmEntryPointRule",
    "ApmNameConflictRule",
    "ApmFieldTypesRule",
    "ApmDeprecatedFieldsRule",
    # Content intelligence
    "ContentWeakLanguageRule",
    "ContentDeadReferencesRule",
    "ContentTautologicalRule",
    "ContentCriticalPositionRule",
    "ContentRedundantWithToolingRule",
    "ContentInstructionBudgetRule",
    "ContentReadmeOverlapRule",
    "ContentNegativeOnlyRule",
    "ContentSectionLengthRule",
    "ContentContradictionRule",
    "ContentHookCandidateRule",
    "ContentActionabilityScoreRule",
    "ContentCognitiveChunksRule",
    "ContentEmbeddedSecretsRule",
    "ContentCrossFileConsistencyRule",
    # Claude Code deep rules
    "ClaudeMdQualityRule",
    "ClaudeMdHookMigrationRule",
    "ClaudeSkillQualityRule",
    "ClaudeMcpSecurityRule",
    "ClaudePluginSizeRule",
    "ClaudeRulesOverlapRule",
    "ClaudeAgentDelegationRule",
    "ClaudeContextBudgetRule",
]
