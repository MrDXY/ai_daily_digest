#!/usr/bin/env python3
"""
测试 Scrapy 爬虫模块

Usage:
    python test_scrapy_crawler.py
    python test_scrapy_crawler.py --backend scrapy
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


async def test_scrapy_import():
    """测试 Scrapy 模块导入"""
    print("Testing Scrapy imports...")

    try:
        import scrapy
        print(f"  ✓ Scrapy version: {scrapy.__version__}")
    except ImportError as e:
        print(f"  ✗ Failed to import scrapy: {e}")
        return False

    try:
        from src.scrapy_crawler import ScrapyFetchManager, ArticleItem
        print("  ✓ ScrapyFetchManager imported")
        print("  ✓ ArticleItem imported")
    except ImportError as e:
        print(f"  ✗ Failed to import scrapy_crawler: {e}")
        return False

    try:
        from src.scrapy_crawler.spiders import BaseSiteSpider, SiteSpider
        print("  ✓ BaseSiteSpider imported")
        print("  ✓ SiteSpider imported")
    except ImportError as e:
        print(f"  ✗ Failed to import spiders: {e}")
        return False

    return True


async def test_scrapy_config():
    """测试配置加载"""
    print("\nTesting configuration...")

    try:
        from src.core.config import load_config, CrawlerConfig

        # 测试 backend 配置选项
        config = CrawlerConfig()
        print(f"  ✓ Default backend: {config.backend}")

        config = CrawlerConfig(backend="scrapy")
        print(f"  ✓ Scrapy backend: {config.backend}")

        return True
    except Exception as e:
        print(f"  ✗ Configuration test failed: {e}")
        return False


async def test_spider_creation():
    """测试 Spider 创建"""
    print("\nTesting Spider creation...")

    try:
        from src.scrapy_crawler.spiders.site_spider import SiteSpider

        # 测试配置
        site_config = {
            "site": {
                "name": "Test Site",
                "url": "https://example.com",
                "type": "structured",
            },
            "list_parser": {
                "container": "article",
                "selectors": {
                    "title": "h2",
                    "url": "a",
                },
            },
        }

        spider = SiteSpider(site_config=site_config, site_name="Test Site")
        print(f"  ✓ Spider created: {spider.name}")
        print(f"  ✓ Site name: {spider.site_name}")
        print(f"  ✓ Start URL: {spider.start_url}")

        return True
    except Exception as e:
        print(f"  ✗ Spider creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_fetch_manager():
    """测试 FetchManager 创建"""
    print("\nTesting ScrapyFetchManager...")

    try:
        from src.scrapy_crawler import ScrapyFetchManager
        from src.core.config import CrawlerConfig

        config = CrawlerConfig(backend="scrapy")

        async with ScrapyFetchManager(config) as manager:
            print("  ✓ ScrapyFetchManager created")
            stats = manager.get_stats()
            print(f"  ✓ Initial stats: {stats}")

        return True
    except Exception as e:
        print(f"  ✗ FetchManager test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """运行所有测试"""
    print("=" * 50)
    print("Scrapy Crawler Module Tests")
    print("=" * 50)

    results = []

    results.append(await test_scrapy_import())
    results.append(await test_scrapy_config())
    results.append(await test_spider_creation())
    results.append(await test_fetch_manager())

    print("\n" + "=" * 50)
    passed = sum(results)
    total = len(results)

    if passed == total:
        print(f"All tests passed! ({passed}/{total})")
        return 0
    else:
        print(f"Some tests failed: {passed}/{total}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

