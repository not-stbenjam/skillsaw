"""Evidence retained for a verified generator copy in the lint tree."""

from dataclasses import dataclass
from pathlib import Path
from typing import Tuple


@dataclass(frozen=True)
class GeneratedCopy:
    generator: str
    sources: Tuple[Path, ...]


# Output size, references, policy and security have independent meaning after
# generation. Only these editorial findings can be duplicates of the source.
# A new rule stays on by default here, even if its name starts with content-.
EDITORIAL_COPY_RULES = frozenset(
    {
        "content-cognitive-chunks",
        "content-description-routing",
        "content-emphasis-density",
        "content-hook-candidate",
        "content-inconsistent-terminology",
        "content-instruction-drift",
        "content-negative-only",
        "content-progressive-disclosure",
        "content-repeated-directive",
        "content-tautological",
        "content-weak-language",
    }
)
