"""
处理流水线
将 HTML 清洗和 AI 摘要组合成完整的处理流程

支持的站点类型:
- structured: 目录页面，需要二次爬取子页面内容
- article: 内容页面，直接爬取当前页面

配置说明:
- site.type: 页面类型 (structured | article)
- list_parser: 列表页解析配置，如果为空则直接作为内容页处理
- detail_parser: 详情页解析配置
  - content_selectors: 最终内容获取的字段配置
  - use_readability: 是否使用 readability 自动提取
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Optional, Callable

from ..core.config import AppConfig
from ..core.models import FetchTask, FetchResult, FetchStatus, Article
from .html_cleaner import HTMLCleaner
from .ai_summarizer import AISummarizer, create_summarizer


logger = logging.getLogger(__name__)


class ProcessingPipeline:
    """
    处理流水线

    流程：
    1. 接收 FetchResult
    2. 根据站点配置判断页面类型
    3. 如果是 structured 类型且有 list_parser，提取列表项并二次爬取
    4. 如果是 article 类型或无 list_parser，直接解析内容
    5. 根据 detail_parser.content_selectors 提取最终内容字段
    6. 调用 AI 进行脱水摘要
    7. 生成 Article 对象
    """

    def __init__(self, config: AppConfig, fetch_callback: Optional[Callable] = None):
        """
        初始化处理流水线

        Args:
            config: 应用配置
            fetch_callback: 用于二次爬取的回调函数，接收 URL 列表，返回 FetchResult 列表
        """
        self.config = config
        self.cleaner = HTMLCleaner()
        self.summarizer: Optional[AISummarizer] = None
        self._fetch_callback = fetch_callback

    async def __aenter__(self):
        self.summarizer = create_summarizer(self.config.ai, self.config)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.summarizer:
            await self.summarizer.close()

    def set_fetch_callback(self, callback: Callable):
        """设置二次爬取回调函数"""
        self._fetch_callback = callback

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

        site_info = site_config.get("site", {})
        site_name = site_info.get("name", "Unknown")
        site_type = site_info.get("type", "structured")
        list_parser = site_config.get("list_parser", {})
        detail_parser = site_config.get("detail_parser", {})

        try:
            # 判断处理方式：
            # 1. 如果 site.type == "article" 或 list_parser 为空，直接处理当前页面为内容页
            # 2. 如果 site.type == "structured" 且有 list_parser，处理为目录页，可能需要二次爬取

            if site_type == "article" or not list_parser:
                # 直接作为内容页处理
                items = await self._process_content_page(result, site_config)
            else:
                # 作为目录页处理
                items = await self._process_list_page(result, site_config)

            # AI 脱水
            articles = await self._summarize_items(items, site_name, detail_parser)

            return articles

        except Exception as e:
            logger.error(f"Pipeline processing error: {e}")
            return []

    async def _process_list_page(
        self,
        result: FetchResult,
        site_config: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """
        处理目录页面（列表页）

        根据 list_parser 提取列表项，如果需要二次爬取则获取详情内容
        """
        list_parser = site_config.get("list_parser", {})
        detail_parser = site_config.get("detail_parser", {})

        container = list_parser.get("container")
        selectors = list_parser.get("selectors", {})
        url_prefix = list_parser.get("url_prefix", "")

        if not container or not selectors:
            logger.warning("Missing list_parser config, treating as content page")
            return await self._process_content_page(result, site_config)

        # 过滤掉无效的 CSS 选择器（如相邻兄弟选择器 "+ tr"）
        valid_selectors = {
            k: v for k, v in selectors.items()
            if v and not v.strip().startswith('+')
        }

        # 提取列表项
        items = self.cleaner.extract_structured(
            html=result.html,
            selectors=valid_selectors,
            container_selector=container,
            base_url=result.url,
            url_prefix=url_prefix,
        )

        logger.info(f"Extracted {len(items)} items from list page")

        # 清洗每个项目的描述
        for item in items:
            if item.get("description"):
                _, clean_text = self.cleaner.clean(
                    f"<p>{item['description']}</p>",
                    base_url=result.url,
                )
                item["description"] = clean_text

        # 检查是否需要二次爬取详情页
        if detail_parser.get("enabled", False) and self._fetch_callback:
            items = await self._fetch_details(items, site_config)

        return items

    async def _process_content_page(
        self,
        result: FetchResult,
        site_config: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """
        处理内容页面

        根据 detail_parser.content_selectors 提取内容，
        或使用 readability 自动提取
        """
        detail_parser = site_config.get("detail_parser", {})
        content_selectors = detail_parser.get("content_selectors", {})
        use_readability = detail_parser.get("use_readability", True)

        item = {"url": result.url}

        if content_selectors:
            # 使用 content_selectors 提取指定字段
            item = self._extract_content_by_selectors(
                result.html,
                content_selectors,
                result.url,
            )
            item["url"] = result.url
        elif use_readability:
            # 使用 readability 提取正文
            article_data = self.cleaner.extract_article(result.html)
            item = {
                "title": article_data.get("title", "Untitled"),
                "url": result.url,
                "description": "",
                "content": article_data.get("text", ""),
            }
        else:
            # 提取元数据作为基础信息
            metadata = self.cleaner.extract_metadata(result.html)
            _, plain_text = self.cleaner.clean(result.html, result.url)
            item = {
                "title": metadata.get("title", "Untitled"),
                "url": result.url,
                "description": metadata.get("description", ""),
                "content": plain_text,
            }

        return [item]

    def _extract_content_by_selectors(
        self,
        html: str,
        content_selectors: dict[str, Any],
        base_url: str,
    ) -> dict[str, Any]:
        """
        根据 content_selectors 提取内容字段

        content_selectors 格式:
        {
            "title": "h1.article-title",
            "content": "div.article-body",
            "author": "span.author-name",
            "publish_date": "time.publish-date",
            ...
        }
        """
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "lxml")
        result = {}

        for field_name, selector_config in content_selectors.items():
            # 支持简单字符串或复杂配置
            if isinstance(selector_config, str):
                selector = selector_config
                attr = None
            elif isinstance(selector_config, dict):
                selector = selector_config.get("selector", "")
                attr = selector_config.get("attr")  # 可选：提取属性而非文本
            else:
                continue

            if not selector:
                continue

            elem = soup.select_one(selector)
            if elem:
                if attr:
                    result[field_name] = elem.get(attr, "")
                else:
                    # 对于 content 字段，保留更多格式
                    if field_name == "content":
                        result[field_name] = elem.get_text(separator="\n", strip=True)
                    else:
                        result[field_name] = elem.get_text(strip=True)
            else:
                result[field_name] = ""

        return result

    async def _fetch_details(
        self,
        items: list[dict[str, Any]],
        site_config: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """
        二次爬取详情页面
        """
        detail_parser = site_config.get("detail_parser", {})
        max_details = detail_parser.get("max_details", 20)
        content_selectors = detail_parser.get("content_selectors", {})
        use_readability = detail_parser.get("use_readability", True)

        # 过滤有效 URL 的项目
        items_to_fetch = [
            item for item in items
            if item.get("url") and item["url"].startswith("http")
        ][:max_details]

        if not items_to_fetch:
            return items

        logger.info(f"Fetching {len(items_to_fetch)} detail pages...")

        # 调用 fetch 回调获取详情页内容
        urls = [item["url"] for item in items_to_fetch]
        detail_results = await self._fetch_callback(urls, site_config)

        # 更新 items 中的内容
        url_to_result = {r.url: r for r in detail_results if r.status == FetchStatus.SUCCESS}

        for item in items_to_fetch:
            url = item.get("url")
            if url in url_to_result:
                detail_result = url_to_result[url]

                if content_selectors:
                    # 使用 content_selectors 提取
                    extracted = self._extract_content_by_selectors(
                        detail_result.html,
                        content_selectors,
                        url,
                    )
                    # 合并提取的内容到 item
                    for key, value in extracted.items():
                        if value:  # 只更新非空值
                            item[key] = value
                elif use_readability:
                    # 使用 readability 提取正文
                    article_data = self.cleaner.extract_article(detail_result.html)
                    item["content"] = article_data.get("text", "")
                    # 如果列表页没有标题，使用详情页标题
                    if not item.get("title"):
                        item["title"] = article_data.get("title", "Untitled")
                else:
                    # 直接提取纯文本
                    _, plain_text = self.cleaner.clean(detail_result.html, url)
                    item["content"] = plain_text

        return items

    async def _summarize_items(
        self,
        items: list[dict[str, Any]],
        source: str,
        detail_parser: dict[str, Any] = None,
    ) -> list[Article]:
        """
        对项目列表进行 AI 摘要

        支持将 content_selectors 中定义的所有字段传递给 AI 进行分析
        """
        if not self.summarizer:
            raise RuntimeError("Summarizer not initialized")

        articles = []
        batch_size = self.config.digest.batch_size

        # 获取 content_selectors 中定义的字段名（用于构建完整的内容）
        content_selectors = (detail_parser or {}).get("content_selectors", {})
        content_fields = list(content_selectors.keys()) if content_selectors else ["content"]

        # 分批处理
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]

            # 准备批量摘要输入
            summarize_inputs = []
            for item in batch:
                # 构建内容：合并 content_selectors 中定义的所有字段
                content_parts = []
                for field in content_fields:
                    value = item.get(field)
                    if value and field not in ["title", "url"]:
                        if field == "content":
                            content_parts.append(value)
                        else:
                            content_parts.append(f"{field}: {value}")

                # 如果没有 content_selectors 定义的字段，使用默认的 content 或 description
                if not content_parts:
                    content = item.get("content") or item.get("description") or ""
                else:
                    content = "\n\n".join(content_parts)

                summarize_inputs.append({
                    "title": item.get("title", "Untitled"),
                    "content": content,
                    "source": source,
                    "description": item.get("description", ""),
                    # 传递所有原始字段给 AI（可能在分析中有用）
                    **{k: v for k, v in item.items() if k not in ["title", "content", "description"]}
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
                        k: v for k, v in original_item.items()
                        if k not in ["title", "url", "description", "content", "language", "stars"]
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
