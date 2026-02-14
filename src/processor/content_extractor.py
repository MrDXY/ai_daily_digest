"""
智能内容提取器 (Smart Content Extractor)
自动识别和提取页面核心内容，减少配置复杂度

特点：
1. 自动识别页面类型（列表页/文章页）
2. 智能提取正文内容（无需复杂选择器配置）
3. 支持多种提取策略：readability、CSS选择器、AI辅助
4. 返回结构化的 Markdown 内容
"""

import re
import logging
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag
from readability import Document

logger = logging.getLogger(__name__)


class SmartContentExtractor:
    """智能内容提取器"""

    # 常见列表容器选择器
    LIST_CONTAINER_PATTERNS = [
        "article", "[class*='post']", "[class*='item']", "[class*='entry']",
        "[class*='story']", "[class*='card']", "[class*='repo']", "li[class]",
    ]

    # 常见标题选择器
    TITLE_SELECTORS = [
        "h1 a", "h2 a", "h3 a", ".title a", ".headline a",
        "[class*='title'] a", "a[class*='title']",
    ]

    # 常见描述选择器
    DESCRIPTION_SELECTORS = [
        "p.description", "p.summary", ".description", ".summary",
        "[class*='description']", "[class*='summary']",
    ]

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

    def __init__(self, config: Optional[dict[str, Any]] = None):
        self.config = config or {}

    def extract(self, html: str, url: str, site_config: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """智能提取页面内容"""
        if not html:
            return self._empty_result()

        site_config = site_config or {}
        metadata = self._extract_metadata(html)

        # 检查是否有显式配置
        list_parser = site_config.get("list_parser", {})

        if list_parser.get("container") and list_parser.get("selectors"):
            items = self._extract_with_config(html, list_parser, url)
            if items:
                return {
                    "page_type": "list",
                    "title": metadata.get("title", ""),
                    "items": items,
                    "content": "",
                    "markdown": self._items_to_markdown(items),
                    "metadata": metadata,
                }

        # 自动检测页面类型
        soup = BeautifulSoup(html, "lxml")
        self._clean_soup(soup)

        items = self._auto_detect_list(soup, url)
        if items and len(items) >= 3:
            return {
                "page_type": "list",
                "title": metadata.get("title", ""),
                "items": items,
                "content": "",
                "markdown": self._items_to_markdown(items),
                "metadata": metadata,
            }

        # 作为文章页处理
        article = self._extract_article(html)
        return {
            "page_type": "article",
            "title": article.get("title", metadata.get("title", "")),
            "items": [],
            "content": article.get("text", ""),
            "markdown": article.get("markdown", ""),
            "metadata": metadata,
        }

    def extract_list(self, html: str, url: str, container: str, selectors: dict[str, str], url_prefix: str = "") -> list[dict[str, Any]]:
        """根据配置提取列表"""
        if not html or not container:
            return []

        soup = BeautifulSoup(html, "lxml")
        containers = soup.select(container)

        items = []
        for elem in containers:
            item = self._extract_item_fields(elem, selectors, url, url_prefix)
            if item.get("title") or item.get("url"):
                items.append(item)

        return items

    def extract_article(self, html: str) -> dict[str, str]:
        """提取文章正文"""
        return self._extract_article(html)

    def _extract_article(self, html: str) -> dict[str, str]:
        """使用 readability 提取文章"""
        try:
            doc = Document(html)
            title = doc.title()
            content_html = doc.summary()

            soup = BeautifulSoup(content_html, "lxml")
            text = soup.get_text(separator="\n", strip=True)
            text = self._clean_whitespace(text)
            markdown = self._html_to_markdown(content_html)

            return {"title": title, "content": content_html, "text": text, "markdown": markdown}
        except Exception as e:
            logger.warning(f"Readability extraction failed: {e}")
            soup = BeautifulSoup(html, "lxml")
            self._clean_soup(soup)

            title = ""
            title_tag = soup.find("title")
            if title_tag:
                title = title_tag.get_text(strip=True)

            text = soup.get_text(separator="\n", strip=True)
            text = self._clean_whitespace(text)

            return {"title": title, "content": str(soup), "text": text, "markdown": text}

    def _extract_with_config(self, html: str, list_parser: dict[str, Any], base_url: str) -> list[dict[str, Any]]:
        """使用配置提取列表"""
        container = list_parser.get("container")
        selectors = list_parser.get("selectors", {})
        url_prefix = list_parser.get("url_prefix", "")
        return self.extract_list(html, base_url, container, selectors, url_prefix)

    def _auto_detect_list(self, soup: BeautifulSoup, base_url: str) -> list[dict[str, Any]]:
        """自动检测并提取列表"""
        best_items = []
        best_score = 0

        for pattern in self.LIST_CONTAINER_PATTERNS:
            try:
                containers = soup.select(pattern)
                if len(containers) < 3:
                    continue

                items = []
                for container in containers[:50]:
                    item = self._extract_item_auto(container, base_url)
                    if item.get("title") and item.get("url"):
                        items.append(item)

                score = len(items) * 10
                if items:
                    avg_title_len = sum(len(i.get("title", "")) for i in items) / len(items)
                    if avg_title_len > 10:
                        score += 20
                    desc_count = sum(1 for i in items if i.get("description"))
                    score += desc_count * 2

                if score > best_score:
                    best_score = score
                    best_items = items
            except Exception:
                continue

        return best_items

    def _extract_item_auto(self, container: Tag, base_url: str) -> dict[str, Any]:
        """自动提取单个条目"""
        item = {}

        for selector in self.TITLE_SELECTORS:
            try:
                link = container.select_one(selector)
                if link:
                    item["title"] = link.get_text(strip=True)
                    href = link.get("href", "")
                    if href:
                        item["url"] = self._normalize_url(href, base_url)
                    break
            except Exception:
                continue

        if not item.get("title"):
            link = container.find("a")
            if link:
                text = link.get_text(strip=True)
                if text and len(text) > 5:
                    item["title"] = text
                    href = link.get("href", "")
                    if href:
                        item["url"] = self._normalize_url(href, base_url)

        for selector in self.DESCRIPTION_SELECTORS:
            try:
                desc_elem = container.select_one(selector)
                if desc_elem:
                    item["description"] = desc_elem.get_text(strip=True)
                    break
            except Exception:
                continue

        if not item.get("description"):
            p = container.find("p")
            if p:
                text = p.get_text(strip=True)
                if text and len(text) > 20:
                    item["description"] = text[:500]

        return item

    def _extract_item_fields(self, container: Tag, selectors: dict[str, str], base_url: str, url_prefix: str = "") -> dict[str, Any]:
        """根据选择器提取条目字段"""
        item = {}

        for field, selector in selectors.items():
            if not selector:
                continue

            try:
                if selector.startswith(":scope"):
                    selector = selector.replace(":scope", "").strip()
                    elem = container if not selector else container.select_one(selector)
                else:
                    elem = container.select_one(selector)

                if not elem:
                    continue

                if field == "url":
                    href = elem.get("href", "") if elem.name == "a" else ""
                    if not href:
                        link = elem.find("a")
                        href = link.get("href", "") if link else ""

                    if href:
                        if href.startswith("/"):
                            href = url_prefix + href if url_prefix else urljoin(base_url, href)
                        elif not href.startswith("http"):
                            href = urljoin(base_url, href)
                        item[field] = href
                else:
                    item[field] = elem.get_text(strip=True)
            except Exception:
                continue

        return item

    def _extract_metadata(self, html: str) -> dict[str, str]:
        """提取页面元数据"""
        soup = BeautifulSoup(html, "lxml")
        metadata = {}

        title_tag = soup.find("title")
        if title_tag:
            metadata["title"] = title_tag.get_text(strip=True)

        for meta in soup.find_all("meta"):
            name = meta.get("name", "").lower()
            property_name = meta.get("property", "").lower()
            content = meta.get("content", "")

            if name == "description" or property_name == "og:description":
                metadata["description"] = content
            elif name == "keywords":
                metadata["keywords"] = content
            elif property_name == "og:title":
                metadata["og_title"] = content

        return metadata

    def _clean_soup(self, soup: BeautifulSoup) -> None:
        """清理噪声元素"""
        for tag_name in self.NOISE_TAGS:
            for tag in soup.find_all(tag_name):
                tag.decompose()

        for elem in soup.find_all(True):
            classes = elem.get("class", [])
            if isinstance(classes, list):
                classes = " ".join(classes)
            elem_id = elem.get("id", "")

            if self.NOISE_PATTERNS.search(classes) or self.NOISE_PATTERNS.search(elem_id):
                if not any(x in classes.lower() for x in ["main", "content", "article", "post"]):
                    elem.decompose()

    def _normalize_url(self, href: str, base_url: str) -> str:
        """规范化 URL"""
        if not href:
            return ""
        if href.startswith(("http://", "https://")):
            return href
        if href.startswith("//"):
            parsed = urlparse(base_url)
            return f"{parsed.scheme}:{href}"
        return urljoin(base_url, href)

    def _clean_whitespace(self, text: str) -> str:
        """清理多余空白"""
        text = re.sub(r"\n{3,}", "\n\n", text)
        lines = [line.strip() for line in text.split("\n")]
        return "\n".join(lines)

    def _html_to_markdown(self, html: str) -> str:
        """HTML 转 Markdown"""
        soup = BeautifulSoup(html, "lxml")

        for i in range(1, 7):
            for tag in soup.find_all(f"h{i}"):
                text = tag.get_text(strip=True)
                tag.replace_with(f"\n{'#' * i} {text}\n")

        for a in soup.find_all("a"):
            text = a.get_text(strip=True)
            href = a.get("href", "")
            if href and text:
                a.replace_with(f"[{text}]({href})")

        for ul in soup.find_all(["ul", "ol"]):
            items = [f"- {li.get_text(strip=True)}" for li in ul.find_all("li", recursive=False)]
            ul.replace_with("\n" + "\n".join(items) + "\n")

        for p in soup.find_all("p"):
            text = p.get_text(strip=True)
            p.replace_with(f"\n{text}\n")

        for code in soup.find_all("code"):
            text = code.get_text(strip=True)
            code.replace_with(f"`{text}`")

        for pre in soup.find_all("pre"):
            text = pre.get_text(strip=True)
            pre.replace_with(f"\n```\n{text}\n```\n")

        text = soup.get_text(separator="\n", strip=True)
        return self._clean_whitespace(text)

    def _items_to_markdown(self, items: list[dict[str, Any]]) -> str:
        """将列表条目转换为 Markdown"""
        lines = []
        for i, item in enumerate(items, 1):
            title = item.get("title", "Untitled")
            url = item.get("url", "")
            desc = item.get("description", "")

            if url:
                lines.append(f"{i}. [{title}]({url})")
            else:
                lines.append(f"{i}. {title}")

            if desc:
                lines.append(f"   > {desc[:200]}")
            lines.append("")

        return "\n".join(lines)

    def _empty_result(self) -> dict[str, Any]:
        """返回空结果"""
        return {"page_type": "unknown", "title": "", "items": [], "content": "", "markdown": "", "metadata": {}}


def extract_content(html: str, url: str, site_config: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """便捷函数：智能提取页面内容"""
    extractor = SmartContentExtractor()
    return extractor.extract(html, url, site_config)


def extract_article(html: str) -> dict[str, str]:
    """便捷函数：提取文章正文"""
    extractor = SmartContentExtractor()
    return extractor.extract_article(html)

