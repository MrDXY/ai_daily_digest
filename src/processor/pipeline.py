"""
处理流水线
将 HTML 清洗和 AI 摘要组合成完整的处理流程

支持的站点类型:
- structured: 目录页面，需要二次爬取子页面内容
- article: 内容页面，直接爬取当前页面

配置说明:
- site.type: 页面类型 (structured | article)
- list_parser: 列表页解析配置，如果为空则直接作为内容页处理
- detail_parser: 详情页解析配置（使用 trafilatura 自动提取正文）
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Optional, Callable

import trafilatura

from ..core.config import AppConfig, get_cache_dir
from ..core.models import FetchTask, FetchResult, FetchStatus, FetchPageType, Article
from ..core.cache import AIPayloadCache, AISummaryCache
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
    5. 使用 trafilatura 提取正文内容
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
        self._errors: list[str] = []

        cache_dir = get_cache_dir(config) / "ai_payload"
        self._ai_payload_cache = AIPayloadCache(
            cache_dir=cache_dir,
            enabled=config.crawler.cache.enabled,
        )
        summary_cache_dir = get_cache_dir(config) / "ai_summary"
        self._ai_summary_cache = AISummaryCache(
            cache_dir=summary_cache_dir,
            enabled=config.crawler.cache.enabled,
        )

    async def __aenter__(self):
        self.summarizer = create_summarizer(self.config.ai, self.config)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.summarizer:
            await self.summarizer.close()

    def set_fetch_callback(self, callback: Callable):
        """设置二次爬取回调函数"""
        self._fetch_callback = callback

    def get_errors(self) -> list[str]:
        """获取处理错误列表"""
        return list(self._errors)

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
        list_parser = site_config.get("list_parser", {})
        detail_parser = site_config.get("detail_parser", {})

        try:
            page_type = result.page_type
            if page_type == FetchPageType.UNKNOWN:
                page_type = self._infer_page_type(site_config)

            if page_type == FetchPageType.CONTENT:
                items = await self._process_content_page(result, site_config)
            else:
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
        list_parser = result.parsed_data.get("list_parser") or site_config.get("list_parser", {})
        detail_parser = site_config.get("detail_parser", {})

        container = list_parser.get("container")
        selectors = list_parser.get("selectors", {})
        url_prefix = list_parser.get("url_prefix", "")

        if not container or not selectors:
            logger.warning("Missing list_parser config, treating as content page")
            return await self._process_content_page(result, site_config)

        items = self._extract_list_items(result, container, selectors, url_prefix)

        logger.info(f"Extracted {len(items)} items from list page")

        # 清洗每个项目的描述
        for item in items:
            if item.get("description"):
                _, clean_text = self.cleaner.clean(
                    f"<p>{item['description']}</p>",
                    base_url=result.url,
                )
                item["description"] = clean_text

        list_depth = self._get_list_depth(site_config, list_parser)
        if list_depth > 1 and self._fetch_callback:
            items = await self._extend_list_items_with_depth(
                items=items,
                result=result,
                site_config=site_config,
                list_parser=list_parser,
                list_depth=list_depth,
            )

        # 检查是否需要二次爬取详情页
        if detail_parser.get("enabled", False) and self._fetch_callback:
            items = await self._fetch_details(items, site_config)
        else:
            # 无二次爬取时，直接构建 AI payload
            for item in items:
                self._attach_ai_payload(item, detail_parser)

        return items

    async def _process_content_page(
        self,
        result: FetchResult,
        site_config: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """
        处理内容页面

        使用 trafilatura 自动提取正文内容
        """
        detail_parser = site_config.get("detail_parser", {})

        item = {"url": result.url}

        html = result.html
        if not html and result.parsed_data.get("crawl4ai"):
            html = result.parsed_data.get("crawl4ai", {}).get("cleaned_html")

        if html:
            # 使用 trafilatura 提取正文
            article_data = self._extract_with_trafilatura(html)
            item = {
                "title": article_data.get("title", "Untitled"),
                "url": result.url,
                "description": "",
                "content": article_data.get("text", ""),
            }
        elif result.text:
            item = {
                "title": "Untitled",
                "url": result.url,
                "description": "",
                "content": result.text,
            }
        else:
            # 提取元数据作为基础信息
            metadata = self.cleaner.extract_metadata(html or "")
            item = {
                "title": metadata.get("title", "Untitled"),
                "url": result.url,
                "description": metadata.get("description", ""),
                "content": "",
            }

        # 预先构建 AI 输入并缓存
        self._attach_ai_payload(item, detail_parser)

        return [item]

    def _extract_with_trafilatura(self, html: str) -> dict[str, str]:
        """使用 trafilatura 提取文章内容"""
        from bs4 import BeautifulSoup

        try:
            # 使用 trafilatura 提取正文
            text = trafilatura.extract(
                html,
                include_comments=False,
                include_tables=True,
                no_fallback=False,
                favor_precision=True,
            )

            # 提取标题
            soup = BeautifulSoup(html, "lxml")
            title = ""

            # 尝试从 meta og:title 获取
            og_title = soup.find("meta", property="og:title")
            if og_title and og_title.get("content"):
                title = og_title.get("content")

            # 尝试从 title 标签获取
            if not title:
                title_tag = soup.find("title")
                if title_tag:
                    title = title_tag.get_text(strip=True)

            # 尝试从 h1 获取
            if not title:
                h1 = soup.find("h1")
                if h1:
                    title = h1.get_text(strip=True)

            if text:
                return {"title": title, "text": text}

            # trafilatura 提取失败，回退到 cleaner
            logger.debug("Trafilatura extraction returned empty, falling back to cleaner")
            return self.cleaner.extract_article(html)

        except Exception as e:
            logger.warning(f"Trafilatura extraction failed: {e}")
            return self.cleaner.extract_article(html)

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

        # 过滤有效 URL 的项目
        items_to_fetch = [
            item for item in items
            if item.get("url") and item["url"].startswith("http")
        ][:max_details]

        if not items_to_fetch:
            return items

        # 优先使用 AI payload 缓存，命中则跳过爬虫
        pending_fetch = []
        for item in items_to_fetch:
            url = item.get("url")
            cached_payload = self._ai_payload_cache.get(url)
            if cached_payload:
                self._merge_payload_into_item(item, cached_payload)
                item["ai_payload"] = cached_payload
                continue

            pending_fetch.append(item)

        if not pending_fetch:
            return items

        logger.info(f"Fetching {len(pending_fetch)} detail pages...")

        # 调用 fetch 回调获取详情页内容
        urls = [item["url"] for item in pending_fetch]
        detail_results = await self._fetch_callback(urls, site_config)

        # 更新 items 中的内容
        url_to_result = {r.url: r for r in detail_results}

        for item in pending_fetch:
            url = item.get("url")
            detail_result = url_to_result.get(url)
            if not detail_result or detail_result.status != FetchStatus.SUCCESS:
                item["_fetch_failed"] = True
                self._record_fetch_failure(url, site_config, detail_result)
                continue

            detail_html = detail_result.html
            if not detail_html and detail_result.parsed_data.get("crawl4ai"):
                detail_html = detail_result.parsed_data.get("crawl4ai", {}).get("cleaned_html")

            if detail_html:
                # 使用 trafilatura 提取正文
                article_data = self._extract_with_trafilatura(detail_html)
                item["content"] = article_data.get("text", "")
                # 如果列表页没有标题，使用详情页标题
                if not item.get("title"):
                    item["title"] = article_data.get("title", "Untitled")
            elif detail_result.text:
                item["content"] = detail_result.text

            # 构建 AI payload 并缓存
            self._attach_ai_payload(item, detail_parser)

        return items

    def _infer_page_type(self, site_config: dict[str, Any]) -> FetchPageType:
        """回退的页面类型推断"""
        site_info = site_config.get("site", {})
        site_type = site_info.get("type", "structured")
        list_parser = site_config.get("list_parser", {})

        if site_type == "article" or not list_parser:
            return FetchPageType.CONTENT
        return FetchPageType.LIST

    def _get_list_depth(self, site_config: dict[str, Any], list_parser: dict[str, Any]) -> int:
        """获取目录页爬取深度"""
        depth = (
            list_parser.get("depth")
            or site_config.get("fetch", {}).get("list_depth")
            or self.config.crawler.list_depth
            or 1
        )
        try:
            depth_int = int(depth)
        except (TypeError, ValueError):
            depth_int = 1
        return max(depth_int, 1)

    def _extract_list_items(
        self,
        result: FetchResult,
        container: str,
        selectors: dict[str, Any],
        url_prefix: str,
    ) -> list[dict[str, Any]]:
        """抽取列表页条目"""
        if result.parsed_data.get("list_items"):
            return list(result.parsed_data.get("list_items"))

        if not result.html:
            return []

        return self.cleaner.extract_structured(
            html=result.html,
            selectors=selectors,
            container_selector=container,
            base_url=result.url,
            url_prefix=url_prefix,
        )

    async def _extend_list_items_with_depth(
        self,
        items: list[dict[str, Any]],
        result: FetchResult,
        site_config: dict[str, Any],
        list_parser: dict[str, Any],
        list_depth: int,
    ) -> list[dict[str, Any]]:
        """按目录页深度扩展列表项"""
        next_page_selector = list_parser.get("next_page_selector")
        if not next_page_selector:
            return items

        visited = {result.url}
        current_results = [result]

        for _ in range(1, list_depth):
            next_urls = []
            for page_result in current_results:
                next_url = self._extract_next_page_url(
                    page_result.html,
                    next_page_selector,
                    page_result.url,
                )
                if next_url and next_url not in visited:
                    visited.add(next_url)
                    next_urls.append(next_url)

            if not next_urls:
                break

            next_results = await self._fetch_callback(next_urls, site_config)
            current_results = [
                r for r in next_results
                if r and r.status == FetchStatus.SUCCESS
            ]

            for page_result in current_results:
                extra_items = self._extract_list_items(
                    page_result,
                    list_parser.get("container"),
                    list_parser.get("selectors", {}),
                    list_parser.get("url_prefix", ""),
                )
                items.extend(extra_items)

        return items

    def _extract_next_page_url(
        self,
        html: Optional[str],
        selector: str,
        base_url: str,
    ) -> Optional[str]:
        """根据选择器提取下一页链接"""
        if not html:
            return None

        from bs4 import BeautifulSoup
        from urllib.parse import urljoin

        soup = BeautifulSoup(html, "lxml")
        elem = soup.select_one(selector)
        if not elem:
            return None

        href = elem.get("href") or ""
        if not href:
            return None

        return urljoin(base_url, href)

    async def _summarize_items(
        self,
        items: list[dict[str, Any]],
        source: str,
        detail_parser: dict[str, Any] = None,
    ) -> list[Article]:
        """
        对项目列表进行 AI 摘要

        使用 trafilatura 提取的正文内容传递给 AI 进行分析
        """
        if not self.summarizer:
            raise RuntimeError("Summarizer not initialized")

        articles = []
        batch_size = self.config.digest.batch_size

        # 分批处理
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]

            # 准备批量摘要输入
            summarize_inputs = []
            input_items = []
            cached_articles: list[Article] = []
            cached_summary_map: dict[str, dict[str, Any]] = {}
            for item in batch:
                if item.get("_fetch_failed"):
                    self._errors.append(
                        f"详情页抓取失败，已跳过 AI: {item.get('title', 'Untitled')} ({item.get('url', '')})"
                    )
                    continue

                url = item.get("url") or ""
                if url:
                    cached_summary = self._ai_summary_cache.get(url)
                    if cached_summary:
                        cached_summary_map[url] = cached_summary
                        cached_articles.append(self._build_article(item, source, cached_summary))
                        continue

                    if url in cached_summary_map:
                        cached_articles.append(self._build_article(item, source, cached_summary_map[url]))
                        continue

                payload = item.get("ai_payload")
                if not payload:
                    payload = self._create_ai_payload(item, detail_parser)

                if not payload.get("content"):
                    self._errors.append(
                        f"AI 输入为空，已跳过: {item.get('title', 'Untitled')} ({item.get('url', '')})"
                    )
                    continue

                summarize_inputs.append({
                    **payload,
                    "source": source,
                })
                input_items.append(item)

            if not summarize_inputs:
                articles.extend(cached_articles)
                continue

            # 批量摘要
            results = await self.summarizer.summarize_batch(
                items=summarize_inputs,
                concurrency=3,
            )

            # 构建 Article 对象
            for j, summary in enumerate(results):
                original_item = input_items[j]
                article = self._build_article(original_item, source, summary)
                articles.append(article)

                url = original_item.get("url") or ""
                if url:
                    self._ai_summary_cache.set(url, summary)

            articles.extend(cached_articles)
            logger.info(f"Processed batch {i // batch_size + 1}, "
                       f"total articles: {len(articles)}")

        return articles

    def _build_article(
        self,
        item: dict[str, Any],
        source: str,
        summary: dict[str, Any],
    ) -> Article:
        """构建 Article 对象（AI 结果或缓存结果通用）"""
        return Article(
            id=str(uuid.uuid4()),
            source=source,
            url=item.get("url", ""),
            title=item.get("title", "Untitled"),
            description=item.get("description"),
            summary=summary.get("summary", ""),
            core_value=summary.get("core_value", ""),
            tech_stack=summary.get("tech_stack", []),
            recommendation=summary.get("recommendation", ""),
            score=summary.get("score", 50.0),
            language=item.get("language"),
            stars=self._parse_stars(item.get("stars")),
            metadata={
                k: v for k, v in item.items()
                if k not in ["title", "url", "description", "content", "language", "stars", "ai_payload", "_fetch_failed"]
            },
            processed_at=datetime.now(),
        )

    def _create_ai_payload(
        self,
        item: dict[str, Any],
        detail_parser: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """构建发送给 AI 的 payload"""
        content = item.get("content") or item.get("description") or ""

        payload = {
            "title": item.get("title", "Untitled"),
            "content": content,
            "description": item.get("description", ""),
        }

        payload.update({
            k: v for k, v in item.items()
            if k not in ["title", "content", "description", "ai_payload"]
        })

        return payload

    def _attach_ai_payload(
        self,
        item: dict[str, Any],
        detail_parser: Optional[dict[str, Any]] = None,
    ) -> None:
        """为 item 构建并缓存 AI payload"""
        payload = self._create_ai_payload(item, detail_parser)
        item["ai_payload"] = payload

        url = item.get("url")
        if url:
            self._ai_payload_cache.set(url, payload)

    def _merge_payload_into_item(self, item: dict[str, Any], payload: dict[str, Any]) -> None:
        """将缓存的 payload 合并回 item"""
        for key, value in payload.items():
            if key not in item or not item.get(key):
                item[key] = value

    def _record_fetch_failure(
        self,
        url: str,
        site_config: dict[str, Any],
        result: Optional[FetchResult],
    ) -> None:
        """记录抓取失败信息"""
        site_name = site_config.get("site", {}).get("name", "Unknown")
        if result is None:
            message = f"详情页抓取失败: {site_name} | {url} | 未返回结果"
        else:
            status_code = result.status_code or "N/A"
            error_message = result.error_message or "Unknown error"
            message = (
                f"详情页抓取失败: {site_name} | {url} | "
                f"HTTP {status_code} | {error_message}"
            )

        self._errors.append(message)

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
