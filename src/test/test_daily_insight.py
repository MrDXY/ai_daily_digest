"""
Daily Insight Generator 测试
"""

import asyncio
import json
import pytest
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from src.insight.daily_insight_generator import (
    DailyInsightGenerator,
    DailyInsight,
    MacroTrend,
    HighImpactPick,
    HiddenGem,
    CommunityPulse,
    Statistics,
    create_daily_insight_generator,
)


class TestDailyInsight:
    """DailyInsight 数据模型测试"""

    def test_to_markdown(self):
        """测试 Markdown 输出"""
        insight = DailyInsight(
            date="2026-02-14",
            macro_trend=MacroTrend(
                title="AI 狂欢持续",
                content="今天的技术圈依然被 AI 相关项目霸屏，但已经开始出现审美疲劳的迹象。",
            ),
            high_impact_picks=[
                HighImpactPick(
                    title="awesome-project",
                    url="https://github.com/example/awesome-project",
                    source="GitHub",
                    one_liner="一个改变游戏规则的项目",
                    insight="这个项目直接动了 XXX 的蛋糕",
                    score=92.0,
                )
            ],
            hidden_gems=[
                HiddenGem(
                    title="hidden-gem",
                    url="https://github.com/example/hidden-gem",
                    source="Lobsters",
                    description="一个被低估的工具",
                    comment="别被 Star 数骗了，这才是真正解决问题的项目",
                )
            ],
            community_pulse=CommunityPulse(
                topic="Rust vs Go 又吵起来了",
                summary="HN 上关于 Rust 和 Go 的争论再次爆发",
                verdict="都是好语言，选适合你的就好",
            ),
            statistics=Statistics(
                total_analyzed=50,
                sources_breakdown={"GitHub": 30, "HN": 15, "Lobsters": 5},
                top_tech_stacks=["Rust", "Python", "TypeScript"],
                filtered_out_count=35,
            ),
        )

        md = insight.to_markdown()

        assert "# 🚀 AI Daily Insight: 2026-02-14" in md
        assert "## 🌪️ 宏观风暴" in md
        assert "AI 狂欢持续" in md
        assert "## ⚡ 核心突破" in md
        assert "awesome-project" in md
        assert "## 💎 遗珠/冷思考" in md
        assert "hidden-gem" in md
        assert "## 🗣️ 社区火药味" in md
        assert "Rust vs Go" in md

    def test_to_dict(self):
        """测试字典输出"""
        insight = DailyInsight(
            date="2026-02-14",
            macro_trend=MacroTrend(title="测试", content="内容"),
            high_impact_picks=[],
            hidden_gems=[],
            community_pulse=CommunityPulse(topic="无", summary="无", verdict="无"),
            statistics=Statistics(),
        )

        data = insight.to_dict()

        assert data["date"] == "2026-02-14"
        assert "macro_trend" in data
        assert "high_impact_picks" in data
        assert "hidden_gems" in data
        assert "community_pulse" in data
        assert "statistics" in data


class TestDailyInsightGenerator:
    """DailyInsightGenerator 测试"""

    @pytest.fixture
    def mock_config(self):
        """创建模拟配置"""
        config = MagicMock()
        config.ai.default_provider = "openai"
        config.ai.openai.api_key = "test-key"
        config.ai.openai.model = "gpt-4o"
        config.ai.openai.max_tokens = 2048
        config.ai.openai.temperature = 0.3
        config.app = {"output_dir": "./output"}
        return config

    @pytest.fixture
    def sample_summaries(self):
        """示例摘要数据"""
        return [
            {
                "title": "Project A",
                "url": "https://example.com/a",
                "source": "GitHub",
                "content_summary": "一个很棒的项目",
                "core_value": "解决了重要问题",
                "tech_stack": ["Python", "FastAPI"],
                "score": 85,
                "stars": 1000,
            },
            {
                "title": "Article B",
                "url": "https://example.com/b",
                "source": "Hacker News",
                "content_summary": "一篇深度文章",
                "core_value": "提供了新视角",
                "tech_stack": ["Rust"],
                "score": 78,
            },
        ]

    @pytest.fixture
    def sample_llm_response(self):
        """模拟 LLM 响应"""
        return json.dumps({
            "macro_trend": {
                "title": "AI 依然火爆",
                "content": "今天的技术圈被各种 AI 项目占据。"
            },
            "high_impact_picks": [
                {
                    "title": "Project A",
                    "url": "https://example.com/a",
                    "source": "GitHub",
                    "one_liner": "值得关注的项目",
                    "insight": "有潜力改变行业格局",
                    "score": 85
                }
            ],
            "hidden_gems": [
                {
                    "title": "Article B",
                    "url": "https://example.com/b",
                    "source": "Hacker News",
                    "description": "被低估的好文章",
                    "comment": "深度分析很到位"
                }
            ],
            "community_pulse": {
                "topic": "技术选型之争",
                "summary": "社区在讨论技术选型问题",
                "verdict": "没有银弹，选适合的"
            },
            "statistics": {
                "total_analyzed": 2,
                "sources_breakdown": {"GitHub": 1, "Hacker News": 1},
                "top_tech_stacks": ["Python", "Rust"],
                "filtered_out_count": 0
            }
        })

    def test_parse_insight_response(self, mock_config, sample_llm_response):
        """测试解析 LLM 响应"""
        generator = DailyInsightGenerator(mock_config)

        insight = generator._parse_insight_response(sample_llm_response, "2026-02-14")

        assert insight.date == "2026-02-14"
        assert insight.macro_trend.title == "AI 依然火爆"
        assert len(insight.high_impact_picks) == 1
        assert insight.high_impact_picks[0].title == "Project A"
        assert len(insight.hidden_gems) == 1
        assert insight.statistics.total_analyzed == 2

    def test_parse_insight_response_with_code_block(self, mock_config, sample_llm_response):
        """测试解析带代码块的 LLM 响应"""
        generator = DailyInsightGenerator(mock_config)

        wrapped_response = f"```json\n{sample_llm_response}\n```"
        insight = generator._parse_insight_response(wrapped_response, "2026-02-14")

        assert insight.date == "2026-02-14"
        assert insight.macro_trend.title == "AI 依然火爆"

    def test_create_empty_insight(self, mock_config):
        """测试创建空洞察报告"""
        generator = DailyInsightGenerator(mock_config)

        insight = generator._create_empty_insight("2026-02-14")

        assert insight.date == "2026-02-14"
        assert insight.macro_trend.title == "数据不足"
        assert len(insight.high_impact_picks) == 0
        assert len(insight.hidden_gems) == 0


class TestFactoryFunction:
    """工厂函数测试"""

    def test_create_daily_insight_generator(self):
        """测试工厂函数"""
        config = MagicMock()
        config.ai.default_provider = "openai"
        config.ai.openai.api_key = "test-key"
        config.app = {"output_dir": "./output"}

        generator = create_daily_insight_generator(config)

        assert isinstance(generator, DailyInsightGenerator)
        assert generator.config == config


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

