"""
Scrapy 爬虫管理器
提供与现有 FetchManager 兼容的接口，支持异步调用
"""

import asyncio
import json
import logging
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Optional

from ..core.models import FetchResult, FetchStatus, FetchMethod, FetchPageType, FetchTask
from ..core.config import CrawlerConfig


logger = logging.getLogger(__name__)


class ScrapyFetchManager:
    """
    Scrapy 抓取管理器

    替代原有的 FetchManager，使用 Scrapy 框架进行爬取

    特点：
    1. 与现有 FetchTask/FetchResult 模型兼容
    2. 支持异步调用
    3. 自动从 YAML 配置加载解析规则
    4. 内置反爬虫策略
    """

    def __init__(
        self,
        config: CrawlerConfig,
        cache_dir: Optional[Path] = None,
        cache_enabled: bool = True,
    ):
        self.config = config
        self.cache_dir = cache_dir
        self.cache_enabled = cache_enabled

        self._results: list[FetchResult] = []
        self._articles: list[dict[str, Any]] = []

        # 统计
        self._request_count = 0
        self._success_count = 0
        self._failure_count = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def close(self) -> None:
        """关闭资源"""
        pass

    def get_stats(self) -> dict[str, int]:
        """获取统计信息"""
        return {
            "requests": self._request_count,
            "success": self._success_count,
            "failure": self._failure_count,
        }

    async def fetch(self, task: FetchTask) -> FetchResult:
        """
        执行单个抓取任务

        Args:
            task: 抓取任务

        Returns:
            FetchResult: 抓取结果
        """
        results = await self.fetch_all([task])
        return results[0] if results else self._create_failed_result(task, "No results")

    async def fetch_many(
        self,
        tasks: list[FetchTask],
    ) -> list[FetchResult]:
        """
        批量抓取（与 FetchManager.fetch_many 兼容）

        用于二次爬取详情页，优先使用 httpx，如果检测到需要 JS 则回退到 Playwright

        Args:
            tasks: 任务列表

        Returns:
            结果列表（与任务顺序对应）
        """
        import httpx

        # JS 阻挡检测关键词
        JS_BLOCK_MARKERS = [
            "enable javascript",
            "javascript is required",
            "please enable javascript",
            "javascript and cookies",
            "browser doesn't support",
            "turn on javascript",
            "requires javascript",
            "you need to enable javascript",
            "this site requires javascript",
            "please turn on javascript",
        ]

        # 已知需要 JS 的域名
        JS_REQUIRED_DOMAINS = [
            "medium.com",
            "dev.to",
            "substack.com",
            "notion.so",
            "bloomberg.com",
            "wsj.com",
            "nytimes.com",
        ]

        def needs_js_by_domain(url: str) -> bool:
            """根据域名判断是否需要 JS"""
            from urllib.parse import urlparse
            domain = urlparse(url).netloc.lower()
            return any(d in domain for d in JS_REQUIRED_DOMAINS)

        def needs_js_by_content(html: str) -> bool:
            """根据内容判断是否需要 JS"""
            if not html:
                return True
            # 内容太短通常是 JS 阻挡页
            if len(html.strip()) < 2000:
                lower_html = html.lower()
                for marker in JS_BLOCK_MARKERS:
                    if marker in lower_html:
                        return True
            return False

        async def fetch_with_playwright(url: str) -> tuple[str, int]:
            """使用 Playwright 抓取页面"""
            try:
                from playwright.async_api import async_playwright

                async with async_playwright() as p:
                    browser = await p.chromium.launch(headless=True)
                    context = await browser.new_context(
                        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    )
                    page = await context.new_page()

                    try:
                        response = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                        # 等待内容加载
                        await page.wait_for_timeout(3000)

                        html = await page.content()
                        status_code = response.status if response else 200

                        return html, status_code
                    finally:
                        await browser.close()
            except Exception as e:
                logger.warning(f"Playwright fetch failed for {url}: {e}")
                return "", 0

        results = []
        semaphore = asyncio.Semaphore(self.config.concurrency)

        async def fetch_one(task: FetchTask) -> FetchResult:
            async with semaphore:
                self._request_count += 1
                url = task.url
                html = ""
                status_code = 0
                method = FetchMethod.LIGHT

                try:
                    # 检查是否已知需要 JS 的域名
                    if needs_js_by_domain(url):
                        logger.info(f"Known JS domain, using Playwright: {url}")
                        html, status_code = await fetch_with_playwright(url)
                        method = FetchMethod.HEAVY
                    else:
                        # 先尝试 httpx
                        import httpx
                        async with httpx.AsyncClient(
                            timeout=self.config.timeout,
                            follow_redirects=True,
                            headers={
                                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                                "Accept-Language": "en-US,en;q=0.9",
                            },
                        ) as client:
                            response = await client.get(url)
                            html = response.text
                            status_code = response.status_code
                            url = str(response.url)

                        # 检查是否需要 JS 渲染
                        if needs_js_by_content(html):
                            logger.info(f"JS required by content, using Playwright: {url}")
                            html, status_code = await fetch_with_playwright(task.url)
                            method = FetchMethod.HEAVY

                    if not html:
                        self._failure_count += 1
                        return FetchResult(
                            task_id=task.id,
                            url=task.url,
                            status=FetchStatus.FAILED,
                            method=method,
                            error_message="Failed to fetch content",
                        )

                    self._success_count += 1
                    return FetchResult(
                        task_id=task.id,
                        url=url,
                        status=FetchStatus.SUCCESS,
                        method=method,
                        page_type=FetchPageType.CONTENT,
                        html=html,
                        status_code=status_code,
                    )
                except Exception as e:
                    self._failure_count += 1
                    return FetchResult(
                        task_id=task.id,
                        url=task.url,
                        status=FetchStatus.FAILED,
                        method=FetchMethod.UNKNOWN,
                        error_message=str(e),
                    )

        results = await asyncio.gather(*[fetch_one(task) for task in tasks])
        return list(results)

    async def fetch_all(self, tasks: list[FetchTask]) -> list[FetchResult]:
        """
        执行多个抓取任务

        Args:
            tasks: 抓取任务列表

        Returns:
            list[FetchResult]: 抓取结果列表
        """
        results = []

        # 按站点分组
        site_tasks: dict[str, tuple[FetchTask, dict[str, Any]]] = {}
        for task in tasks:
            site_name = task.site_name
            if site_name not in site_tasks:
                site_tasks[site_name] = (task, task.site_config)

        # 为每个站点运行 Spider
        for site_name, (task, site_config) in site_tasks.items():
            logger.info(f"Crawling {site_name}...")
            self._request_count += 1

            try:
                spider_results, articles = await self._run_spider_subprocess(
                    site_config, site_name
                )

                if spider_results:
                    result = self._convert_to_fetch_result(spider_results[0], task)
                    results.append(result)
                    self._results.append(result)
                    self._articles.extend(articles)

                    if result.status == FetchStatus.SUCCESS:
                        self._success_count += 1
                    else:
                        self._failure_count += 1
                else:
                    result = self._create_failed_result(task, "Spider returned no results")
                    results.append(result)
                    self._failure_count += 1

            except Exception as e:
                logger.error(f"Spider failed for {site_name}: {e}")
                result = self._create_failed_result(task, str(e))
                results.append(result)
                self._failure_count += 1

        return results

    async def _run_spider_subprocess(
        self,
        site_config: dict[str, Any],
        site_name: str,
    ) -> tuple[list[dict], list[dict]]:
        """
        在子进程中运行 Spider

        使用子进程可以避免 Twisted reactor 只能启动一次的问题
        """
        settings = self._get_scrapy_settings()

        # 获取项目根目录
        project_root = Path(__file__).parent.parent.parent

        # 创建 runner 脚本
        runner_script = '''
import sys
import json

# 设置路径
sys.path.insert(0, "{project_root}")

from scrapy.crawler import CrawlerProcess
from scrapy import signals
from src.scrapy_crawler.spiders.site_spider import SiteSpider

def run_spider(site_config, site_name, settings):
    results = []
    articles = []
    
    def spider_closed(spider, reason):
        nonlocal results, articles
        # 转换为可序列化的字典
        for r in getattr(spider, 'results', []):
            if hasattr(r, '__iter__'):
                results.append(dict(r))
            else:
                results.append(r)
        for a in getattr(spider, 'articles', []):
            if hasattr(a, '__iter__'):
                articles.append(dict(a))
            else:
                articles.append(a)
    
    process = CrawlerProcess(settings)
    crawler = process.create_crawler(SiteSpider)
    crawler.signals.connect(spider_closed, signal=signals.spider_closed)
    
    process.crawl(crawler, site_config=site_config, site_name=site_name)
    process.start()
    
    return results, articles

if __name__ == "__main__":
    site_config = json.loads(sys.argv[1])
    site_name = sys.argv[2]
    settings = json.loads(sys.argv[3])
    
    results, articles = run_spider(site_config, site_name, settings)
    
    # 输出结果
    output = json.dumps({{"results": results, "articles": articles}})
    print("__SCRAPY_OUTPUT_START__")
    print(output)
    print("__SCRAPY_OUTPUT_END__")
'''.format(project_root=str(project_root))

        # 写入临时文件
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.py', delete=False, encoding='utf-8'
        ) as f:
            f.write(runner_script)
            script_path = f.name

        try:
            # 运行子进程
            process = await asyncio.create_subprocess_exec(
                sys.executable,
                script_path,
                json.dumps(site_config),
                site_name,
                json.dumps(settings),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(project_root),
            )

            # 等待完成，设置超时
            timeout = self.config.timeout * 5  # 给予足够时间
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                logger.error(f"Spider timed out for {site_name}")
                return [], []

            stdout_text = stdout.decode('utf-8', errors='ignore')
            stderr_text = stderr.decode('utf-8', errors='ignore')

            # 解析输出
            if "__SCRAPY_OUTPUT_START__" in stdout_text and "__SCRAPY_OUTPUT_END__" in stdout_text:
                json_str = stdout_text.split("__SCRAPY_OUTPUT_START__")[1].split("__SCRAPY_OUTPUT_END__")[0].strip()
                data = json.loads(json_str)
                return data.get("results", []), data.get("articles", [])

            # 如果没有找到标记，记录错误
            if stderr_text:
                logger.warning(f"Spider stderr: {stderr_text[:500]}")

            logger.warning(f"Could not parse spider output for {site_name}")
            return [], []

        except Exception as e:
            logger.error(f"Spider subprocess failed: {e}")
            return [], []
        finally:
            # 清理临时文件
            try:
                os.unlink(script_path)
            except Exception:
                pass

    def _get_scrapy_settings(self) -> dict[str, Any]:
        """获取 Scrapy 设置"""
        settings = {
            "BOT_NAME": "ai_daily_digest",
            "SPIDER_MODULES": ["src.scrapy_crawler.spiders"],
            "NEWSPIDER_MODULE": "src.scrapy_crawler.spiders",
            "ROBOTSTXT_OBEY": False,
            "CONCURRENT_REQUESTS": self.config.concurrency,
            "DOWNLOAD_DELAY": 1,
            "RANDOMIZE_DOWNLOAD_DELAY": True,
            "COOKIES_ENABLED": True,
            "DOWNLOAD_TIMEOUT": self.config.timeout,
            "RETRY_ENABLED": True,
            "RETRY_TIMES": self.config.max_retries,
            "LOG_LEVEL": "WARNING",
            "LOG_ENABLED": True,
            "REQUEST_FINGERPRINTER_IMPLEMENTATION": "2.7",
        }

        if self.config.user_agents:
            settings["USER_AGENTS"] = self.config.user_agents

        return settings

    def _convert_to_fetch_result(
        self, spider_result: dict[str, Any], task: FetchTask
    ) -> FetchResult:
        """将 Spider 结果转换为 FetchResult"""
        status = spider_result.get("status", "failed")

        return FetchResult(
            task_id=task.id,
            url=spider_result.get("url", task.url),
            status=FetchStatus.SUCCESS if status == "success" else FetchStatus.FAILED,
            method=FetchMethod.CRAWL4AI,
            page_type=FetchPageType.LIST if spider_result.get("page_type") == "list" else FetchPageType.CONTENT,
            html=spider_result.get("html"),
            text=spider_result.get("text"),
            title=spider_result.get("title"),
            description=spider_result.get("description"),
            parsed_data=spider_result.get("parsed_data", {}),
            status_code=spider_result.get("status_code"),
            error_message=spider_result.get("error_message"),
        )

    def _create_failed_result(self, task: FetchTask, error: str) -> FetchResult:
        """创建失败的抓取结果"""
        return FetchResult(
            task_id=task.id,
            url=task.url,
            status=FetchStatus.FAILED,
            method=FetchMethod.UNKNOWN,
            error_message=error,
        )

    def get_articles(self) -> list[dict[str, Any]]:
        """获取所有抓取的文章"""
        return self._articles

    def get_results(self) -> list[FetchResult]:
        """获取所有抓取结果"""
        return self._results


# 为了兼容性，提供别名
ScrapyCrawlerRunner = ScrapyFetchManager

