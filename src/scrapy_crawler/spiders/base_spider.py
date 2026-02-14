"""
基础 Spider 类
提供通用的配置加载和解析功能
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Generator, Optional
from urllib.parse import urljoin

import scrapy
from scrapy.http import Response, Request
from bs4 import BeautifulSoup
from readability import Document
import trafilatura

from ..items import FetchResultItem, ArticleItem


logger = logging.getLogger(__name__)


class BaseSiteSpider(scrapy.Spider):
    """
    基础站点 Spider

    支持从 YAML 配置动态加载解析规则
    """

    name = "base_site"

    # 常见列表容器选择器（自动检测用）
    LIST_CONTAINER_PATTERNS = [
        "article", "[class*='post']", "[class*='item']", "[class*='entry']",
        "[class*='story']", "[class*='card']", "[class*='repo']", "li[class]",
    ]

    # 常见标题选择器
    TITLE_SELECTORS = [
        "h1 a", "h2 a", "h3 a", ".title a", ".headline a",
        "[class*='title'] a", "a[class*='title']",
    ]

    def __init__(
        self,
        site_config: Optional[dict[str, Any]] = None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.site_config = site_config or {}
        self.site_info = self.site_config.get("site", {})
        self.site_name = self.site_info.get("name", "Unknown")
        self.start_url = self.site_info.get("url", "")
        self.fetch_config = self.site_config.get("fetch", {})
        self.list_parser = self.site_config.get("list_parser", {})
        self.detail_parser = self.site_config.get("detail_parser", {})

        # 存储结果
        self.results: list[Any] = []
        self.articles: list[dict[str, Any]] = []

    def start_requests(self) -> Generator[Request, None, None]:
        """生成初始请求"""
        if not self.start_url:
            logger.error(f"No start URL configured for {self.site_name}")
            return

        yield scrapy.Request(
            url=self.start_url,
            callback=self.parse_list_page,
            meta={
                "site_config": self.site_config,
                "site_name": self.site_name,
                "page_type": "list",
            },
            errback=self.handle_error,
        )

    def parse_list_page(self, response: Response) -> Generator[Any, None, None]:
        """
        解析列表页

        根据配置提取列表项，如果启用详情爬取则生成详情页请求
        """
        logger.info(f"Parsing list page: {response.url}")

        # 创建抓取结果
        fetch_result = FetchResultItem(
            task_id=str(uuid.uuid4()),
            url=response.url,
            site_name=self.site_name,
            site_config=self.site_config,
            status="success",
            method="scrapy",
            page_type="list",
            html=response.text,
            status_code=response.status,
            fetched_at=datetime.now().isoformat(),
        )

        # 解析列表项
        articles = self._parse_list_items(response)
        logger.info(f"Found {len(articles)} items on {self.site_name}")

        # 存储到 parsed_data
        fetch_result["parsed_data"] = {
            "items": articles,
            "list_parser": self.list_parser,
            "detail_parser": self.detail_parser,
        }

        # 保存抓取结果
        self.results.append(fetch_result)

        # 如果启用详情爬取，生成详情页请求
        if self.detail_parser.get("enabled", False):
            max_details = self.detail_parser.get("max_details", 20)

            for i, article in enumerate(articles[:max_details]):
                url = article.get("url")
                if not url:
                    continue

                yield scrapy.Request(
                    url=url,
                    callback=self.parse_detail_page,
                    meta={
                        "site_config": self.site_config,
                        "site_name": self.site_name,
                        "article_data": article,
                        "page_type": "content",
                    },
                    errback=self.handle_error,
                    priority=-i,  # 保持顺序
                )
        else:
            # 不需要详情爬取，直接输出文章
            for article in articles:
                article_item = ArticleItem(
                    id=str(uuid.uuid4()),
                    source=self.site_name,
                    url=article.get("url", ""),
                    title=article.get("title", ""),
                    description=article.get("description", ""),
                    language=article.get("language"),
                    stars=article.get("stars"),
                    forks=article.get("forks"),
                    stars_today=article.get("stars_today"),
                    tags=article.get("tags"),
                    author=article.get("author"),
                )
                self.articles.append(dict(article_item))
                yield article_item

    def parse_detail_page(self, response: Response) -> Generator[ArticleItem, None, None]:
        """
        解析详情页

        提取文章正文内容
        """
        article_data = response.meta.get("article_data", {})
        logger.info(f"Parsing detail: {article_data.get('title', response.url)[:50]}...")

        # 提取内容
        content = self._extract_detail_content(response)

        # 创建文章 Item
        article = ArticleItem(
            id=str(uuid.uuid4()),
            source=self.site_name,
            url=response.url,
            title=article_data.get("title", ""),
            description=article_data.get("description", ""),
            language=article_data.get("language"),
            stars=article_data.get("stars"),
            forks=article_data.get("forks"),
            stars_today=article_data.get("stars_today"),
            tags=article_data.get("tags"),
            author=article_data.get("author"),
            content=content.get("content", ""),
            readme=content.get("readme", ""),
            markdown=content.get("markdown", ""),
        )

        self.articles.append(dict(article))
        yield article

    def _parse_list_items(self, response: Response) -> list[dict[str, Any]]:
        """根据配置解析列表项"""
        if not self.list_parser.get("container"):
            # 尝试自动检测
            return self._auto_detect_list(response)

        return self._parse_with_config(response)

    def _parse_with_config(self, response: Response) -> list[dict[str, Any]]:
        """使用配置的选择器解析列表"""
        container_selector = self.list_parser.get("container", "")
        selectors = self.list_parser.get("selectors", {})
        url_prefix = self.list_parser.get("url_prefix", "")

        items = []
        containers = response.css(container_selector)

        for container in containers:
            item_data = {"source": self.site_name}

            for field, selector in selectors.items():
                if field == "url":
                    href = container.css(f"{selector}::attr(href)").get()
                    if href:
                        if href.startswith("/"):
                            href = url_prefix + href if url_prefix else urljoin(response.url, href)
                        elif not href.startswith("http"):
                            href = urljoin(response.url, href)
                        item_data["url"] = href
                elif field in ("tags",):
                    # 多值字段
                    values = container.css(f"{selector}::text").getall()
                    item_data[field] = [v.strip() for v in values if v.strip()]
                else:
                    text = container.css(f"{selector}::text").get()
                    if not text:
                        # 尝试获取子元素文本
                        text = container.css(selector).xpath("string()").get()
                    if text:
                        item_data[field] = text.strip()

            if item_data.get("url") and item_data.get("title"):
                items.append(item_data)

        return items

    def _auto_detect_list(self, response: Response) -> list[dict[str, Any]]:
        """自动检测列表项"""
        soup = BeautifulSoup(response.text, "lxml")
        items = []

        for pattern in self.LIST_CONTAINER_PATTERNS:
            containers = soup.select(pattern)
            if len(containers) >= 3:
                for container in containers:
                    item = self._extract_item_from_container(container, response.url)
                    if item:
                        items.append(item)
                if items:
                    break

        return items

    def _extract_item_from_container(
        self, container: Any, base_url: str
    ) -> Optional[dict[str, Any]]:
        """从容器元素提取项目信息"""
        item = {"source": self.site_name}

        # 尝试各种标题选择器
        for selector in self.TITLE_SELECTORS:
            elem = container.select_one(selector)
            if elem:
                item["title"] = elem.get_text(strip=True)
                href = elem.get("href")
                if href:
                    if not href.startswith("http"):
                        href = urljoin(base_url, href)
                    item["url"] = href
                break

        # 如果没找到带链接的标题，尝试单独找标题和链接
        if not item.get("title"):
            for tag in ["h1", "h2", "h3", "h4"]:
                elem = container.find(tag)
                if elem:
                    item["title"] = elem.get_text(strip=True)
                    break

        if not item.get("url"):
            link = container.find("a", href=True)
            if link:
                href = link["href"]
                if not href.startswith("http"):
                    href = urljoin(base_url, href)
                item["url"] = href

        if item.get("title") and item.get("url"):
            return item
        return None

    def _extract_detail_content(self, response: Response) -> dict[str, Any]:
        """提取详情页内容（使用 trafilatura）"""
        result = {
            "content": "",
            "readme": "",
            "markdown": "",
        }

        try:
            # 使用 trafilatura 提取正文
            text = trafilatura.extract(
                response.text,
                include_comments=False,
                include_tables=True,
                no_fallback=False,
                favor_precision=True,
            )
            if text:
                result["markdown"] = text[:5000]
                result["content"] = text
            else:
                # trafilatura 提取失败，回退到 readability
                logger.debug("Trafilatura extraction returned empty, falling back to readability")
                doc = Document(response.text)
                content_html = doc.summary()
                result["content"] = content_html

                soup = BeautifulSoup(content_html, "lxml")
                text = soup.get_text(separator="\n", strip=True)
                result["markdown"] = text[:5000]
        except Exception as e:
            logger.warning(f"Content extraction failed: {e}")
            # 最终回退到 readability
            try:
                doc = Document(response.text)
                content_html = doc.summary()
                result["content"] = content_html

                soup = BeautifulSoup(content_html, "lxml")
                text = soup.get_text(separator="\n", strip=True)
                result["markdown"] = text[:5000]
            except Exception as e2:
                logger.warning(f"Readability extraction also failed: {e2}")

        return result

    def handle_error(self, failure):
        """处理请求错误"""
        request = failure.request
        logger.error(f"Request failed: {request.url}, error: {failure.value}")

        # 记录失败的请求
        fetch_result = FetchResultItem(
            task_id=str(uuid.uuid4()),
            url=request.url,
            site_name=self.site_name,
            site_config=self.site_config,
            status="failed",
            method="scrapy",
            error_message=str(failure.value),
            fetched_at=datetime.now().isoformat(),
        )
        self.results.append(fetch_result)

    def closed(self, reason: str):
        """Spider 关闭时的回调"""
        logger.info(
            f"Spider {self.name} closed: {reason}. "
            f"Fetched {len(self.results)} results, {len(self.articles)} articles."
        )

