"""Action resolution module.

Provides skill check and action resolution systems for Dolmenwood.
"""

from src.resolution.skill_resolver import (
    SkillCheckResult,
    SkillDefinition,
    SkillOutcome,
    SkillResolver,
    get_skill_resolver,
    resolve_skill_check,
)

__all__ = [
    "SkillCheckResult",
    "SkillDefinition",
    "SkillOutcome",
    "SkillResolver",
    "get_skill_resolver",
    "resolve_skill_check",
]
