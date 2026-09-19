"""A retired third-party rule used to exercise the deprecation API."""

from skillsaw.rule import Rule, Severity


class RetiredRule(Rule):
    deprecated = "0.18.0"
    deprecated_reason = "The replacement validates the same fields."
    replaced_by = "agentskill-valid"

    @property
    def rule_id(self):
        return "example-retired"

    @property
    def description(self):
        return "Validate legacy skill metadata"

    def default_severity(self):
        return Severity.WARNING

    def check(self, context):
        return []
