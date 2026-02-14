"""
Daily Insight Generator

将每日抓取的单条摘要进行"二次炼金"，生成具有全局洞察力的每日技术简报。
"""

from .daily_insight_generator import (
    DailyInsightGenerator,
    DailyInsight,
    MacroTrend,
    HighImpactPick,
    HiddenGem,
    CommunityPulse,
    Statistics,
    create_daily_insight_generator,
)

__all__ = [
    "DailyInsightGenerator",
    "DailyInsight",
    "MacroTrend",
    "HighImpactPick",
    "HiddenGem",
    "CommunityPulse",
    "Statistics",
    "create_daily_insight_generator",
]


