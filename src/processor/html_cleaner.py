"""
HTML 清洗器
提取正文内容，清理无关标签
"""

import re
from typing import Any, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag
from readability import Document


class HTMLCleaner:
    """
    HTML 清洗器

    支持两种模式：
    1. 结构化提取：根据 CSS 选择器提取特定元素
    2. 自动提取：使用 readability 算法提取正文
    """

    # 默认需要移除的标签
    DEFAULT_REMOVE_TAGS = [
        "script", "style", "nav", "footer", "header",
        "aside", "form", "iframe", "noscript", "svg",
        "button", "input", "select", "textarea",
    ]

    # 默认需要移除的 class/id 模式
    NOISE_PATTERNS = [
        r"ad[-_]?",
        r"advertisement",
        r"sidebar",
        r"comment",
        r"social",
        r"share",
        r"related",
        r"recommend",
        r"footer",
        r"header",
        r"nav",
        r"menu",
    ]

    def __init__(self, config: Optional[dict[str, Any]] = None):
        self.config = config or {}
        self.remove_tags = self.config.get("remove_tags", self.DEFAULT_REMOVE_TAGS)

    def clean(
        self,
        html: str,
        base_url: Optional[str] = None,
    ) -> tuple[str, str]:
        """
        清洗 HTML

        Args:
            html: 原始 HTML
            base_url: 基础 URL（用于转换相对链接）

        Returns:
            (cleaned_html, plain_text): 清洗后的 HTML 和纯文本
        """
        soup = BeautifulSoup(html, "lxml")

        # 移除无用标签
        for tag_name in self.remove_tags:
            for tag in soup.find_all(tag_name):
                tag.decompose()

        # 移除注释
        for comment in soup.find_all(string=lambda x: isinstance(x, type(soup.new_string("")))):
            if hasattr(comment, 'extract') and '<!--' in str(comment):
                comment.extract()

        # 移除噪声元素
        self._remove_noise_elements(soup)

        # 转换相对链接
        if base_url:
            self._convert_relative_urls(soup, base_url)

        cleaned_html = str(soup)
        plain_text = soup.get_text(separator="\n", strip=True)

        # 清理多余空白
        plain_text = self._clean_whitespace(plain_text)

        return cleaned_html, plain_text

    def extract_by_selector(
        self,
        html: str,
        selector: str,
        base_url: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """
        根据选择器提取元素

        Args:
            html: HTML 内容
            selector: CSS 选择器
            base_url: 基础 URL

        Returns:
            提取的元素列表
        """
        soup = BeautifulSoup(html, "lxml")
        elements = soup.select(selector)

        results = []
        for elem in elements:
            item = {
                "html": str(elem),
                "text": elem.get_text(strip=True),
            }

            # 提取链接
            link = elem.find("a")
            if link and link.get("href"):
                href = link.get("href")
                if base_url:
                    href = urljoin(base_url, href)
                item["url"] = href

            results.append(item)

        return results

    def extract_structured(
        self,
        html: str,
        selectors: dict[str, str],
        container_selector: Optional[str] = None,
        base_url: Optional[str] = None,
        url_prefix: str = "",
    ) -> list[dict[str, Any]]:
        """
        结构化提取

        Args:
            html: HTML 内容
            selectors: 字段选择器映射 {"title": "h2 a", "description": "p.desc"}
            container_selector: 容器选择器
            base_url: 基础 URL
            url_prefix: URL 前缀

        Returns:
            提取的数据列表
        """
        soup = BeautifulSoup(html, "lxml")

        if container_selector:
            containers = soup.select(container_selector)
        else:
            containers = [soup]

        results = []
        for container in containers:
            item = {}

            for field, selector in selectors.items():
                if not selector:
                    continue

                elem = container.select_one(selector)
                if not elem:
                    item[field] = None
                    continue

                # 特殊处理 URL 字段
                if field == "url":
                    href = elem.get("href", "") if elem.name == "a" else ""
                    if not href:
                        link = elem.find("a")
                        href = link.get("href", "") if link else ""

                    if href:
                        if href.startswith("/"):
                            href = url_prefix + href
                        elif base_url and not href.startswith("http"):
                            href = urljoin(base_url, href)
                    item[field] = href
                else:
                    item[field] = elem.get_text(strip=True)

            if any(item.values()):
                results.append(item)

        return results

    def extract_article(self, html: str) -> dict[str, str]:
        """
        使用 readability 提取文章正文

        Args:
            html: HTML 内容

        Returns:
            {"title": "...", "content": "...", "text": "..."}
        """
        doc = Document(html)

        title = doc.title()
        content_html = doc.summary()

        # 清洗提取的内容
        soup = BeautifulSoup(content_html, "lxml")
        text = soup.get_text(separator="\n", strip=True)
        text = self._clean_whitespace(text)

        return {
            "title": title,
            "content": content_html,
            "text": text,
        }

    def _remove_noise_elements(self, soup: BeautifulSoup) -> None:
        """移除噪声元素"""
        noise_regex = re.compile("|".join(self.NOISE_PATTERNS), re.IGNORECASE)

        for elem in soup.find_all(True):
            # 检查 class
            classes = elem.get("class", [])
            if isinstance(classes, list):
                classes = " ".join(classes)

            # 检查 id
            elem_id = elem.get("id", "")

            if noise_regex.search(classes) or noise_regex.search(elem_id):
                # 不移除主要内容区域
                if not any(x in classes.lower() for x in ["main", "content", "article", "post"]):
                    elem.decompose()

    def _convert_relative_urls(self, soup: BeautifulSoup, base_url: str) -> None:
        """转换相对 URL 为绝对 URL"""
        for tag in soup.find_all(["a", "img", "link", "script"]):
            for attr in ["href", "src"]:
                url = tag.get(attr)
                if url and not url.startswith(("http://", "https://", "data:", "#", "javascript:")):
                    tag[attr] = urljoin(base_url, url)

    def _clean_whitespace(self, text: str) -> str:
        """清理多余空白"""
        # 合并连续空行
        text = re.sub(r"\n{3,}", "\n\n", text)
        # 移除行首尾空白
        lines = [line.strip() for line in text.split("\n")]
        return "\n".join(lines)

    def extract_metadata(self, html: str) -> dict[str, str]:
        """
        提取页面元数据

        Returns:
            {"title": "...", "description": "...", "keywords": "..."}
        """
        soup = BeautifulSoup(html, "lxml")
        metadata = {}

        # 标题
        title_tag = soup.find("title")
        if title_tag:
            metadata["title"] = title_tag.get_text(strip=True)

        # Meta 标签
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
            elif property_name == "og:image":
                metadata["og_image"] = content

        return metadata
