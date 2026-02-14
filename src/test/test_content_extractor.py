"""
内容提取器测试
测试 SmartContentExtractor 的功能
"""

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.processor.content_extractor import (
    SmartContentExtractor,
    extract_content,
    extract_article,
)


class TestSmartContentExtractor(unittest.TestCase):
    """SmartContentExtractor 测试"""

    def setUp(self):
        self.extractor = SmartContentExtractor()

    def test_extract_empty_html(self):
        """测试空 HTML 返回空结果"""
        result = self.extractor.extract("", "https://example.com")

        self.assertEqual(result["page_type"], "unknown")
        self.assertEqual(result["items"], [])
        self.assertEqual(result["content"], "")

    def test_extract_simple_article(self):
        """测试简单文章提取"""
        html = """
        <!DOCTYPE html>
        <html>
        <head><title>Test Article</title></head>
        <body>
            <article>
                <h1>Hello World</h1>
                <p>This is a test article with some content that should be extracted by the readability algorithm.</p>
                <p>It has multiple paragraphs to make it look like a real article.</p>
            </article>
        </body>
        </html>
        """

        result = self.extractor.extract(html, "https://example.com")

        # 应该识别为文章页面
        self.assertIn(result["page_type"], ["article", "list"])
        self.assertIn("title", result["metadata"])

    def test_extract_list_page(self):
        """测试列表页提取"""
        html = """
        <!DOCTYPE html>
        <html>
        <head><title>News List</title></head>
        <body>
            <article class="post">
                <h2><a href="/post/1">First Post</a></h2>
                <p class="description">Description of first post</p>
            </article>
            <article class="post">
                <h2><a href="/post/2">Second Post</a></h2>
                <p class="description">Description of second post</p>
            </article>
            <article class="post">
                <h2><a href="/post/3">Third Post</a></h2>
                <p class="description">Description of third post</p>
            </article>
            <article class="post">
                <h2><a href="/post/4">Fourth Post</a></h2>
                <p class="description">Description of fourth post</p>
            </article>
        </body>
        </html>
        """

        result = self.extractor.extract(html, "https://example.com")

        # 应该识别为列表页面
        self.assertEqual(result["page_type"], "list")
        self.assertGreaterEqual(len(result["items"]), 3)

        # 验证提取的条目
        for item in result["items"]:
            self.assertIn("title", item)
            self.assertIn("url", item)

    def test_extract_with_config(self):
        """测试使用配置提取"""
        html = """
        <html>
        <body>
            <div class="story">
                <span class="title"><a href="/s/1">Story 1</a></span>
            </div>
            <div class="story">
                <span class="title"><a href="/s/2">Story 2</a></span>
            </div>
            <div class="story">
                <span class="title"><a href="/s/3">Story 3</a></span>
            </div>
        </body>
        </html>
        """

        site_config = {
            "list_parser": {
                "container": "div.story",
                "selectors": {
                    "title": "span.title a",
                    "url": "span.title a",
                },
                "url_prefix": "https://example.com",
            }
        }

        result = self.extractor.extract(html, "https://example.com", site_config)

        self.assertEqual(result["page_type"], "list")
        self.assertEqual(len(result["items"]), 3)

        # 验证 URL 前缀
        for item in result["items"]:
            self.assertTrue(item["url"].startswith("https://example.com"))


class TestExtractList(unittest.TestCase):
    """extract_list 方法测试"""

    def setUp(self):
        self.extractor = SmartContentExtractor()

    def test_extract_github_trending_style(self):
        """测试 GitHub Trending 风格的列表"""
        html = """
        <html>
        <body>
            <article class="Box-row">
                <h2><a href="/user/repo1">user / repo1</a></h2>
                <p class="col-9">A cool project description</p>
            </article>
            <article class="Box-row">
                <h2><a href="/user/repo2">user / repo2</a></h2>
                <p class="col-9">Another project</p>
            </article>
        </body>
        </html>
        """

        items = self.extractor.extract_list(
            html,
            "https://github.com/trending",
            "article.Box-row",
            {"title": "h2 a", "url": "h2 a", "description": "p.col-9"},
            "https://github.com",
        )

        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["title"], "user / repo1")
        self.assertEqual(items[0]["url"], "https://github.com/user/repo1")

    def test_extract_hackernews_style(self):
        """测试 Hacker News 风格的列表"""
        html = """
        <html>
        <body>
            <tr class="athing">
                <td><span class="titleline"><a href="https://example.com/1">HN Story 1</a></span></td>
            </tr>
            <tr class="athing">
                <td><span class="titleline"><a href="https://example.com/2">HN Story 2</a></span></td>
            </tr>
        </body>
        </html>
        """

        items = self.extractor.extract_list(
            html,
            "https://news.ycombinator.com",
            "tr.athing",
            {"title": "span.titleline > a", "url": "span.titleline > a"},
            "",
        )

        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["title"], "HN Story 1")
        self.assertEqual(items[0]["url"], "https://example.com/1")


class TestExtractArticle(unittest.TestCase):
    """extract_article 方法测试"""

    def setUp(self):
        self.extractor = SmartContentExtractor()

    def test_extract_basic_article(self):
        """测试基本文章提取"""
        html = """
        <!DOCTYPE html>
        <html>
        <head><title>Test Article Title</title></head>
        <body>
            <article>
                <h1>Test Article Title</h1>
                <p>This is the first paragraph of the article.</p>
                <p>This is the second paragraph with more content to make it substantial.</p>
                <p>And here is a third paragraph for good measure.</p>
            </article>
            <script>console.log('test')</script>
        </body>
        </html>
        """

        result = self.extractor.extract_article(html)

        self.assertIn("title", result)
        self.assertIn("text", result)
        self.assertIn("markdown", result)

        # 验证脚本标签被移除
        self.assertNotIn("console.log", result["text"])

    def test_extract_article_with_code(self):
        """测试带代码的文章提取"""
        html = """
        <!DOCTYPE html>
        <html>
        <head><title>Code Tutorial</title></head>
        <body>
            <article>
                <h1>Python Tutorial</h1>
                <p>Here is some code:</p>
                <pre><code>def hello():
    print("Hello, World!")</code></pre>
                <p>That was a simple function.</p>
            </article>
        </body>
        </html>
        """

        result = self.extractor.extract_article(html)

        self.assertIn("Hello, World!", result["text"])


class TestMetadataExtraction(unittest.TestCase):
    """元数据提取测试"""

    def setUp(self):
        self.extractor = SmartContentExtractor()

    def test_extract_basic_metadata(self):
        """测试基本元数据提取"""
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Page Title</title>
            <meta name="description" content="Page description">
            <meta name="keywords" content="keyword1, keyword2">
        </head>
        <body></body>
        </html>
        """

        result = self.extractor.extract(html, "https://example.com")

        self.assertEqual(result["metadata"]["title"], "Page Title")
        self.assertEqual(result["metadata"]["description"], "Page description")
        self.assertEqual(result["metadata"]["keywords"], "keyword1, keyword2")

    def test_extract_og_metadata(self):
        """测试 Open Graph 元数据提取"""
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Page Title</title>
            <meta property="og:title" content="OG Title">
            <meta property="og:description" content="OG Description">
        </head>
        <body></body>
        </html>
        """

        result = self.extractor.extract(html, "https://example.com")

        self.assertEqual(result["metadata"]["og_title"], "OG Title")
        self.assertEqual(result["metadata"]["description"], "OG Description")


class TestConvenienceFunctions(unittest.TestCase):
    """便捷函数测试"""

    def test_extract_content_function(self):
        """测试 extract_content 便捷函数"""
        html = "<html><head><title>Test</title></head><body><p>Content</p></body></html>"
        result = extract_content(html, "https://example.com")

        self.assertIn("page_type", result)
        self.assertIn("metadata", result)

    def test_extract_article_function(self):
        """测试 extract_article 便捷函数"""
        html = """
        <html>
        <head><title>Test Article</title></head>
        <body>
            <article>
                <h1>Test</h1>
                <p>Article content here.</p>
            </article>
        </body>
        </html>
        """
        result = extract_article(html)

        self.assertIn("title", result)
        self.assertIn("text", result)
        self.assertIn("markdown", result)


class TestURLNormalization(unittest.TestCase):
    """URL 规范化测试"""

    def setUp(self):
        self.extractor = SmartContentExtractor()

    def test_normalize_absolute_url(self):
        """测试绝对 URL 不变"""
        url = self.extractor._normalize_url(
            "https://example.com/page",
            "https://base.com"
        )
        self.assertEqual(url, "https://example.com/page")

    def test_normalize_relative_url(self):
        """测试相对 URL 转换"""
        url = self.extractor._normalize_url(
            "/path/to/page",
            "https://example.com"
        )
        self.assertEqual(url, "https://example.com/path/to/page")

    def test_normalize_protocol_relative_url(self):
        """测试协议相对 URL 转换"""
        url = self.extractor._normalize_url(
            "//cdn.example.com/resource",
            "https://example.com"
        )
        self.assertEqual(url, "https://cdn.example.com/resource")

    def test_normalize_empty_url(self):
        """测试空 URL 返回空字符串"""
        url = self.extractor._normalize_url("", "https://example.com")
        self.assertEqual(url, "")


class TestNoiseRemoval(unittest.TestCase):
    """噪声移除测试"""

    def setUp(self):
        self.extractor = SmartContentExtractor()

    def test_remove_script_tags(self):
        """测试移除 script 标签"""
        html = """
        <html>
        <body>
            <p>Content</p>
            <script>alert('hello')</script>
        </body>
        </html>
        """

        result = self.extractor.extract(html, "https://example.com")
        self.assertNotIn("alert", result["content"])

    def test_remove_ad_elements(self):
        """测试移除广告元素（在自动检测列表时生效）"""
        html = """
        <html>
        <body>
            <article class="post">
                <h2><a href="/1">Post 1</a></h2>
                <p class="description">Main content</p>
            </article>
            <article class="post">
                <h2><a href="/2">Post 2</a></h2>
                <p class="description">More content</p>
            </article>
            <article class="post">
                <h2><a href="/3">Post 3</a></h2>
                <p class="description">Even more content</p>
            </article>
            <div class="sidebar advertisement">Buy now!</div>
        </body>
        </html>
        """

        result = self.extractor.extract(html, "https://example.com")
        # 广告内容不应出现在 markdown 输出中
        self.assertNotIn("Buy now!", result.get("markdown", ""))


class TestHTMLToMarkdown(unittest.TestCase):
    """HTML 转 Markdown 测试"""

    def setUp(self):
        self.extractor = SmartContentExtractor()

    def test_convert_headings(self):
        """测试标题转换"""
        html = "<h1>Title</h1><h2>Subtitle</h2>"
        markdown = self.extractor._html_to_markdown(html)

        self.assertIn("# Title", markdown)
        self.assertIn("## Subtitle", markdown)

    def test_convert_links(self):
        """测试链接转换"""
        html = '<a href="https://example.com">Link Text</a>'
        markdown = self.extractor._html_to_markdown(html)

        self.assertIn("[Link Text](https://example.com)", markdown)

    def test_convert_lists(self):
        """测试列表转换"""
        html = "<ul><li>Item 1</li><li>Item 2</li></ul>"
        markdown = self.extractor._html_to_markdown(html)

        self.assertIn("- Item 1", markdown)
        self.assertIn("- Item 2", markdown)


if __name__ == "__main__":
    unittest.main()



