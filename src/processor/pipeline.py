"""
处理流水线
将 HTML 清洗和 AI 摘要组合成完整的处理流程
"""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any, Optional

from ..core.config import AppConfig
from ..core.models import FetchResult, FetchStatus, Article
from ..core.exceptions import ParseException
from .html_cleaner import HTMLCleaner
from .ai_summarizer import AISummarizer, create_summarizer


logger = logging.getLogger(__name__)


class ProcessingPipeline:
    """
    处理流水线

    流程：
    1. 接收 FetchResult
    2. 根据站点配置解析 HTML
    3. 提取结构化数据
    4. 调用 AI 进行脱水摘要
    5. 生成 Article 对象
    """

    def __init__(self, config: AppConfig):
        self.config = config
        self.cleaner = HTMLCleaner()
        self.summarizer: Optional[AISummarizer] = None

    async def __aenter__(self):
        self.summarizer = create_summarizer(self.config.ai)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.summarizer:
            await self.summarizer.close()

    async def process(
        self,
        result: FetchResult,
        site_config: dict[str, Any],
    ) -> list[Article]:
        """
        处理单个抓取结果

        Args:
            result: 抓取结果
            site_config: 站点配置

        Returns:
            生成的 Article 列表
        """
        if result.status != FetchStatus.SUCCESS or not result.html:
            logger.warning(f"Skipping failed fetch result: {result.task_id}")
            return []

        site_name = site_config.get("site", {}).get("name", "Unknown")
        site_type = site_config.get("site", {}).get("type", "structured")

        try:
            # 根据站点类型选择处理方式
            if site_type == "structured":
                items = await self._process_structured(result, site_config)
            elif site_type == "article":
                items = await self._process_article(result, site_config)
            else:
                items = await self._process_structured(result, site_config)

            # AI 脱水
            articles = await self._summarize_items(items, site_name)

            return articles

        except Exception as e:
            logger.error(f"Pipeline processing error: {e}")
            return []

    async def _process_structured(
        self,
        result: FetchResult,
        site_config: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """处理结构化页面（如 GitHub Trending）"""
        parser_config = site_config.get("list_parser", {})

        container = parser_config.get("container")
        selectors = parser_config.get("selectors", {})
        url_prefix = parser_config.get("url_prefix", "")

        if not container or not selectors:
            logger.warning("Missing parser config, using readability")
            return await self._process_article(result, site_config)

        # 提取列表项
        items = self.cleaner.extract_structured(
            html=result.html,
            selectors=selectors,
            container_selector=container,
            base_url=result.url,
            url_prefix=url_prefix,
        )

        logger.info(f"Extracted {len(items)} items from structured page")

        # 清洗每个项目的描述
        for item in items:
            if item.get("description"):
                _, clean_text = self.cleaner.clean(
                    f"<p>{item['description']}</p>",
                    base_url=result.url,
                )
                item["description"] = clean_text

        return items

    async def _process_article(
        self,
        result: FetchResult,
        site_config: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """处理文章类页面"""
        # 使用 readability 提取正文
        article_data = self.cleaner.extract_article(result.html)

        return [{
            "title": article_data.get("title", "Untitled"),
            "url": result.url,
            "description": "",
            "content": article_data.get("text", ""),
        }]

    async def _summarize_items(
        self,
        items: list[dict[str, Any]],
        source: str,
    ) -> list[Article]:
        """对项目列表进行 AI 摘要"""
        if not self.summarizer:
            raise RuntimeError("Summarizer not initialized")

        articles = []
        batch_size = self.config.digest.batch_size

        # 分批处理
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]

            # 准备批量摘要输入
            summarize_inputs = []
            for item in batch:
                # 如果没有详细内容，使用描述
                content = item.get("content") or item.get("description") or ""

                summarize_inputs.append({
                    "title": item.get("title", "Untitled"),
                    "content": content,
                    "source": source,
                    "description": item.get("description", ""),
                })

            # 批量摘要
            results = await self.summarizer.summarize_batch(
                items=summarize_inputs,
                concurrency=3,
            )

            # 构建 Article 对象
            for j, summary in enumerate(results):
                original_item = batch[j]

                article = Article(
                    id=str(uuid.uuid4()),
                    source=source,
                    url=original_item.get("url", ""),
                    title=original_item.get("title", "Untitled"),
                    description=original_item.get("description"),
                    summary=summary.get("summary", ""),
                    core_value=summary.get("core_value", ""),
                    tech_stack=summary.get("tech_stack", []),
                    recommendation=summary.get("recommendation", ""),
                    score=summary.get("score", 5.0),
                    language=original_item.get("language"),
                    stars=self._parse_stars(original_item.get("stars")),
                    metadata={
                        "forks": original_item.get("forks"),
                        "stars_today": original_item.get("stars_today"),
                    },
                    processed_at=datetime.now(),
                )

                articles.append(article)

            logger.info(f"Processed batch {i // batch_size + 1}, "
                       f"total articles: {len(articles)}")

        return articles

    def _parse_stars(self, stars_str: Optional[str]) -> Optional[int]:
        """解析 star 数"""
        if not stars_str:
            return None

        try:
            # 处理 "1,234" 或 "1.2k" 格式
            stars_str = stars_str.strip().lower().replace(",", "")

            if "k" in stars_str:
                return int(float(stars_str.replace("k", "")) * 1000)
            elif "m" in stars_str:
                return int(float(stars_str.replace("m", "")) * 1000000)
            else:
                return int(stars_str)
        except:
            return None

    async def process_many(
        self,
        results: list[tuple[FetchResult, dict[str, Any]]],
    ) -> list[Article]:
        """
        批量处理

        Args:
            results: (FetchResult, site_config) 元组列表

        Returns:
            所有生成的 Article 列表
        """
        all_articles = []

        for result, site_config in results:
            articles = await self.process(result, site_config)
            all_articles.extend(articles)

        return all_articles
