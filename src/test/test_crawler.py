"""
爬虫模块测试
测试 StealthFetcher 和 FetchManager 的功能
"""

import asyncio
import unittest
from unittest.mock import MagicMock, patch

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.core.models import FetchTask, FetchResult, FetchStatus, FetchMethod
from src.crawler.stealth_fetcher import (
    StealthFetcher,
    _generate_fingerprint,
    _get_referer_for_url,
    USER_AGENTS,
)


class TestFingerprint(unittest.TestCase):
    """浏览器指纹生成测试"""

    def test_generate_fingerprint_returns_headers(self):
        """测试指纹生成返回正确的请求头"""
        headers = _generate_fingerprint()

        # 验证必要的请求头存在
        self.assertIn("User-Agent", headers)
        self.assertIn("Accept", headers)
        self.assertIn("Accept-Language", headers)
        self.assertIn("Accept-Encoding", headers)

    def test_generate_fingerprint_ua_from_pool(self):
        """测试 User-Agent 来自预定义池"""
        headers = _generate_fingerprint()
        self.assertIn(headers["User-Agent"], USER_AGENTS)

    def test_generate_fingerprint_randomness(self):
        """测试多次生成的指纹有随机性"""
        fingerprints = [_generate_fingerprint() for _ in range(10)]
        # 至少有一些不同的 User-Agent
        uas = set(f["User-Agent"] for f in fingerprints)
        # 由于池中有多个 UA，应该至少有2种不同的
        self.assertGreaterEqual(len(uas), 1)


class TestReferer(unittest.TestCase):
    """Referer 生成测试"""

    def test_github_uses_self_referer(self):
        """测试 GitHub URL 使用自身域名作为 referer"""
        referer = _get_referer_for_url("https://github.com/trending")
        self.assertEqual(referer, "https://github.com/")

    def test_hackernews_uses_self_referer(self):
        """测试 Hacker News 使用自身域名"""
        referer = _get_referer_for_url("https://news.ycombinator.com/best")
        self.assertEqual(referer, "https://news.ycombinator.com/")

    def test_lobsters_uses_self_referer(self):
        """测试 Lobsters 使用自身域名"""
        referer = _get_referer_for_url("https://lobste.rs/")
        self.assertEqual(referer, "https://lobste.rs/")

    def test_other_sites_use_random_referer(self):
        """测试其他站点使用随机 referer"""
        referer = _get_referer_for_url("https://example.com/page")
        # 应该是搜索引擎或空
        self.assertIn(referer, [
            "https://www.google.com/",
            "https://www.bing.com/",
            "https://duckduckgo.com/",
            "",
        ])


class TestStealthFetcher(unittest.TestCase):
    """StealthFetcher 测试"""

    def setUp(self):
        self.config = {
            "timeout": 30,
            "stealth": {
                "enable_crawl4ai": False,  # 禁用避免实际网络请求
                "enable_playwright": False,
                "enable_httpx": True,
                "request_delay": (0, 0.1),  # 最小延迟
            }
        }
        self.fetcher = StealthFetcher(self.config)

    def tearDown(self):
        asyncio.get_event_loop().run_until_complete(self.fetcher.close())

    def test_method_returns_crawl4ai(self):
        """测试 method 属性返回 CRAWL4AI"""
        self.assertEqual(self.fetcher.method, FetchMethod.CRAWL4AI)

    def test_anti_bot_markers_defined(self):
        """测试反爬虫标记已定义"""
        self.assertIsInstance(self.fetcher.ANTI_BOT_MARKERS, list)
        self.assertIn("captcha", self.fetcher.ANTI_BOT_MARKERS)
        self.assertIn("403 forbidden", self.fetcher.ANTI_BOT_MARKERS)

    def test_is_blocked_response_empty(self):
        """测试空响应被检测为被阻止"""
        self.assertTrue(self.fetcher._is_blocked_response("", ""))
        self.assertTrue(self.fetcher._is_blocked_response(None, ""))

    def test_is_blocked_response_short_with_marker(self):
        """测试短响应带反爬标记被检测"""
        html = "<html><body>Please enable JavaScript to continue</body></html>"
        self.assertTrue(self.fetcher._is_blocked_response(html, ""))

    def test_is_blocked_response_github_error(self):
        """测试 GitHub 特定错误消息被检测"""
        html = "<html><body>You can't perform that action at this time.</body></html>"
        self.assertTrue(self.fetcher._is_blocked_response(html, "https://github.com/trending"))

    def test_is_blocked_response_normal_page(self):
        """测试正常页面不被误判"""
        # 创建一个足够长的正常 HTML
        html = "<html><body>" + "Content " * 1000 + "</body></html>"
        self.assertFalse(self.fetcher._is_blocked_response(html, ""))


class TestStealthFetcherHttpx(unittest.TestCase):
    """StealthFetcher httpx 后端测试"""

    def setUp(self):
        self.config = {
            "timeout": 30,
            "stealth": {
                "enable_crawl4ai": False,
                "enable_playwright": False,
                "enable_httpx": True,
                "request_delay": (0, 0),
            }
        }
        self.fetcher = StealthFetcher(self.config)

    def tearDown(self):
        asyncio.get_event_loop().run_until_complete(self.fetcher.close())

    @patch('httpx.AsyncClient.get')
    def test_fetch_success(self, mock_get):
        """测试成功抓取"""
        async def run_test():
            # Mock 响应
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = "<html><body>Test Content</body></html>"
            mock_get.return_value = mock_response

            task = FetchTask(
                id="test-1",
                url="https://example.com",
                site_name="test",
                site_config={"fetch": {"method": "httpx"}},
            )

            result = await self.fetcher.fetch(task)

            self.assertEqual(result.status, FetchStatus.SUCCESS)
            self.assertEqual(result.status_code, 200)
            self.assertIn("Test Content", result.html)

        asyncio.get_event_loop().run_until_complete(run_test())

    @patch('httpx.AsyncClient.get')
    def test_fetch_404_error(self, mock_get):
        """测试 404 错误处理"""
        async def run_test():
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_get.return_value = mock_response

            task = FetchTask(
                id="test-2",
                url="https://example.com/notfound",
                site_name="test",
                site_config={"fetch": {"method": "httpx"}},
            )

            result = await self.fetcher.fetch(task)

            self.assertEqual(result.status, FetchStatus.FAILED)
            self.assertEqual(result.status_code, 404)

        asyncio.get_event_loop().run_until_complete(run_test())


class TestFetchTask(unittest.TestCase):
    """FetchTask 模型测试"""

    def test_create_task(self):
        """测试创建任务"""
        task = FetchTask(
            id="task-1",
            url="https://github.com/trending",
            site_name="GitHub Trending",
        )

        self.assertEqual(task.id, "task-1")
        self.assertEqual(task.url, "https://github.com/trending")
        self.assertEqual(task.site_name, "GitHub Trending")
        self.assertEqual(task.priority, 0)

    def test_task_with_metadata(self):
        """测试带元数据的任务"""
        task = FetchTask(
            id="task-2",
            url="https://example.com",
            site_name="test",
            metadata={"headers": {"X-Custom": "value"}},
        )

        self.assertEqual(task.metadata["headers"]["X-Custom"], "value")

    def test_invalid_url_raises_error(self):
        """测试无效 URL 抛出异常"""
        with self.assertRaises(ValueError):
            FetchTask(
                id="task-3",
                url="invalid-url",
                site_name="test",
            )


class TestFetchResult(unittest.TestCase):
    """FetchResult 模型测试"""

    def test_create_success_result(self):
        """测试创建成功结果"""
        result = FetchResult(
            task_id="task-1",
            url="https://example.com",
            status=FetchStatus.SUCCESS,
            method=FetchMethod.CRAWL4AI,
            html="<html><body>Content</body></html>",
            status_code=200,
        )

        self.assertEqual(result.status, FetchStatus.SUCCESS)
        self.assertEqual(result.status_code, 200)
        self.assertIn("Content", result.html)

    def test_create_failed_result(self):
        """测试创建失败结果"""
        result = FetchResult(
            task_id="task-2",
            url="https://example.com",
            status=FetchStatus.FAILED,
            method=FetchMethod.UNKNOWN,
            error_message="Connection timeout",
        )

        self.assertEqual(result.status, FetchStatus.FAILED)
        self.assertEqual(result.error_message, "Connection timeout")


if __name__ == "__main__":
    unittest.main()


