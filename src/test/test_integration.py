"""
集成测试
测试真实站点的抓取和内容提取
"""

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.processor.content_extractor import SmartContentExtractor


# 模拟的 HTML 内容用于测试
MOCK_GITHUB_TRENDING_HTML = """
<!DOCTYPE html>
<html>
<head><title>Trending repositories on GitHub today</title></head>
<body>
<main>
    <article class="Box-row">
        <h2 class="h3">
            <a href="/microsoft/vscode">microsoft / <span>vscode</span></a>
        </h2>
        <p class="col-9">Visual Studio Code</p>
        <span class="d-inline-block ml-0 mr-3">
            <span itemprop="programmingLanguage">TypeScript</span>
        </span>
    </article>
    <article class="Box-row">
        <h2 class="h3">
            <a href="/facebook/react">facebook / <span>react</span></a>
        </h2>
        <p class="col-9">A declarative, efficient, and flexible JavaScript library</p>
        <span class="d-inline-block ml-0 mr-3">
            <span itemprop="programmingLanguage">JavaScript</span>
        </span>
    </article>
    <article class="Box-row">
        <h2 class="h3">
            <a href="/rust-lang/rust">rust-lang / <span>rust</span></a>
        </h2>
        <p class="col-9">Empowering everyone to build reliable and efficient software.</p>
        <span class="d-inline-block ml-0 mr-3">
            <span itemprop="programmingLanguage">Rust</span>
        </span>
    </article>
</main>
</body>
</html>
"""

MOCK_HACKERNEWS_HTML = """
<!DOCTYPE html>
<html>
<head><title>Best | Hacker News</title></head>
<body>
<table>
    <tr class="athing" id="123">
        <td class="title">
            <span class="titleline">
                <a href="https://example.com/story1">Amazing new technology discovered</a>
            </span>
        </td>
    </tr>
    <tr class="athing" id="124">
        <td class="title">
            <span class="titleline">
                <a href="https://example.com/story2">Breaking: Major announcement</a>
            </span>
        </td>
    </tr>
    <tr class="athing" id="125">
        <td class="title">
            <span class="titleline">
                <a href="https://example.com/story3">Show HN: My new project</a>
            </span>
        </td>
    </tr>
</table>
</body>
</html>
"""

MOCK_LOBSTERS_HTML = """
<!DOCTYPE html>
<html>
<head><title>Lobsters</title></head>
<body>
<ol class="stories list">
    <li class="story">
        <div class="details">
            <span class="link"><a class="u-url" href="https://example.com/post1">Interesting Article Title</a></span>
            <span class="tags"><a class="tag" href="/t/programming">programming</a></span>
            <div class="byline">
                <a class="u-author" href="/u/user1">user1</a>
            </div>
        </div>
    </li>
    <li class="story">
        <div class="details">
            <span class="link"><a class="u-url" href="https://example.com/post2">Another Great Post</a></span>
            <span class="tags"><a class="tag" href="/t/rust">rust</a></span>
            <div class="byline">
                <a class="u-author" href="/u/user2">user2</a>
            </div>
        </div>
    </li>
    <li class="story">
        <div class="details">
            <span class="link"><a class="u-url" href="https://example.com/post3">Tech News Update</a></span>
            <span class="tags"><a class="tag" href="/t/news">news</a></span>
            <div class="byline">
                <a class="u-author" href="/u/user3">user3</a>
            </div>
        </div>
    </li>
</ol>
</body>
</html>
"""

MOCK_ARTICLE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>How to Build a Great Product</title>
    <meta name="description" content="A comprehensive guide to product development">
</head>
<body>
    <nav>Navigation Menu</nav>
    <article>
        <h1>How to Build a Great Product</h1>
        <p>Building a great product requires careful planning and execution. In this article, we'll explore the key principles that make products successful.</p>
        <h2>1. Understand Your Users</h2>
        <p>The first step in building any great product is understanding who your users are and what they need. Conduct user research, interviews, and surveys to gather insights.</p>
        <h2>2. Focus on Quality</h2>
        <p>Quality should never be compromised. A well-built product with fewer features will always outperform a buggy product with many features.</p>
        <h2>3. Iterate Quickly</h2>
        <p>Don't wait for perfection. Ship early, get feedback, and iterate. The faster you can learn from real users, the better your product will become.</p>
        <pre><code>
def build_product():
    understand_users()
    focus_on_quality()
    iterate_quickly()
        </code></pre>
    </article>
    <aside>Related Articles</aside>
    <footer>Copyright 2026</footer>
</body>
</html>
"""


class TestGitHubTrendingExtraction(unittest.TestCase):
    """GitHub Trending 提取测试"""

    def setUp(self):
        self.extractor = SmartContentExtractor()
        self.site_config = {
            "list_parser": {
                "container": "article.Box-row",
                "selectors": {
                    "title": "h2 a",
                    "url": "h2 a",
                    "description": "p.col-9",
                    "language": "span[itemprop='programmingLanguage']",
                },
                "url_prefix": "https://github.com",
            }
        }

    def test_extract_trending_repos(self):
        """测试提取 trending 仓库"""
        result = self.extractor.extract(
            MOCK_GITHUB_TRENDING_HTML,
            "https://github.com/trending",
            self.site_config,
        )

        self.assertEqual(result["page_type"], "list")
        self.assertEqual(len(result["items"]), 3)

        # 验证第一个项目
        first_item = result["items"][0]
        self.assertIn("vscode", first_item["title"])
        self.assertEqual(first_item["url"], "https://github.com/microsoft/vscode")
        self.assertIn("Visual Studio Code", first_item.get("description", ""))


class TestHackerNewsExtraction(unittest.TestCase):
    """Hacker News 提取测试"""

    def setUp(self):
        self.extractor = SmartContentExtractor()
        self.site_config = {
            "list_parser": {
                "container": "tr.athing",
                "selectors": {
                    "title": "span.titleline > a",
                    "url": "span.titleline > a",
                },
                "url_prefix": "",
            }
        }

    def test_extract_hn_stories(self):
        """测试提取 HN 故事"""
        result = self.extractor.extract(
            MOCK_HACKERNEWS_HTML,
            "https://news.ycombinator.com/best",
            self.site_config,
        )

        self.assertEqual(result["page_type"], "list")
        self.assertEqual(len(result["items"]), 3)

        # 验证提取的标题
        titles = [item["title"] for item in result["items"]]
        self.assertIn("Amazing new technology discovered", titles)
        self.assertIn("Breaking: Major announcement", titles)
        self.assertIn("Show HN: My new project", titles)


class TestLobstersExtraction(unittest.TestCase):
    """Lobsters 提取测试"""

    def setUp(self):
        self.extractor = SmartContentExtractor()
        self.site_config = {
            "list_parser": {
                "container": "ol.stories.list > li.story",
                "selectors": {
                    "title": ".details span.link a.u-url",
                    "url": ".details span.link a.u-url",
                    "tags": ".details span.tags a.tag",
                    "author": ".details .byline a.u-author",
                },
                "url_prefix": "https://lobste.rs",
            }
        }

    def test_extract_lobsters_stories(self):
        """测试提取 Lobsters 故事"""
        result = self.extractor.extract(
            MOCK_LOBSTERS_HTML,
            "https://lobste.rs/",
            self.site_config,
        )

        self.assertEqual(result["page_type"], "list")
        self.assertEqual(len(result["items"]), 3)

        # 验证提取的数据
        first_item = result["items"][0]
        self.assertEqual(first_item["title"], "Interesting Article Title")
        self.assertEqual(first_item["url"], "https://example.com/post1")


class TestArticleExtraction(unittest.TestCase):
    """文章内容提取测试"""

    def setUp(self):
        self.extractor = SmartContentExtractor()

    def test_extract_article_content(self):
        """测试提取文章内容"""
        result = self.extractor.extract(
            MOCK_ARTICLE_HTML,
            "https://example.com/article",
        )

        # 应该识别为文章
        self.assertEqual(result["page_type"], "article")

        # 验证内容提取
        self.assertIn("How to Build a Great Product", result["content"])
        self.assertIn("Understand Your Users", result["content"])
        self.assertIn("Focus on Quality", result["content"])

    def test_extract_article_metadata(self):
        """测试提取文章元数据"""
        result = self.extractor.extract(
            MOCK_ARTICLE_HTML,
            "https://example.com/article",
        )

        self.assertEqual(result["metadata"]["title"], "How to Build a Great Product")
        self.assertEqual(
            result["metadata"]["description"],
            "A comprehensive guide to product development"
        )


class TestAutoDetection(unittest.TestCase):
    """自动检测测试"""

    def setUp(self):
        self.extractor = SmartContentExtractor()

    def test_auto_detect_list_page(self):
        """测试自动检测列表页"""
        # 不提供配置，测试自动检测
        result = self.extractor.extract(
            MOCK_GITHUB_TRENDING_HTML,
            "https://github.com/trending",
        )

        # 应该能自动识别为列表页
        self.assertEqual(result["page_type"], "list")
        self.assertGreaterEqual(len(result["items"]), 1)

    def test_auto_detect_article_page(self):
        """测试自动检测文章页"""
        result = self.extractor.extract(
            MOCK_ARTICLE_HTML,
            "https://example.com/article",
        )

        self.assertEqual(result["page_type"], "article")
        self.assertTrue(len(result["content"]) > 100)


class TestMarkdownGeneration(unittest.TestCase):
    """Markdown 生成测试"""

    def setUp(self):
        self.extractor = SmartContentExtractor()

    def test_list_to_markdown(self):
        """测试列表转 Markdown"""
        result = self.extractor.extract(
            MOCK_HACKERNEWS_HTML,
            "https://news.ycombinator.com",
            {
                "list_parser": {
                    "container": "tr.athing",
                    "selectors": {
                        "title": "span.titleline > a",
                        "url": "span.titleline > a",
                    },
                }
            }
        )

        markdown = result["markdown"]

        # 验证 Markdown 格式
        self.assertIn("1.", markdown)  # 有序列表
        self.assertIn("[", markdown)   # 链接格式
        self.assertIn("](", markdown)  # 链接格式

    def test_article_to_markdown(self):
        """测试文章转 Markdown"""
        result = self.extractor.extract(
            MOCK_ARTICLE_HTML,
            "https://example.com/article",
        )

        markdown = result["markdown"]

        # 验证 Markdown 内容
        self.assertTrue(len(markdown) > 0)


class TestEdgeCases(unittest.TestCase):
    """边缘情况测试"""

    def setUp(self):
        self.extractor = SmartContentExtractor()

    def test_malformed_html(self):
        """测试畸形 HTML"""
        html = "<html><body><p>Unclosed tag<div>Content</body></html>"
        result = self.extractor.extract(html, "https://example.com")

        # 不应该崩溃
        self.assertIsNotNone(result)
        self.assertIn("page_type", result)

    def test_empty_containers(self):
        """测试空容器"""
        html = """
        <html><body>
            <article class="post"></article>
            <article class="post"></article>
        </body></html>
        """
        result = self.extractor.extract(html, "https://example.com")

        # 不应该崩溃
        self.assertIsNotNone(result)

    def test_unicode_content(self):
        """测试 Unicode 内容"""
        html = """
        <html><head><title>中文标题</title></head>
        <body>
            <article>
                <h1>测试文章</h1>
                <p>这是中文内容 🎉 with emoji</p>
            </article>
        </body></html>
        """

        result = self.extractor.extract(html, "https://example.com")

        self.assertIn("中文标题", result["metadata"]["title"])

    def test_deeply_nested_content(self):
        """测试深度嵌套内容"""
        html = """
        <html><body>
            <div><div><div><div><div>
                <article>
                    <h1>Nested Title</h1>
                    <p>Nested content</p>
                </article>
            </div></div></div></div></div>
        </body></html>
        """

        result = self.extractor.extract(html, "https://example.com")

        # 应该能提取到内容
        self.assertIsNotNone(result)


if __name__ == "__main__":
    unittest.main()



