"""
Scrapy 中间件
实现反爬虫策略和请求处理
"""

import logging
import random
import time
from typing import Optional, Union
from urllib.parse import urlparse

from scrapy import signals
from scrapy.crawler import Crawler
from scrapy.http import Request, Response
from scrapy.spiders import Spider
from scrapy.exceptions import IgnoreRequest


logger = logging.getLogger(__name__)


# ============================================
# 浏览器指纹配置
# ============================================

USER_AGENTS = [
    # Chrome on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    # Chrome on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    # Firefox on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
    # Safari on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    # Edge on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
]

ACCEPT_LANGUAGES = [
    "en-US,en;q=0.9",
    "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
    "en-GB,en;q=0.9,en-US;q=0.8",
    "en-US,en;q=0.5",
]

REFERER_SOURCES = [
    "https://www.google.com/",
    "https://www.bing.com/",
    "https://duckduckgo.com/",
    "",
]


class RandomUserAgentMiddleware:
    """
    随机 User-Agent 中间件
    为每个请求设置随机的 User-Agent
    """

    def __init__(self, user_agents: Optional[list[str]] = None):
        self.user_agents = user_agents or USER_AGENTS

    @classmethod
    def from_crawler(cls, crawler: Crawler):
        user_agents = crawler.settings.getlist("USER_AGENTS") or USER_AGENTS
        return cls(user_agents)

    def process_request(self, request: Request, spider: Spider) -> None:
        request.headers["User-Agent"] = random.choice(self.user_agents)


class StealthMiddleware:
    """
    隐身中间件
    添加各种 headers 来伪装成真实浏览器
    """

    # 反爬检测标记
    ANTI_BOT_MARKERS = [
        "captcha", "cf-browser-verification", "challenge-running",
        "just a moment", "checking your browser", "access denied",
        "403 forbidden", "blocked", "rate limit", "too many requests",
        "please enable javascript", "enable cookies", "unusual traffic",
        "bot detected", "automated access", "security check",
    ]

    # 内容验证模式
    CONTENT_VALIDATORS = {
        "github.com": ["repository", "trending", "stars", "forks", "commit"],
        "news.ycombinator.com": ["hacker news", "points", "comments", "submitted"],
        "lobste.rs": ["lobsters", "stories", "comments", "tags"],
    }

    def process_request(self, request: Request, spider: Spider) -> None:
        """处理请求，添加隐身 headers"""
        ua = request.headers.get("User-Agent", b"").decode("utf-8", errors="ignore")

        # 基本 headers
        request.headers.setdefault("Accept",
            "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8")
        request.headers.setdefault("Accept-Language", random.choice(ACCEPT_LANGUAGES))
        request.headers.setdefault("Accept-Encoding", "gzip, deflate, br")
        request.headers.setdefault("Connection", "keep-alive")
        request.headers.setdefault("Upgrade-Insecure-Requests", "1")

        # Sec-Fetch headers
        request.headers.setdefault("Sec-Fetch-Dest", "document")
        request.headers.setdefault("Sec-Fetch-Mode", "navigate")
        request.headers.setdefault("Sec-Fetch-Site", "none")
        request.headers.setdefault("Sec-Fetch-User", "?1")
        request.headers.setdefault("Cache-Control", "max-age=0")

        # Chrome 特有的 Sec-CH-UA headers
        if "Chrome" in ua:
            version = "120" if "120" in ua else "119"
            request.headers.setdefault("Sec-CH-UA",
                f'"Not_A Brand";v="8", "Chromium";v="{version}", "Google Chrome";v="{version}"')
            request.headers.setdefault("Sec-CH-UA-Mobile", "?0")
            platform = '"macOS"' if "Macintosh" in ua else '"Windows"'
            request.headers.setdefault("Sec-CH-UA-Platform", platform)

        # 设置 Referer
        if not request.headers.get("Referer"):
            referer = self._get_referer_for_url(request.url)
            if referer:
                request.headers["Referer"] = referer

    def process_response(
        self, request: Request, response: Response, spider: Spider
    ) -> Union[Request, Response]:
        """检查响应是否被反爬虫检测拦截"""
        if response.status in [403, 429, 503]:
            logger.warning(f"Possible anti-bot response: {response.status} for {request.url}")

        # 检查页面内容是否包含反爬标记
        body = response.text.lower() if hasattr(response, "text") else ""
        for marker in self.ANTI_BOT_MARKERS:
            if marker in body and len(body) < 5000:
                logger.warning(f"Anti-bot marker detected: '{marker}' in {request.url}")
                break

        return response

    def _get_referer_for_url(self, url: str) -> str:
        """根据 URL 生成合适的 Referer"""
        parsed = urlparse(url)
        domain = parsed.netloc

        self_referrer_domains = ["github.com", "news.ycombinator.com", "lobste.rs"]
        for d in self_referrer_domains:
            if d in domain:
                return f"{parsed.scheme}://{domain}/"

        return random.choice(REFERER_SOURCES)


class RetryWithDelayMiddleware:
    """
    带延迟的重试中间件
    在重试之前添加随机延迟
    """

    def __init__(self, delay_range: tuple[float, float] = (1, 3)):
        self.delay_range = delay_range

    @classmethod
    def from_crawler(cls, crawler: Crawler):
        settings = crawler.settings.get("CUSTOM_SETTINGS", {})
        delay_range = settings.get("request_delay_range", (1, 3))
        return cls(delay_range)

    def process_response(
        self, request: Request, response: Response, spider: Spider
    ) -> Union[Request, Response]:
        """处理响应，如果失败则添加延迟重试"""
        if response.status in [429, 503]:
            retry_times = request.meta.get("retry_times", 0)
            if retry_times < 3:
                delay = random.uniform(*self.delay_range) * (retry_times + 1)
                logger.info(f"Rate limited, waiting {delay:.1f}s before retry: {request.url}")
                time.sleep(delay)

                new_request = request.copy()
                new_request.meta["retry_times"] = retry_times + 1
                new_request.dont_filter = True
                return new_request

        return response


class PlaywrightMiddleware:
    """
    Playwright 中间件
    为需要 JS 渲染的页面使用 Playwright

    需要安装 scrapy-playwright:
    pip install scrapy-playwright
    playwright install chromium
    """

    def process_request(self, request: Request, spider: Spider) -> None:
        """检查是否需要使用 Playwright"""
        site_config = request.meta.get("site_config", {})
        fetch_config = site_config.get("fetch", {})

        if fetch_config.get("requires_js", False):
            request.meta["playwright"] = True
            request.meta["playwright_include_page"] = False

            # 等待时间
            wait_for = fetch_config.get("wait_for", 1000)
            if wait_for:
                request.meta["playwright_page_methods"] = [
                    {"method": "wait_for_timeout", "args": [wait_for]},
                ]

            # 等待特定元素
            wait_for_selector = fetch_config.get("wait_for_selector")
            if wait_for_selector:
                request.meta["playwright_page_methods"] = [
                    {"method": "wait_for_selector", "args": [wait_for_selector]},
                ]


class ScrapyStatsMiddleware:
    """
    统计中间件
    收集爬取统计信息
    """

    def __init__(self, stats):
        self.stats = stats

    @classmethod
    def from_crawler(cls, crawler: Crawler):
        middleware = cls(crawler.stats)
        crawler.signals.connect(middleware.spider_opened, signal=signals.spider_opened)
        return middleware

    def spider_opened(self, spider: Spider):
        self.stats.set_value("custom/start_time", time.time())

    def process_response(
        self, request: Request, response: Response, spider: Spider
    ) -> Response:
        """记录响应统计"""
        domain = urlparse(request.url).netloc
        self.stats.inc_value(f"custom/domain/{domain}/requests")

        if response.status == 200:
            self.stats.inc_value(f"custom/domain/{domain}/success")
        else:
            self.stats.inc_value(f"custom/domain/{domain}/failed")

        return response

