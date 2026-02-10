"""
重量级抓取器
使用 Playwright + playwright-stealth 实现完整浏览器渲染
"""

import asyncio
import time
from typing import Any, Optional

from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from playwright_stealth.stealth import Stealth

from ..core.models import FetchTask, FetchResult, FetchMethod
from ..core.exceptions import FetchException
from .base import BaseFetcher


class HeavyFetcher(BaseFetcher):
    """
    重量级抓取器

    特点：
    - 基于 Playwright，完整浏览器渲染
    - 支持 JavaScript 执行
    - 使用 stealth 插件绕过检测
    - 资源占用较高，速度较慢
    """

    def __init__(self, config: Optional[dict[str, Any]] = None):
        super().__init__(config)
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None

        # Playwright 配置
        pw_config = self.config.get("playwright", {})
        self._headless = pw_config.get("headless", True)
        self._slow_mo = pw_config.get("slow_mo", 100)

    @property
    def method(self) -> FetchMethod:
        return FetchMethod.HEAVY

    async def _ensure_browser(self) -> Browser:
        """确保浏览器已启动"""
        if self._browser is None:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=self._headless,
                slow_mo=self._slow_mo,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-web-security",
                    "--disable-features=IsolateOrigins,site-per-process",
                ]
            )
        return self._browser

    async def _create_context(self) -> BrowserContext:
        """创建浏览器上下文"""
        browser = await self._ensure_browser()

        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=self._get_user_agent(),
            locale="en-US",
            timezone_id="America/New_York",
            # 模拟真实浏览器特征
            java_script_enabled=True,
            ignore_https_errors=True,
        )

        return context

    async def fetch(self, task: FetchTask) -> FetchResult:
        """
        执行重量级抓取

        Args:
            task: 抓取任务

        Returns:
            FetchResult: 抓取结果
        """
        start_time = time.time()
        context: Optional[BrowserContext] = None
        page: Optional[Page] = None

        try:
            # 创建上下文和页面
            context = await self._create_context()
            page = await context.new_page()

            # 应用 stealth 插件
            stealth = Stealth()
            await stealth.apply_stealth_async(page)

            # 设置额外的反检测脚本
            await self._inject_anti_detection(page)

            # 获取站点配置的等待时间
            site_config = task.site_config.get("fetch", {})
            wait_for = site_config.get("wait_for", 2000)

            # 导航到目标页面
            response = await page.goto(
                task.url,
                wait_until="networkidle",
                timeout=self.timeout * 1000,
            )

            # 额外等待（确保动态内容加载）
            await page.wait_for_timeout(wait_for)

            # 检查响应状态
            status_code = response.status if response else 0

            if status_code >= 400:
                return self._create_failed_result(
                    task=task,
                    error_message=f"HTTP {status_code}",
                    status_code=status_code,
                    start_time=start_time,
                )

            # 获取渲染后的 HTML
            html = await page.content()

            # 验证内容
            if not self._is_valid_content(html):
                # 尝试等待更长时间
                await page.wait_for_timeout(3000)
                html = await page.content()

            return self._create_success_result(
                task=task,
                html=html,
                status_code=status_code,
                start_time=start_time,
            )

        except asyncio.TimeoutError:
            return self._create_failed_result(
                task=task,
                error_message="Page load timeout",
                start_time=start_time,
            )

        except Exception as e:
            return self._create_failed_result(
                task=task,
                error_message=str(e),
                start_time=start_time,
            )

        finally:
            # 清理资源
            if page:
                await page.close()
            if context:
                await context.close()

    async def _inject_anti_detection(self, page: Page) -> None:
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
        """)

    def _is_valid_content(self, html: str) -> bool:
        """验证内容有效性"""
        if not html or len(html) < 500:
            return False

        # 检测 Cloudflare 挑战页面
        cf_markers = [
            "cf-browser-verification",
            "challenge-running",
            "cf-spinner",
            "checking your browser",
        ]

        html_lower = html.lower()
        for marker in cf_markers:
            if marker in html_lower:
                return False

        return True

    async def close(self) -> None:
        """关闭浏览器"""
        if self._browser:
            await self._browser.close()
            self._browser = None

        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    async def fetch_with_interaction(
        self,
        task: FetchTask,
        interactions: list[dict[str, Any]],
    ) -> FetchResult:
        """
        带交互的抓取（如滚动、点击）

        Args:
            task: 抓取任务
            interactions: 交互指令列表
                - {"type": "scroll", "y": 1000}
                - {"type": "click", "selector": "button.load-more"}
                - {"type": "wait", "ms": 2000}

        Returns:
            FetchResult: 抓取结果
        """
        start_time = time.time()
        context: Optional[BrowserContext] = None
        page: Optional[Page] = None

        try:
            context = await self._create_context()
            page = await context.new_page()
            stealth = Stealth()
            await stealth.apply_stealth_async(page)
            await self._inject_anti_detection(page)

            response = await page.goto(
                task.url,
                wait_until="networkidle",
                timeout=self.timeout * 1000,
            )

            # 执行交互指令
            for action in interactions:
                action_type = action.get("type")

                if action_type == "scroll":
                    y = action.get("y", 1000)
                    await page.evaluate(f"window.scrollBy(0, {y})")

                elif action_type == "click":
                    selector = action.get("selector")
                    if selector:
                        try:
                            await page.click(selector, timeout=5000)
                        except:
                            pass  # 忽略点击失败

                elif action_type == "wait":
                    ms = action.get("ms", 1000)
                    await page.wait_for_timeout(ms)

                elif action_type == "scroll_to_bottom":
                    await page.evaluate("""
                        async () => {
                            await new Promise((resolve) => {
                                let totalHeight = 0;
                                const distance = 100;
                                const timer = setInterval(() => {
                                    const scrollHeight = document.body.scrollHeight;
                                    window.scrollBy(0, distance);
                                    totalHeight += distance;
                                    if(totalHeight >= scrollHeight){
                                        clearInterval(timer);
                                        resolve();
                                    }
                                }, 100);
                            });
                        }
                    """)

            html = await page.content()
            status_code = response.status if response else 0

            return self._create_success_result(
                task=task,
                html=html,
                status_code=status_code,
                start_time=start_time,
            )

        except Exception as e:
            return self._create_failed_result(
                task=task,
                error_message=str(e),
                start_time=start_time,
            )

        finally:
            if page:
                await page.close()
            if context:
                await context.close()
