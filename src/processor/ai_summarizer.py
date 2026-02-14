"""
AI 摘要器
支持多种 AI 模型后端：Claude, OpenAI, Azure OpenAI, 自定义模型

注意：此模块使用 ai_provider.py 提供的 AIProviderClient 进行 AI 调用
"""

import json
import logging
from typing import Any, Optional

from ..core.config import AIConfig
from ..core.exceptions import AIException, RateLimitException
from .ai_provider import AIProviderClient, AIProviderError, RateLimitError


logger = logging.getLogger(__name__)


# ============================================
# 摘要 Prompt 模板
# ============================================

DIGEST_PROMPT = """你是一个专业的技术内容分析师。请分析以下技术项目/文章，并提供结构化的摘要。

## 输入内容
标题: {title}
来源: {source}
描述: {description}
正文内容:
{content}

## 任务要求
请提供以下信息（JSON 格式）：

1. **summary**: 用 2-3 句话概括项目/文章的核心内容（中文）
2. **core_value**: 这个项目/文章的核心价值是什么？解决了什么问题？（1-2 句话）
3. **tech_stack**: 涉及的主要技术栈（列表形式，如 ["Python", "FastAPI", "PostgreSQL"]）
4. **recommendation**: 推荐理由，为什么值得关注？（1-2 句话）
5. **score**: 综合评分 (0-100)，评分标准（共 10 个维度，总分 100 分）：
    - 创新性 (0-15分): 是否有新颖的想法或独到观点
    - 价值密度 (0-15分): 信息含量/结论密度是否高
    - 可信度 (0-12分): 论据充分、引用可靠、逻辑自洽
    - 可验证性 (0-8分): 结论是否可复现/可验证
    - 实用性 (0-5分): 是否能指导实践或产生可操作启发
    - 清晰度 (0-5分): 表达结构清楚、要点明确
    - 时效性 (0-15分): 与当前趋势/技术演进的相关度
    - 影响力 (0-15分): 对行业/社区/读者的影响潜力
    - 普适性/适用范围 (0-5分): 跨场景可迁移/可借鉴程度
    - 可扩展性/延展性 (0-5分): 是否提供可持续探索的方向或后续空间

## 输出格式
请直接输出 JSON，不要包含其他内容：
```json
{{
  "summary": "...",
  "core_value": "...",
  "tech_stack": ["...", "..."],
  "recommendation": "...",
    "score": 86
}}
```
"""


# ============================================
# AI Summarizer (统一接口)
# ============================================

class AISummarizer:
    """
    AI 摘要器

    使用 AIProviderClient 进行 AI 调用，支持：
    - 动态切换 Provider
    - 自动回退
    - 批量处理
    """

    def __init__(self, config: AIConfig, app_config: Any = None):
        """
        初始化 AI 摘要器

        Args:
            config: AI 配置
            app_config: 完整的应用配置（用于创建 AIProviderClient）
        """
        self.config = config
        self._provider: Optional[AIProviderClient] = None
        self._app_config = app_config

    def _get_provider(self) -> AIProviderClient:
        """获取 AI Provider"""
        if self._provider is None:
            if self._app_config is None:
                raise AIException("App config not provided for AI provider initialization")
            self._provider = AIProviderClient(self._app_config)
        return self._provider

    async def summarize(
        self,
        title: str,
        content: str,
        source: str,
        description: str = "",
        **kwargs,
    ) -> dict[str, Any]:
        """
        生成摘要

        Args:
            title: 标题
            content: 正文内容
            source: 来源
            description: 描述

        Returns:
            摘要结果字典
        """
        provider = self._get_provider()

        # 构建 prompt
        prompt = DIGEST_PROMPT.format(
            title=title,
            source=source,
            description=description or "N/A",
            content=content[:8000],  # 限制内容长度
        )

        try:
            response = await provider.generate_text(
                prompt=prompt,
                system="你是一个专业的技术内容分析师，擅长提取技术文章和开源项目的核心价值。请用中文回答。",
            )

            # 解析 JSON 响应
            result = self._parse_response(response)
            return result

        except RateLimitError as e:
            raise RateLimitException(
                f"Rate limit exceeded: {e}",
                provider=e.provider,
                model=e.model,
                cause=e.cause,
            )
        except AIProviderError as e:
            raise AIException(
                f"AI provider error: {e}",
                provider=e.provider,
                model=e.model,
                cause=e.cause,
            )

    def _parse_response(self, response: str) -> dict[str, Any]:
        """解析 AI 响应"""
        # 尝试提取 JSON
        try:
            # 移除可能的 markdown 代码块标记
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]

            result = json.loads(response.strip())

            # 验证必需字段
            required_fields = ["summary", "core_value", "tech_stack", "recommendation", "score"]
            for field in required_fields:
                if field not in result:
                    result[field] = "" if field != "score" else 50.0
                    if field == "tech_stack":
                        result[field] = []

            # 确保 score 是数字
            score_raw = result.get("score", 50.0)
            # 处理 score 可能是 dict 的情况（如 {"value": 85, "confidence": "high"}）
            if isinstance(score_raw, dict):
                score_raw = score_raw.get("value", score_raw.get("score", 50.0))
            try:
                score = float(score_raw)
            except (TypeError, ValueError):
                score = 50.0
            # 兼容旧的 0-10 评分
            if 0 <= score <= 10:
                score *= 10
            result["score"] = max(0, min(100, score))  # 限制在 0-100

            return result

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse AI response as JSON: {e}")
            # 返回默认结构
            return {
                "summary": response[:500],
                "core_value": "Unable to extract",
                "tech_stack": [],
                "recommendation": "Unable to extract",
                "score": 50.0,
            }

    async def summarize_batch(
        self,
        items: list[dict[str, Any]],
        concurrency: int = 3,
    ) -> list[dict[str, Any]]:
        """
        批量摘要

        Args:
            items: 项目列表，每个项目包含 title, content, source, description
            concurrency: 并发数

        Returns:
            摘要结果列表
        """
        import asyncio

        semaphore = asyncio.Semaphore(concurrency)

        async def process_one(item: dict[str, Any]) -> dict[str, Any]:
            async with semaphore:
                try:
                    result = await self.summarize(
                        title=item.get("title", ""),
                        content=item.get("content", ""),
                        source=item.get("source", ""),
                        description=item.get("description", ""),
                    )
                    result["_source_item"] = item
                    return result
                except Exception as e:
                    logger.error(f"Failed to summarize: {e}")
                    return {
                        "summary": "处理失败",
                        "core_value": str(e),
                        "tech_stack": [],
                        "recommendation": "",
                        "score": 0.0,
                        "_source_item": item,
                        "_error": str(e),
                    }

        results = await asyncio.gather(
            *[process_one(item) for item in items]
        )

        return list(results)

    async def close(self) -> None:
        """关闭 Provider"""
        if self._provider:
            await self._provider.close()
            self._provider = None


def create_summarizer(config: AIConfig, app_config: Any = None) -> AISummarizer:
    """
    工厂函数：创建 AI 摘要器

    Args:
        config: AI 配置
        app_config: 完整的应用配置

    Returns:
        AISummarizer 实例
    """
    return AISummarizer(config, app_config)
