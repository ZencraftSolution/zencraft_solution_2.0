"""Indicative estimate calculation. Every coefficient comes from EstimatorConfig so pricing can be tuned without a deploy."""
import math
from decimal import ROUND_HALF_UP, Decimal

from .models import EstimatorConfig, FeatureOption, ProjectType

VALID_PLATFORMS = {"web", "ios", "android", "windows", "macos", "linux"}


def _round_to(value, step):
    return (Decimal(value) / step).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * step


def suggest_team(hours, platforms, design_needs, urgency):
    """Returns (team list, full-time-equivalent headcount)."""
    mobile = any(p in platforms for p in ("ios", "android"))
    desktop = any(p in platforms for p in ("windows", "macos", "linux"))
    if hours < 450:
        team = [("Full-stack developer", 1.0), ("QA engineer", 0.5), ("Project manager", 0.25)]
    elif hours < 1400:
        team = [("Senior developer", 1.0), ("Developer", 1.0), ("QA engineer", 1.0), ("Project manager", 0.5)]
    elif hours < 3200:
        team = [("Tech lead", 1.0), ("Developers", 3.0), ("QA engineers", 1.5), ("DevOps engineer", 0.5), ("Project manager", 1.0)]
    else:
        team = [("Solution architect", 1.0), ("Developers", 5.0), ("QA engineers", 2.0), ("DevOps engineer", 1.0), ("Project manager", 1.0), ("Business analyst", 1.0)]
    if mobile:
        team.append(("Mobile developer", 1.0 if hours >= 450 else 0.5))
    if desktop:
        team.append(("Desktop developer", 1.0 if hours >= 1400 else 0.5))
    if design_needs in ("uiux", "branding"):
        team.append(("UI/UX designer", 1.0 if hours >= 1400 else 0.5))
    if urgency in ("fast", "critical") and hours >= 450:
        team.append(("Additional developer", 1.0))
    fte = sum(share for _, share in team)
    return [{"role": role, "allocation": share} for role, share in team], fte


def calculate(project_type_key, feature_keys, platforms, timeline, team_preference, design_needs, config=None):
    config = config or EstimatorConfig.load()
    try:
        project_type = ProjectType.objects.get(key=project_type_key, is_active=True)
    except ProjectType.DoesNotExist:
        raise ValueError("Unknown project type")

    platforms = [p for p in platforms if p in VALID_PLATFORMS] or ["web"]
    features = list(FeatureOption.objects.filter(key__in=feature_keys, project_types=project_type, is_active=True))

    hours = Decimal(project_type.base_hours) + sum((Decimal(f.hours) for f in features), Decimal("0"))

    coefficients = config.platform_coefficients or {}
    extra_share = sum(Decimal(str(coefficients.get(p, 0.3))) for p in platforms[1:])
    hours *= Decimal("1") + extra_share

    hours *= Decimal(str((config.design_multipliers or {}).get(design_needs, 1)))
    hours *= Decimal(str((config.urgency_multipliers or {}).get(timeline, 1)))
    hours *= Decimal(str((config.team_multipliers or {}).get(team_preference, 1)))

    cost = hours * config.blended_hourly_rate_npr * (Decimal("1") + config.contingency_pct / Decimal("100"))
    cost = max(cost, config.minimum_project_npr)
    low = _round_to(cost * config.range_low_factor, Decimal("10000"))
    high = _round_to(cost * config.range_high_factor, Decimal("10000"))

    team, fte = suggest_team(float(hours), platforms, design_needs, timeline)
    weekly_capacity = max(1.0, fte * config.team_hours_per_week)
    weeks = float(hours) / weekly_capacity
    weeks_low = max(2, math.floor(weeks * 0.9))
    weeks_high = max(weeks_low + 1, math.ceil(weeks * 1.3))

    return {
        "project_type": project_type,
        "features": [f.key for f in features],
        "platforms": platforms,
        "hours": int(hours),
        "low": low,
        "high": high,
        "weeks_low": weeks_low,
        "weeks_high": weeks_high,
        "team": team,
        "disclaimer": config.disclaimer,
    }
