"""
动态站点 Spider
根据配置文件动态生成爬取规则
"""

import logging
from typing import Any, Optional

from .base_spider import BaseSiteSpider


logger = logging.getLogger(__name__)


class SiteSpider(BaseSiteSpider):
    """
    动态站点 Spider

    可以在运行时通过传入不同的 site_config 来爬取不同的站点
    """

    name = "site_spider"

    def __init__(
        self,
        site_config: Optional[dict[str, Any]] = None,
        site_name: Optional[str] = None,
        *args,
        **kwargs,
    ):
        # 设置 spider 名称
        if site_name:
            self.name = f"site_{site_name.lower().replace(' ', '_')}"

        super().__init__(site_config=site_config, *args, **kwargs)


class GithubTrendingSpider(BaseSiteSpider):
    """GitHub Trending 专用 Spider"""

    name = "github_trending"
    allowed_domains = ["github.com"]

    def __init__(self, site_config: Optional[dict[str, Any]] = None, *args, **kwargs):
        # 默认配置
        default_config = {
            "site": {
                "name": "GitHub Trending",
                "url": "https://github.com/trending",
                "type": "structured",
            },
            "fetch": {
                "requires_js": False,
                "wait_for": 2000,
            },
            "list_parser": {
                "container": "article.Box-row",
                "selectors": {
                    "title": "h2 a",
                    "url": "h2 a",
                    "description": "p.col-9",
                    "language": "span[itemprop='programmingLanguage']",
                    "stars": "a.Link--muted:nth-of-type(1)",
                    "forks": "a.Link--muted:nth-of-type(2)",
                    "stars_today": "span.d-inline-block.float-sm-right",
                },
                "url_prefix": "https://github.com",
            },
            "detail_parser": {
                "enabled": True,
                "max_details": 20,
            },
        }

        # 合并配置
        if site_config:
            self._merge_config(default_config, site_config)

        super().__init__(site_config=default_config, *args, **kwargs)

    def _merge_config(self, base: dict, override: dict) -> None:
        """递归合并配置"""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_config(base[key], value)
            else:
                base[key] = value


class HackerNewsSpider(BaseSiteSpider):
    """Hacker News 专用 Spider"""

    name = "hacker_news"
    allowed_domains = ["news.ycombinator.com"]

    def __init__(self, site_config: Optional[dict[str, Any]] = None, *args, **kwargs):
        default_config = {
            "site": {
                "name": "Hacker News",
                "url": "https://news.ycombinator.com/best",
                "type": "structured",
            },
            "fetch": {
                "requires_js": False,
                "wait_for": 1000,
            },
            "list_parser": {
                "container": "tr.athing",
                "selectors": {
                    "title": "span.titleline > a",
                    "url": "span.titleline > a",
                },
                "url_prefix": "",
            },
            "detail_parser": {
                "enabled": True,
                "max_details": 30,
            },
        }

        if site_config:
            self._merge_config(default_config, site_config)

        super().__init__(site_config=default_config, *args, **kwargs)

    def _merge_config(self, base: dict, override: dict) -> None:
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_config(base[key], value)
            else:
                base[key] = value


class LobstersSpider(BaseSiteSpider):
    """Lobsters 专用 Spider"""

    name = "lobsters"
    allowed_domains = ["lobste.rs"]

    def __init__(self, site_config: Optional[dict[str, Any]] = None, *args, **kwargs):
        default_config = {
            "site": {
                "name": "Lobsters",
                "url": "https://lobste.rs/",
                "type": "structured",
            },
            "fetch": {
                "requires_js": False,
                "wait_for": 500,
            },
            "list_parser": {
                "container": "ol.stories.list > li.story",
                "selectors": {
                    "title": ".details span.link a.u-url",
                    "url": ".details span.link a.u-url",
                    "tags": ".details span.tags a.tag",
                    "author": ".details .byline a.u-author",
                },
                "url_prefix": "",
            },
            "detail_parser": {
                "enabled": True,
                "max_details": 20,
            },
        }

        if site_config:
            self._merge_config(default_config, site_config)

        super().__init__(site_config=default_config, *args, **kwargs)

    def _merge_config(self, base: dict, override: dict) -> None:
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_config(base[key], value)
            else:
                base[key] = value

