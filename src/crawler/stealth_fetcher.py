"""
隐身抓取器 (Stealth Fetcher)
整合多种反爬虫技术，提供稳定可靠的页面抓取能力

特点：
1. 多层代理和请求伪装
2. 智能重试和错误恢复
3. 自动适应不同网站的反爬策略
4. 支持 Crawl4AI / Playwright / httpx 多后端
"""

import asyncio
import logging
import random
import time
from typing import Any, Optional
from urllib.parse import urlparse

import httpx

from ..core.models import FetchTask, FetchResult, FetchStatus, FetchMethod
from .base import BaseFetcher

logger = logging.getLogger(__name__)


# ============================================
# 浏览器指纹配置
# ============================================

# 常用 User-Agent 池
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

# 常用 Accept-Language
ACCEPT_LANGUAGES = [
    "en-US,en;q=0.9",
    "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
    "en-GB,en;q=0.9,en-US;q=0.8",
    "en-US,en;q=0.5",
]

# 常用 Referer 前缀
REFERER_SOURCES = [
    "https://www.google.com/",
    "https://www.bing.com/",
    "https://duckduckgo.com/",
    "",  # 直接访问
]


def _generate_fingerprint() -> dict[str, str]:
    """生成随机浏览器指纹"""
    ua = random.choice(USER_AGENTS)
    lang = random.choice(ACCEPT_LANGUAGES)

    headers = {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": lang,
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }

    # 根据 UA 添加适当的 Sec-CH-UA 头
    if "Chrome" in ua:
        version = "120" if "120" in ua else "119"
        headers["Sec-CH-UA"] = f'"Not_A Brand";v="8", "Chromium";v="{version}", "Google Chrome";v="{version}"'
        headers["Sec-CH-UA-Mobile"] = "?0"
        headers["Sec-CH-UA-Platform"] = '"macOS"' if "Macintosh" in ua else '"Windows"'

    return headers


def _get_referer_for_url(url: str) -> str:
    """根据 URL 生成合适的 Referer"""
    parsed = urlparse(url)
    domain = parsed.netloc

    # 某些站点最好使用自身域名作为 referer
    self_referrer_domains = ["github.com", "news.ycombinator.com", "lobste.rs"]

    for d in self_referrer_domains:
        if d in domain:
            return f"{parsed.scheme}://{domain}/"

    return random.choice(REFERER_SOURCES)


class StealthFetcher(BaseFetcher):
    """
    隐身抓取器

    采用多层策略确保抓取稳定性：
    1. Layer 1: Crawl4AI (内置 stealth + 浏览器渲染)
    2. Layer 2: Playwright + stealth (完整浏览器)
    3. Layer 3: httpx + 指纹伪装 (轻量级)

    每层都带有智能重试和错误检测
    """

    # 反爬检测标记
    ANTI_BOT_MARKERS = [
        # Cloudflare
        "captcha",
        "cf-browser-verification",
        "challenge-running",
        "just a moment",
        "checking your browser",
        # 通用反爬
        "access denied",
        "403 forbidden",
        "blocked",
        "rate limit",
        "too many requests",
        "please enable javascript",
        "enable cookies",
        "unusual traffic",
        "bot detected",
        "automated access",
        "security check",
        # GitHub 特定
        "you can't perform that action",
        "can't perform that action",
        "this page is taking too long to load",
        "something went wrong",
        # 通用错误页面
        "page not available",
        "service unavailable",
        "temporarily unavailable",
        "try again later",
        "we're sorry",
        "oops!",
        "error occurred",
        "request blocked",
        "forbidden",
        "unauthorized",
    ]

    # 页面内容验证模式 - 用于检测页面是否包含预期内容
    CONTENT_VALIDATORS = {
        "github.com": ["repository", "trending", "stars", "forks", "commit"],
        "news.ycombinator.com": ["hacker news", "points", "comments", "submitted"],
        "lobste.rs": ["lobsters", "stories", "comments", "tags"],
    }

    def __init__(self, config: Optional[dict[str, Any]] = None):
        super().__init__(config)
        self._httpx_client: Optional[httpx.AsyncClient] = None
        self._playwright = None
        self._browser = None

        # 配置
        fetcher_config = self.config.get("stealth", {})
        self._enable_crawl4ai = fetcher_config.get("enable_crawl4ai", True)
        self._enable_playwright = fetcher_config.get("enable_playwright", True)
        self._enable_httpx = fetcher_config.get("enable_httpx", True)
        self._request_delay = fetcher_config.get("request_delay", (1, 3))  # 随机延迟范围(秒)

        # Crawl4AI 相关
        self._crawl4ai_available = None
        self._crawl4ai_error: Optional[str] = None

    @property
    def method(self) -> FetchMethod:
        return FetchMethod.CRAWL4AI  # 主要使用 Crawl4AI

    async def _check_crawl4ai(self) -> bool:
        """检查 Crawl4AI 是否可用"""
        if self._crawl4ai_available is not None:
            return self._crawl4ai_available

        try:
            import importlib
            crawl4ai = importlib.import_module("crawl4ai")
            AsyncWebCrawler = getattr(crawl4ai, "AsyncWebCrawler", None)
            self._crawl4ai_available = AsyncWebCrawler is not None
        except Exception as e:
            self._crawl4ai_available = False
            self._crawl4ai_error = str(e)
            logger.warning(f"Crawl4AI not available: {e}")

        return self._crawl4ai_available

    async def _get_httpx_client(self) -> httpx.AsyncClient:
        """获取或创建 httpx 客户端"""
        if self._httpx_client is None:
            timeout = httpx.Timeout(self.timeout, connect=10.0)
            self._httpx_client = httpx.AsyncClient(
                timeout=timeout,
                follow_redirects=True,
                http2=True,  # 启用 HTTP/2
            )
        return self._httpx_client

    async def fetch(self, task: FetchTask) -> FetchResult:
        """
        执行抓取，使用多层回退策略
        """
        start_time = time.time()

        # 获取站点配置
        site_config = task.site_config.get("fetch", {})
        prefer_method = site_config.get("method", "auto").lower()
        requires_js = site_config.get("requires_js", False)

        # 添加随机延迟（模拟人类行为）
        if self._request_delay:
            delay = random.uniform(*self._request_delay)
            await asyncio.sleep(delay)

        # 根据配置选择抓取策略
        if prefer_method == "httpx" and self._enable_httpx:
            return await self._fetch_with_httpx(task, start_time)

        if prefer_method == "playwright" and self._enable_playwright:
            return await self._fetch_with_playwright(task, start_time)

        # 自动选择策略
        # 如果需要 JS 渲染，优先使用 Crawl4AI 或 Playwright
        if requires_js or prefer_method in ("crawl4ai", "heavy", "browser"):
            result = await self._fetch_with_crawl4ai(task, start_time)
            if result.status == FetchStatus.SUCCESS:
                return result

            # 回退到 Playwright
            if self._enable_playwright:
                result = await self._fetch_with_playwright(task, start_time)
                if result.status == FetchStatus.SUCCESS:
                    return result

            return result

        # 默认策略：先尝试 Crawl4AI，失败后回退到 httpx/Playwright
        if self._enable_crawl4ai:
            result = await self._fetch_with_crawl4ai(task, start_time)
            if result.status == FetchStatus.SUCCESS:
                return result

        # 回退到 httpx
        if self._enable_httpx:
            result = await self._fetch_with_httpx(task, start_time)
            if result.status == FetchStatus.SUCCESS:
                if not self._is_blocked_response(result.html or "", task.url):
                    return result
                logger.info(f"[{task.id}] Detected anti-bot page, falling back to browser")



        # 最后回退到 Playwright
        if self._enable_playwright:
            result = await self._fetch_with_playwright(task, start_time)
            return result

        # 所有方法都失败
        return self._create_failed_result(
            task=task,
            error_message="All fetch methods failed",
            start_time=start_time,
        )

    async def _fetch_with_httpx(self, task: FetchTask, start_time: float) -> FetchResult:
        """使用 httpx 进行轻量级抓取"""
        try:
            client = await self._get_httpx_client()
            headers = _generate_fingerprint()

            # 添加 Referer
            referer = _get_referer_for_url(task.url)
            if referer:
                headers["Referer"] = referer

            # 合并自定义头
            if task.metadata.get("headers"):
                headers.update(task.metadata["headers"])

            response = await client.get(task.url, headers=headers)

            if response.status_code >= 400:
                return self._create_failed_result(
                    task=task,
                    error_message=f"HTTP {response.status_code}",
                    status_code=response.status_code,
                    start_time=start_time,
                )

            html = response.text

            return self._create_success_result(
                task=task,
                html=html,
                status_code=response.status_code,
                start_time=start_time,
            )

        except httpx.TimeoutException:
            return self._create_failed_result(
                task=task,
                error_message="Request timeout (httpx)",
                start_time=start_time,
            )
        except Exception as e:
            return self._create_failed_result(
                task=task,
                error_message=f"httpx error: {str(e)}",
                start_time=start_time,
            )

    async def _fetch_with_crawl4ai(self, task: FetchTask, start_time: float) -> FetchResult:
        """使用 Crawl4AI 进行抓取"""
        if not await self._check_crawl4ai():
            return self._create_failed_result(
                task=task,
                error_message=f"Crawl4AI not available: {self._crawl4ai_error}",
                start_time=start_time,
            )

        try:
            import importlib
            crawl4ai = importlib.import_module("crawl4ai")
            AsyncWebCrawler = getattr(crawl4ai, "AsyncWebCrawler")
            BrowserConfig = getattr(crawl4ai, "BrowserConfig", None)
            CrawlerRunConfig = getattr(crawl4ai, "CrawlerRunConfig", None)

            # 配置浏览器
            browser_config = None
            if BrowserConfig:
                try:
                    browser_config = BrowserConfig(
                        headless=True,
                        user_agent=random.choice(USER_AGENTS),
                        viewport_width=1920,
                        viewport_height=1080,
                    )
                except Exception:
                    pass

            # 配置爬虫运行参数
            run_config = None
            if CrawlerRunConfig:
                try:
                    site_fetch_config = task.site_config.get("fetch", {})

                    # 构建配置参数
                    config_kwargs = {
                        "page_timeout": self.timeout * 1000,
                        "verbose": False,  # 减少日志输出
                    }

                    # wait_for 在 Crawl4AI 0.8+ 中是 CSS 选择器字符串，不是毫秒数
                    # 使用 delay_before_return_html 来实现等待效果
                    wait_time_ms = site_fetch_config.get("wait_for", 2000)
                    if isinstance(wait_time_ms, (int, float)):
                        # 转换为秒
                        delay_seconds = max(0.1, wait_time_ms / 1000.0)
                        config_kwargs["delay_before_return_html"] = delay_seconds

                    # wait_for_selector 如果是字符串则作为 CSS 选择器
                    wait_for_selector = site_fetch_config.get("wait_for_selector")
                    if wait_for_selector and isinstance(wait_for_selector, str):
                        config_kwargs["wait_for"] = wait_for_selector

                    run_config = CrawlerRunConfig(**config_kwargs)
                except Exception as e:
                    logger.debug(f"Failed to configure CrawlerRunConfig: {e}")
                    run_config = None

            # 创建爬虫实例
            try:
                if browser_config:
                    crawler_ctx = AsyncWebCrawler(browser_config=browser_config)
                else:
                    crawler_ctx = AsyncWebCrawler()
            except TypeError:
                crawler_ctx = AsyncWebCrawler()

            async with crawler_ctx as crawler:
                try:
                    if run_config:
                        result = await crawler.arun(url=task.url, config=run_config)
                    else:
                        result = await crawler.arun(url=task.url)
                except TypeError:
                    result = await crawler.arun(task.url)

            html = (
                getattr(result, "html", None)
                or getattr(result, "cleaned_html", None)
                or ""
            )
            text = getattr(result, "text", None)
            markdown = getattr(result, "markdown", None)
            status_code = getattr(result, "status_code", None) or 200

            if not html and not text:
                return self._create_failed_result(
                    task=task,
                    error_message="Empty content from Crawl4AI",
                    status_code=status_code,
                    start_time=start_time,
                )

            # 检查是否是反爬页面
            if self._is_blocked_response(html, task.url):
                return self._create_failed_result(
                    task=task,
                    error_message="Blocked by anti-bot protection (Crawl4AI)",
                    status_code=status_code,
                    start_time=start_time,
                )

            # 构建额外数据
            parsed_data = self._build_parsed_data(task)
            parsed_data["crawl4ai"] = {
                "markdown": markdown,
                "text": text,
                "cleaned_html": getattr(result, "cleaned_html", None),
                "links": getattr(result, "links", None),
                "title": getattr(result, "title", None),
            }

            return self._create_success_result(
                task=task,
                html=html,
                status_code=status_code,
                start_time=start_time,
                parsed_data=parsed_data,
                text=text,
            )

        except Exception as e:
            logger.exception(f"[{task.id}] Crawl4AI fetch failed")
            return self._create_failed_result(
                task=task,
                error_message=f"Crawl4AI error: {str(e)}",
                start_time=start_time,
            )

    async def _fetch_with_playwright(self, task: FetchTask, start_time: float) -> FetchResult:
        """使用 Playwright 进行完整浏览器渲染抓取"""
        try:
            from playwright.async_api import async_playwright

            try:
                from playwright_stealth import stealth_async
            except ImportError:
                from playwright_stealth import Stealth
                async def stealth_async(page):
                    await Stealth().apply_stealth_async(page)

            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--disable-dev-shm-usage",
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-web-security",
                        "--disable-features=IsolateOrigins,site-per-process",
                    ]
                )

                context = await browser.new_context(
                    viewport={"width": 1920, "height": 1080},
                    user_agent=random.choice(USER_AGENTS),
                    locale="en-US",
                    timezone_id="America/New_York",
                    java_script_enabled=True,
                    ignore_https_errors=True,
                )

                page = await context.new_page()

                # 应用 stealth
                await stealth_async(page)

                # 注入反检测脚本
                await self._inject_anti_detection(page)

                # 获取等待时间配置
                site_fetch_config = task.site_config.get("fetch", {})
                wait_for = site_fetch_config.get("wait_for", 2000)

                # 导航到页面
                response = await page.goto(
                    task.url,
                    wait_until="domcontentloaded",
                    timeout=self.timeout * 1000,
                )

                # 等待页面加载
                await page.wait_for_timeout(wait_for)

                status_code = response.status if response else 0

                if status_code >= 400:
                    await browser.close()
                    return self._create_failed_result(
                        task=task,
                        error_message=f"HTTP {status_code}",
                        status_code=status_code,
                        start_time=start_time,
                    )

                html = await page.content()

                # 检查是否是反爬页面
                if self._is_blocked_response(html, task.url):
                    # 等待更长时间
                    await page.wait_for_timeout(3000)
                    html = await page.content()

                await browser.close()

                if self._is_blocked_response(html, task.url):
                    return self._create_failed_result(
                        task=task,
                        error_message="Blocked by anti-bot protection (Playwright)",
                        status_code=status_code,
                        start_time=start_time,
                    )

                return self._create_success_result(
                    task=task,
                    html=html,
                    status_code=status_code,
                    start_time=start_time,
                )

        except Exception as e:
            logger.exception(f"[{task.id}] Playwright fetch failed")
            return self._create_failed_result(
                task=task,
                error_message=f"Playwright error: {str(e)}",
                start_time=start_time,
            )

    async def _inject_anti_detection(self, page) -> None:
        """注入反检测脚本"""
        await page.add_init_script("""
            // 覆盖 webdriver 检测
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            
            // 覆盖 chrome 检测
            window.chrome = {
                runtime: {}
            };
            
            // 覆盖 permissions 检测
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
            
            // 覆盖 plugins 检测
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            
            // 覆盖 languages 检测
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });
            
            // 覆盖 platform 检测
            Object.defineProperty(navigator, 'platform', {
                get: () => 'MacIntel'
            });
        """)

    def _is_blocked_response(self, html: str, url: str = "") -> bool:
        """
        检测是否是反爬虫页面

        Args:
            html: 页面 HTML 内容
            url: 页面 URL（用于站点特定验证）

        Returns:
            True 如果检测到反爬页面
        """
        if not html:
            return True

        # 页面太短通常是错误页面
        if len(html) < 500:
            logger.debug(f"Page too short ({len(html)} chars), likely blocked")
            return True

        html_lower = html.lower()

        # 检查反爬标记
        for marker in self.ANTI_BOT_MARKERS:
            if marker in html_lower:
                # 对于短页面，更可能是反爬页面
                if len(html) < 15000:
                    logger.debug(f"Anti-bot marker found: '{marker}'")
                    return True

        # 站点特定内容验证
        if url:
            domain = urlparse(url).netloc
            for site_domain, validators in self.CONTENT_VALIDATORS.items():
                if site_domain in domain:
                    # 检查是否包含预期内容标记
                    found_any = any(v in html_lower for v in validators)
                    if not found_any and len(html) < 20000:
                        logger.debug(f"Expected content markers not found for {site_domain}")
                        return True
                    break

        return False

    async def close(self) -> None:
        """关闭资源"""
        if self._httpx_client:
            await self._httpx_client.aclose()
            self._httpx_client = None


class StealthFetcherPool:
    """
    抓取器池

    管理多个抓取器实例，提供负载均衡和故障恢复
    """

    def __init__(self, config: dict[str, Any], pool_size: int = 3):
        self.config = config
        self.pool_size = pool_size
        self._fetchers: list[StealthFetcher] = []
        self._current_index = 0
        self._lock = asyncio.Lock()

    async def __aenter__(self):
        for _ in range(self.pool_size):
            fetcher = StealthFetcher(self.config)
            self._fetchers.append(fetcher)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        for fetcher in self._fetchers:
            await fetcher.close()
        self._fetchers.clear()

    async def get_fetcher(self) -> StealthFetcher:
        """获取一个抓取器（轮询）"""
        async with self._lock:
            fetcher = self._fetchers[self._current_index]
            self._current_index = (self._current_index + 1) % self.pool_size
            return fetcher

    async def fetch(self, task: FetchTask) -> FetchResult:
        """执行抓取"""
        fetcher = await self.get_fetcher()
        return await fetcher.fetch(task)


