"""
Scrapy Item Pipelines
处理和转换抓取的数据
"""

import logging
import re
from typing import Any, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from readability import Document
from scrapy import Spider
from scrapy.crawler import Crawler

from .items import FetchResultItem, ArticleItem, ListPageItem


logger = logging.getLogger(__name__)


class ContentCleanerPipeline:
    """
    内容清洗 Pipeline
    清理 HTML 中的噪声元素
    """

    # 需要移除的噪声标签
    NOISE_TAGS = [
        "script", "style", "nav", "footer", "header", "aside",
        "form", "iframe", "noscript", "svg", "button", "input",
    ]

    # 噪声 class/id 模式
    NOISE_PATTERNS = re.compile(
        r"(ad[-_]?|advertisement|sidebar|comment|social|share|"
        r"related|recommend|footer|header|nav[-_]?|menu|popup|modal)",
        re.IGNORECASE
    )

    def process_item(self, item: Any, spider: Spider) -> Any:
        """清洗 HTML 内容"""
        if not isinstance(item, FetchResultItem):
            return item

        html = item.get("html")
        if not html:
            return item

        try:
            soup = BeautifulSoup(html, "lxml")
            self._clean_soup(soup)
            item["html"] = str(soup)
        except Exception as e:
            logger.warning(f"HTML cleaning failed: {e}")

        return item

    def _clean_soup(self, soup: BeautifulSoup) -> None:
        """清理 BeautifulSoup 对象"""
        # 移除噪声标签
        for tag_name in self.NOISE_TAGS:
            for tag in soup.find_all(tag_name):
                tag.decompose()

        # 移除匹配噪声模式的元素
        for elem in soup.find_all(True):
            classes = elem.get("class", [])
            elem_id = elem.get("id", "")

            class_str = " ".join(classes) if isinstance(classes, list) else str(classes)

            if self.NOISE_PATTERNS.search(class_str) or self.NOISE_PATTERNS.search(elem_id):
                # 保留主要内容区域
                if not any(c in class_str.lower() for c in ["main", "content", "article", "post"]):
                    elem.decompose()


class ContentExtractorPipeline:
    """
    内容提取 Pipeline
    从 HTML 中提取结构化内容
    """

    def process_item(self, item: Any, spider: Spider) -> Any:
        """提取内容"""
        if isinstance(item, FetchResultItem):
            return self._process_fetch_result(item, spider)
        elif isinstance(item, ArticleItem):
            return self._process_article(item, spider)
        return item

    def _process_fetch_result(self, item: FetchResultItem, spider: Spider) -> FetchResultItem:
        """处理抓取结果，提取元数据"""
        html = item.get("html")
        if not html:
            return item

        try:
            soup = BeautifulSoup(html, "lxml")

            # 提取标题
            if not item.get("title"):
                title_tag = soup.find("title")
                if title_tag:
                    item["title"] = title_tag.get_text(strip=True)

            # 提取描述
            if not item.get("description"):
                meta_desc = soup.find("meta", attrs={"name": "description"})
                if meta_desc:
                    item["description"] = meta_desc.get("content", "")

            # 提取纯文本
            if not item.get("text"):
                try:
                    doc = Document(html)
                    item["text"] = doc.summary()
                except Exception:
                    item["text"] = soup.get_text(separator="\n", strip=True)[:5000]

        except Exception as e:
            logger.warning(f"Content extraction failed: {e}")

        return item

    def _process_article(self, item: ArticleItem, spider: Spider) -> ArticleItem:
        """处理文章项，提取内容"""
        content = item.get("content") or item.get("readme")

        if content and not item.get("markdown"):
            # 将 HTML 转换为简化的 Markdown
            item["markdown"] = self._html_to_markdown(content)

        return item

    def _html_to_markdown(self, html: str) -> str:
        """简单的 HTML 到 Markdown 转换"""
        if not html:
            return ""

        try:
            soup = BeautifulSoup(html, "lxml")

            # 移除脚本和样式
            for tag in soup.find_all(["script", "style"]):
                tag.decompose()

            text = soup.get_text(separator="\n", strip=True)

            # 清理多余空行
            lines = [line.strip() for line in text.split("\n") if line.strip()]
            return "\n\n".join(lines[:100])  # 限制长度

        except Exception:
            return html[:3000]


class ListParserPipeline:
    """
    列表页解析 Pipeline
    根据配置的选择器解析列表页
    """

    def process_item(self, item: Any, spider: Spider) -> Any:
        """解析列表页"""
        if not isinstance(item, FetchResultItem):
            return item

        parsed_data = item.get("parsed_data", {})
        list_parser = parsed_data.get("list_parser", {})

        if not list_parser.get("container"):
            return item

        html = item.get("html")
        if not html:
            return item

        try:
            articles = self._parse_list_page(
                html=html,
                base_url=item.get("url", ""),
                list_parser=list_parser,
                site_name=item.get("site_name", "Unknown"),
            )

            # 将解析的文章列表添加到 parsed_data
            parsed_data["items"] = articles
            item["parsed_data"] = parsed_data
            item["page_type"] = "list"

        except Exception as e:
            logger.error(f"List parsing failed: {e}")

        return item

    def _parse_list_page(
        self,
        html: str,
        base_url: str,
        list_parser: dict[str, Any],
        site_name: str,
    ) -> list[dict[str, Any]]:
        """解析列表页"""
        soup = BeautifulSoup(html, "lxml")

        container_selector = list_parser.get("container", "")
        selectors = list_parser.get("selectors", {})
        url_prefix = list_parser.get("url_prefix", "")

        items = []
        containers = soup.select(container_selector)

        for container in containers:
            item_data = {"source": site_name}

            for field, selector in selectors.items():
                elem = container.select_one(selector)
                if not elem:
                    continue

                if field == "url":
                    href = elem.get("href", "")
                    if href:
                        if href.startswith("/"):
                            href = url_prefix + href if url_prefix else urljoin(base_url, href)
                        elif not href.startswith("http"):
                            href = urljoin(base_url, href)
                        item_data["url"] = href
                elif field in ("tags",):
                    # 多值字段，查找所有匹配元素
                    all_elems = container.select(selector)
                    item_data[field] = [e.get_text(strip=True) for e in all_elems]
                else:
                    item_data[field] = elem.get_text(strip=True)

            if item_data.get("url") and item_data.get("title"):
                items.append(item_data)

        return items


class ResultCollectorPipeline:
    """
    结果收集 Pipeline
    将处理后的 items 收集到 spider 的结果列表中
    """

    def process_item(self, item: Any, spider: Spider) -> Any:
        """收集处理结果"""
        if not hasattr(spider, "results"):
            spider.results = []

        spider.results.append(item)
        return item


class DetailFetcherPipeline:
    """
    详情页抓取 Pipeline
    根据配置决定是否需要二次爬取详情页

    注意：这个 Pipeline 会生成新的请求，需要在 Spider 中处理
    """

    def process_item(self, item: Any, spider: Spider) -> Any:
        """标记需要二次爬取的项目"""
        if not isinstance(item, FetchResultItem):
            return item

        parsed_data = item.get("parsed_data", {})
        detail_parser = parsed_data.get("detail_parser", {})

        if not detail_parser.get("enabled", False):
            return item

        items = parsed_data.get("items", [])
        max_details = detail_parser.get("max_details", 20)

        # 标记需要抓取详情的 URL
        urls_to_fetch = []
        for i, article in enumerate(items):
            if i >= max_details:
                break
            url = article.get("url")
            if url:
                urls_to_fetch.append(url)

        parsed_data["detail_urls"] = urls_to_fetch
        item["parsed_data"] = parsed_data

        return item

