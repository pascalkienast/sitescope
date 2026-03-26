"""
Risk-level helpers shared across point and area analysis flows.
"""

from collections.abc import Iterable

from models import RiskLevel

RISK_PRIORITY = {
    RiskLevel.HIGH: 4,
    RiskLevel.MEDIUM: 3,
    RiskLevel.LOW: 2,
    RiskLevel.NONE: 1,
    RiskLevel.UNKNOWN: 0,
}


def highest_risk(levels: Iterable[RiskLevel]) -> RiskLevel:
    """Return the highest-priority risk level from an iterable."""
    resolved = list(levels)
    if not resolved:
        return RiskLevel.NONE
    return max(resolved, key=lambda level: RISK_PRIORITY.get(level, -1))
