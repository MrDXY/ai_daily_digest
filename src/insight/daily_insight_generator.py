"""
Daily Insight Generator

将每日抓取的单条摘要进行"二次炼金"，生成具有全局洞察力的每日技术简报。

核心功能：
- 读取当天所有 AI 摘要
- 聚合分析，识别模式与关联
- 筛选高价值内容
- 生成毒舌风格的每日简报
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

import aiofiles

from ..core.config import AppConfig, get_output_dir, get_report_date_dir
from ..core.cache import AISummaryCache
from ..processor.ai_provider import AIProviderClient, AIProviderError

logger = logging.getLogger(__name__)


# ============================================
# Editor-in-Chief System Prompt
# ============================================

EDITOR_IN_CHIEF_SYSTEM_PROMPT = """你是一位毒舌且洞察力极强的科技主编。你的目标是从一大堆杂乱的技术新闻中，挖掘出背后的"底层逻辑"。

原则：
- 拒绝翻译腔，拒绝客套话
- 如果某个趋势是垃圾，请直接指出
- 如果某个小众项目有潜力颠覆行业，请大肆赞美
- 寻找不同项目之间的"协同效应"或"矛盾点"

你的文风应该是：
- 犀利、直接、有态度
- 像一个老江湖在茶余饭后吐槽行业八卦
- 不怕得罪人，但言之有物
- 用数据和逻辑说话，而不是空洞的赞美或批评"""


INSIGHT_GENERATION_PROMPT = """## 任务
你需要分析以下 {count} 条今日技术新闻摘要，生成一份具有全局洞察力的每日技术简报。

## 输入数据
以下是今天的所有技术新闻摘要（JSON 格式）：

```json
{summaries_json}
```

## 分析步骤
请按以下步骤进行分析：

1. **聚合与聚类**：识别这些条目之间的关联（例如：是否有多个项目都在讨论同一技术趋势？）

2. **模式识别**：
   - 今天有哪些技术热点？
   - 不同来源（HN/GitHub/Lobsters）之间是否有共同关注的话题？
   - 有哪些意想不到的关联？

3. **内容筛选**：
   - 剔除平庸的、广告性质的或重复的项目
   - 只保留前 10-15% 的高价值内容
   - 特别关注那些"看起来不起眼但可能很重要"的项目

4. **生成报告**：按照下方指定的格式生成最终内容

## 输出格式
请严格按照以下 JSON 格式输出：

```json
{{
  "macro_trend": {{
    "title": "一句话标题（不超过20字）",
    "content": "150字左右的深度评论，总结今天的技术情绪。是激进、疲软还是在憋大招？要有观点，要犀利。"
  }},
  "high_impact_picks": [
    {{
      "title": "项目名",
      "url": "项目链接",
      "source": "来源（如 HN/GitHub）",
      "one_liner": "一句话总结（不超过50字）",
      "insight": "为什么这玩意儿值得看？它动了谁的蛋糕？（50-100字）",
      "score": 原始评分
    }}
  ],
  "hidden_gems": [
    {{
      "title": "项目名",
      "url": "项目链接",
      "source": "来源",
      "description": "一句话描述（不超过50字）",
      "comment": "别被 Star 数骗了，这个项目真正解决的问题是...（50-100字）"
    }}
  ],
  "community_pulse": {{
    "topic": "争议话题标题",
    "summary": "总结今天社区争议最大的话题（100-150字）",
    "verdict": "你作为主编的最终裁决（50-100字，要有态度）"
  }},
  "statistics": {{
    "total_analyzed": 分析的总条目数,
    "sources_breakdown": {{"HN": 数量, "GitHub": 数量, ...}},
    "top_tech_stacks": ["最常出现的技术1", "技术2", "技术3"],
    "filtered_out_count": 被筛掉的低价值条目数
  }}
}}
```

## 注意事项
- high_impact_picks 数量控制在 3-5 个
- hidden_gems 数量控制在 2-3 个
- 如果今天没有明显的社区争议话题，community_pulse 可以聊聊你观察到的有趣现象
- 所有文字必须是中文
- 保持毒舌但专业的风格，言之有物"""


# ============================================
# Data Models
# ============================================

@dataclass
class HighImpactPick:
    """高影响力项目"""
    title: str
    url: str
    source: str
    one_liner: str
    insight: str
    score: float = 0.0


@dataclass
class HiddenGem:
    """遗珠项目"""
    title: str
    url: str
    source: str
    description: str
    comment: str


@dataclass
class CommunityPulse:
    """社区动态"""
    topic: str
    summary: str
    verdict: str


@dataclass
class MacroTrend:
    """宏观趋势"""
    title: str
    content: str


@dataclass
class Statistics:
    """统计数据"""
    total_analyzed: int = 0
    sources_breakdown: dict[str, int] = field(default_factory=dict)
    top_tech_stacks: list[str] = field(default_factory=list)
    filtered_out_count: int = 0


@dataclass
class DailyInsight:
    """每日洞察报告"""
    date: str
    macro_trend: MacroTrend
    high_impact_picks: list[HighImpactPick]
    hidden_gems: list[HiddenGem]
    community_pulse: CommunityPulse
    statistics: Statistics
    generated_at: datetime = field(default_factory=datetime.now)

    def to_markdown(self) -> str:
        """转换为 Markdown 格式"""
        lines = [
            f"# 🚀 AI Daily Insight: {self.date}",
            "",
            f"## 🌪️ 宏观风暴 (The Macro Trend)",
            f"> **{self.macro_trend.title}**",
            ">",
            f"> {self.macro_trend.content}",
            "",
            "## ⚡ 核心突破 (High-Impact Picks)",
            "",
        ]

        for pick in self.high_impact_picks:
            score_display = f"评分: {pick.score}" if pick.score else ""
            lines.extend([
                f"- **[{pick.title}]({pick.url})** `{pick.source}` {score_display}",
                f"  - {pick.one_liner}",
                f"  - **犀利洞察**: {pick.insight}",
                "",
            ])

        lines.extend([
            "## 💎 遗珠/冷思考 (Hidden Gems & Skepticism)",
            "",
        ])

        for gem in self.hidden_gems:
            lines.extend([
                f"- **[{gem.title}]({gem.url})** `{gem.source}`",
                f"  - {gem.description}",
                f"  - **点评**: {gem.comment}",
                "",
            ])

        lines.extend([
            "## 🗣️ 社区火药味 (Community Pulse)",
            "",
            f"### {self.community_pulse.topic}",
            "",
            self.community_pulse.summary,
            "",
            f"**主编裁决**: {self.community_pulse.verdict}",
            "",
            "---",
            "",
            "## 📊 数据统计",
            "",
            f"- 分析条目: {self.statistics.total_analyzed}",
            f"- 筛除条目: {self.statistics.filtered_out_count}",
            f"- 来源分布: {', '.join(f'{k}: {v}' for k, v in self.statistics.sources_breakdown.items())}",
            f"- 热门技术: {', '.join(self.statistics.top_tech_stacks)}",
            "",
            "---",
            "",
            f"> 🤖 由 AI Daily Insight 于 {self.generated_at.strftime('%Y-%m-%d %H:%M:%S')} 生成",
            "> ",
            "> 本报告使用 LLM 进行二次分析，观点仅供参考",
        ])

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "date": self.date,
            "macro_trend": {
                "title": self.macro_trend.title,
                "content": self.macro_trend.content,
            },
            "high_impact_picks": [
                {
                    "title": p.title,
                    "url": p.url,
                    "source": p.source,
                    "one_liner": p.one_liner,
                    "insight": p.insight,
                    "score": p.score,
                }
                for p in self.high_impact_picks
            ],
            "hidden_gems": [
                {
                    "title": g.title,
                    "url": g.url,
                    "source": g.source,
                    "description": g.description,
                    "comment": g.comment,
                }
                for g in self.hidden_gems
            ],
            "community_pulse": {
                "topic": self.community_pulse.topic,
                "summary": self.community_pulse.summary,
                "verdict": self.community_pulse.verdict,
            },
            "statistics": {
                "total_analyzed": self.statistics.total_analyzed,
                "sources_breakdown": self.statistics.sources_breakdown,
                "top_tech_stacks": self.statistics.top_tech_stacks,
                "filtered_out_count": self.statistics.filtered_out_count,
            },
            "generated_at": self.generated_at.isoformat(),
        }


# ============================================
# Daily Insight Generator
# ============================================

class DailyInsightGenerator:
    """
    每日洞察生成器

    读取当天的 AI 摘要，通过 LLM 进行二次分析，
    生成具有全局洞察力的每日技术简报。
    """

    def __init__(self, config: AppConfig):
        """
        初始化生成器

        Args:
            config: 应用配置
        """
        self.config = config
        self._provider: Optional[AIProviderClient] = None

        # 初始化摘要缓存
        cache_dir = get_output_dir(config) / "cache" / "ai_summary"
        self._summary_cache = AISummaryCache(cache_dir, enabled=True)

    def _get_provider(self) -> AIProviderClient:
        """获取 AI Provider"""
        if self._provider is None:
            self._provider = AIProviderClient(self.config)
        return self._provider

    async def load_summaries(self, target_date: Optional[date] = None) -> list[dict[str, Any]]:
        """
        加载指定日期的所有摘要

        Args:
            target_date: 目标日期，默认为今天

        Returns:
            摘要列表
        """
        if target_date is None:
            target_date = date.today()

        cache_dir = self._summary_cache.cache_dir / target_date.isoformat()

        if not cache_dir.exists():
            logger.warning(f"No summary cache found for {target_date}")
            return []

        summaries = []
        for cache_file in cache_dir.glob("*.json"):
            try:
                async with aiofiles.open(cache_file, "r", encoding="utf-8") as f:
                    content = await f.read()
                    data = json.loads(content)

                    summary_data = data.get("summary", {})
                    source_item = summary_data.get("_source_item", {})

                    # 构建统一的摘要条目
                    entry = {
                        "title": source_item.get("title", ""),
                        "url": data.get("url", source_item.get("url", "")),
                        "source": source_item.get("source", "Unknown"),
                        "content_summary": summary_data.get("summary", ""),
                        "core_value": summary_data.get("core_value", ""),
                        "tech_stack": summary_data.get("tech_stack", []),
                        "recommendation": summary_data.get("recommendation", ""),
                        "score": summary_data.get("score", 0),
                        "stars": source_item.get("stars"),
                    }

                    # 过滤掉无效条目
                    if entry["title"] and entry["content_summary"]:
                        summaries.append(entry)

            except Exception as e:
                logger.warning(f"Failed to load summary from {cache_file}: {e}")
                continue

        logger.info(f"Loaded {len(summaries)} summaries for {target_date}")
        return summaries

    async def generate_insight(
        self,
        summaries: list[dict[str, Any]],
        target_date: Optional[date] = None,
    ) -> DailyInsight:
        """
        生成每日洞察报告

        Args:
            summaries: 摘要列表
            target_date: 目标日期

        Returns:
            DailyInsight 对象
        """
        if target_date is None:
            target_date = date.today()

        date_str = target_date.isoformat()

        if not summaries:
            logger.warning("No summaries to analyze")
            return self._create_empty_insight(date_str)

        # 准备输入数据
        summaries_json = json.dumps(summaries, ensure_ascii=False, indent=2)

        # 构建 prompt
        prompt = INSIGHT_GENERATION_PROMPT.format(
            count=len(summaries),
            summaries_json=summaries_json,
        )

        provider = self._get_provider()

        try:
            # 调用 LLM 生成洞察
            response = await provider.generate_text(
                prompt=prompt,
                system=EDITOR_IN_CHIEF_SYSTEM_PROMPT,
                max_tokens=4096,
                temperature=0.7,  # 稍高的温度以获得更有创意的输出
            )

            # 解析响应
            insight = self._parse_insight_response(response, date_str)
            return insight

        except AIProviderError as e:
            logger.error(f"Failed to generate insight: {e}")
            raise

    def _parse_insight_response(self, response: str, date_str: str) -> DailyInsight:
        """解析 LLM 响应"""
        try:
            # 移除可能的 markdown 代码块标记
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]

            data = json.loads(response.strip())

            # 解析各部分
            macro_data = data.get("macro_trend", {})
            macro_trend = MacroTrend(
                title=macro_data.get("title", "今日无特别趋势"),
                content=macro_data.get("content", ""),
            )

            high_impact_picks = [
                HighImpactPick(
                    title=p.get("title", ""),
                    url=p.get("url", ""),
                    source=p.get("source", ""),
                    one_liner=p.get("one_liner", ""),
                    insight=p.get("insight", ""),
                    score=p.get("score", 0),
                )
                for p in data.get("high_impact_picks", [])
            ]

            hidden_gems = [
                HiddenGem(
                    title=g.get("title", ""),
                    url=g.get("url", ""),
                    source=g.get("source", ""),
                    description=g.get("description", ""),
                    comment=g.get("comment", ""),
                )
                for g in data.get("hidden_gems", [])
            ]

            pulse_data = data.get("community_pulse", {})
            community_pulse = CommunityPulse(
                topic=pulse_data.get("topic", "今日社区无明显争议"),
                summary=pulse_data.get("summary", ""),
                verdict=pulse_data.get("verdict", ""),
            )

            stats_data = data.get("statistics", {})
            statistics = Statistics(
                total_analyzed=stats_data.get("total_analyzed", 0),
                sources_breakdown=stats_data.get("sources_breakdown", {}),
                top_tech_stacks=stats_data.get("top_tech_stacks", []),
                filtered_out_count=stats_data.get("filtered_out_count", 0),
            )

            return DailyInsight(
                date=date_str,
                macro_trend=macro_trend,
                high_impact_picks=high_impact_picks,
                hidden_gems=hidden_gems,
                community_pulse=community_pulse,
                statistics=statistics,
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse insight response as JSON: {e}")
            logger.debug(f"Response: {response[:500]}...")
            return self._create_empty_insight(date_str)

    def _create_empty_insight(self, date_str: str) -> DailyInsight:
        """创建空的洞察报告"""
        return DailyInsight(
            date=date_str,
            macro_trend=MacroTrend(
                title="数据不足",
                content="今日没有足够的数据进行分析。",
            ),
            high_impact_picks=[],
            hidden_gems=[],
            community_pulse=CommunityPulse(
                topic="无",
                summary="没有发现明显的社区讨论热点。",
                verdict="建议关注更多信息源。",
            ),
            statistics=Statistics(),
        )

    async def generate_and_save(
        self,
        target_date: Optional[date] = None,
        output_format: str = "both",
    ) -> tuple[DailyInsight, Path]:
        """
        生成并保存每日洞察报告

        Args:
            target_date: 目标日期
            output_format: 输出格式，"markdown" / "json" / "both"

        Returns:
            (DailyInsight, 输出文件路径)
        """
        if target_date is None:
            target_date = date.today()

        date_str = target_date.isoformat()

        # 加载摘要
        summaries = await self.load_summaries(target_date)

        # 生成洞察
        insight = await self.generate_insight(summaries, target_date)

        # 保存文件
        output_dir = get_report_date_dir(self.config, date_str)
        output_dir.mkdir(parents=True, exist_ok=True)

        saved_path = None

        # 保存 Markdown
        if output_format in ("markdown", "both"):
            md_path = output_dir / f"daily_insight_{date_str}.md"
            async with aiofiles.open(md_path, "w", encoding="utf-8") as f:
                await f.write(insight.to_markdown())
            logger.info(f"Saved Markdown insight to {md_path}")
            saved_path = md_path

        # 保存 JSON
        if output_format in ("json", "both"):
            json_path = output_dir / f"daily_insight_{date_str}.json"
            async with aiofiles.open(json_path, "w", encoding="utf-8") as f:
                await f.write(json.dumps(insight.to_dict(), ensure_ascii=False, indent=2))
            logger.info(f"Saved JSON insight to {json_path}")
            if saved_path is None:
                saved_path = json_path

        return insight, saved_path

    async def close(self) -> None:
        """关闭资源"""
        if self._provider:
            await self._provider.close()
            self._provider = None


# ============================================
# Factory Function
# ============================================

def create_daily_insight_generator(config: AppConfig) -> DailyInsightGenerator:
    """
    工厂函数：创建每日洞察生成器

    Args:
        config: 应用配置

    Returns:
        DailyInsightGenerator 实例
    """
    return DailyInsightGenerator(config)

