"""Backward-compatibility shim — rules moved to content/ package."""

from .content import (  # noqa: F401
    ContentWeakLanguageRule,
    ContentTautologicalRule,
    ContentRedundantWithToolingRule,
    ContentInstructionBudgetRule,
    ContentNegativeOnlyRule,
    ContentSectionLengthRule,
    ContentContradictionRule,
    ContentHookCandidateRule,
    ContentCognitiveChunksRule,
    ContentEmbeddedSecretsRule,
    ContentBannedReferencesRule,
    ContentInconsistentTerminologyRule,
    ContentInstructionDriftRule,
    ContentBrokenInternalReferenceRule,
    ContentUnlinkedInternalReferenceRule,
    ContentPlaceholderTextRule,
)
