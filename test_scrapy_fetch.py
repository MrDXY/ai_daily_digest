#!/usr/bin/env python3
"""
快速测试 Scrapy 爬虫实际抓取能力
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


async def test_scrapy_fetch():
    """测试 Scrapy 实际抓取"""
    print("=" * 60)
    print("Testing Scrapy Real Fetch")
    print("=" * 60)

    from src.scrapy_crawler import ScrapyFetchManager
    from src.core.config import CrawlerConfig
    from src.core.models import FetchTask

    # 简单的测试配置 - 使用 Lobsters (更简单的页面)
    site_config = {
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
            "container": "ol.stories li.story",
            "selectors": {
                "title": ".link a.u-url",
                "url": ".link a.u-url",
            },
            "url_prefix": "",
        },
        "detail_parser": {
            "enabled": False,  # 不抓取详情页，加快速度
        },
    }

    task = FetchTask(
        id="test_lobsters",
        url="https://lobste.rs/",
        site_name="Lobsters",
        site_config=site_config,
    )

    config = CrawlerConfig(
        backend="scrapy",
        timeout=30,
        concurrency=3,
        max_retries=2,
    )

    print(f"\nFetching: {task.url}")
    print("-" * 60)

    async with ScrapyFetchManager(config) as manager:
        result = await manager.fetch(task)

        print(f"Status: {result.status}")
        print(f"Status Code: {result.status_code}")
        print(f"Page Type: {result.page_type}")

        if result.html:
            print(f"HTML Length: {len(result.html)} chars")

        if result.parsed_data:
            items = result.parsed_data.get("items", [])
            print(f"Parsed Items: {len(items)}")

            if items:
                print("\nFirst 3 items:")
                for i, item in enumerate(items[:3]):
                    print(f"  {i+1}. {item.get('title', 'N/A')[:50]}")
                    print(f"     URL: {item.get('url', 'N/A')[:60]}")

        if result.error_message:
            print(f"Error: {result.error_message}")

        # 获取文章
        articles = manager.get_articles()
        print(f"\nArticles collected: {len(articles)}")

        stats = manager.get_stats()
        print(f"Stats: {stats}")

    print("\n" + "=" * 60)
    # status 可能是枚举或字符串
    status_val = result.status.value if hasattr(result.status, 'value') else result.status
    return status_val == "success"


if __name__ == "__main__":
    success = asyncio.run(test_scrapy_fetch())
    print(f"\nTest {'PASSED' if success else 'FAILED'}")
    sys.exit(0 if success else 1)


