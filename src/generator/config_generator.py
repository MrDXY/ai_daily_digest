"""
配置生成器
根据目标页面 URL，使用 AI 生成站点配置文件

功能：
1. 爬取目标页面
2. 分析页面结构（HTML）
3. 使用 AI 生成合适的 YAML 配置
"""

import logging
import re
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import httpx
import yaml

from ..core.config import AppConfig, get_config_dir
from ..core.models import FetchTask, FetchStatus
from ..processor import AIProviderClient

logger = logging.getLogger(__name__)


# ============================================
# 配置生成 Prompt 模板
# ============================================

CONFIG_GENERATION_PROMPT = """你是一个专业的网页解析专家。请分析以下网页的 HTML 结构，并生成一个用于内容抓取的 YAML 配置文件。

## 目标 URL
{url}

## 页面 HTML（已截取关键部分）
```html
{html_snippet}
```

## 配置文件格式说明
我们需要生成一个类似以下格式的 YAML 配置：

```yaml
# 站点配置
site:
  name: "站点名称"
  url: "列表页URL"
  type: "structured"  # structured: 目录页，需要解析列表 | article: 内容页，直接爬取

# 抓取策略
fetch:
  prefer_light: true  # 是否优先使用轻量抓取
  requires_js: false  # 是否需要 JS 渲染
  wait_for: 1000      # 等待时间（毫秒）

# 列表页解析规则（仅 structured 类型需要）
list_parser:
  container: "CSS选择器"  # 每个条目的容器选择器
  selectors:
    title: "CSS选择器"      # 标题选择器（相对于 container）
    url: "CSS选择器"        # 链接选择器
    description: "CSS选择器"  # 描述选择器（可选）
    # 其他自定义字段...
  url_prefix: ""  # URL 前缀（如果链接是相对路径）

# 详情页解析配置
detail_parser:
  enabled: true  # 是否启用二次爬取详情页
  max_details: 20  # 最大详情抓取数
  # 正文提取使用 trafilatura 自动提取

# 数据清洗配置
cleaning:
  remove_tags: ["script", "style", "nav", "footer", "aside"]
  extract_text: true
```

## 任务要求
1. 分析页面结构，识别这是一个列表页（如新闻列表、项目列表）还是内容页（单篇文章）
2. 找出页面中的主要内容区域和列表项
3. 生成准确的 CSS 选择器
4. 判断是否需要 JS 渲染（如果页面内容明显是动态加载的）

## 输出要求
请直接输出完整的 YAML 配置内容，不要包含其他解释文字。配置应该可以直接保存为 .yaml 文件使用。
确保 YAML 格式正确，使用合适的缩进（2个空格）。
"""


class ConfigGenerator:
    """
    配置生成器

    根据目标 URL 自动生成站点配置文件
    """

    def __init__(self, config: AppConfig):
        """
        初始化配置生成器

        Args:
            config: 应用配置
        """
        self.config = config
        self._ai_provider: Optional[AIProviderClient] = None

    def _get_ai_provider(self) -> AIProviderClient:
        """获取 AI Provider"""
        if self._ai_provider is None:
            self._ai_provider = AIProviderClient(self.config)
        return self._ai_provider

    async def _fetch_with_httpx(self, url: str) -> str:
        """使用 httpx 抓取页面"""
        async with httpx.AsyncClient(
            timeout=self.config.crawler.timeout,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            },
        ) as client:
            response = await client.get(url)
            return response.text

    async def _fetch_with_playwright(self, url: str) -> str:
        """使用 Playwright 抓取页面"""
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(3000)
                html = await page.content()
                return html
            finally:
                await browser.close()

    async def fetch_page(self, url: str, use_js: bool = False) -> str:
        """
        抓取页面内容

        Args:
            url: 目标 URL
            use_js: 是否使用 JS 渲染

        Returns:
            HTML 内容
        """
        try:
            if use_js:
                return await self._fetch_with_playwright(url)
            else:
                return await self._fetch_with_httpx(url)
        except Exception as e:
            raise RuntimeError(f"抓取失败: {e}")

    def _extract_html_snippet(self, html: str, max_length: int = 30000) -> str:
        """
        提取 HTML 关键部分

        为了不超过 AI 的 token 限制，需要智能截取 HTML

        Args:
            html: 完整 HTML
            max_length: 最大长度

        Returns:
            截取后的 HTML
        """
        # 移除脚本和样式内容（保留标签以便分析）
        html = re.sub(r'<script[^>]*>.*?</script>', '<script></script>', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '<style></style>', html, flags=re.DOTALL | re.IGNORECASE)

        # 移除注释
        html = re.sub(r'<!--.*?-->', '', html, flags=re.DOTALL)

        # 压缩空白
        html = re.sub(r'\s+', ' ', html)
        html = re.sub(r'>\s+<', '><', html)

        if len(html) <= max_length:
            return html

        # 尝试只保留 body 内容
        body_match = re.search(r'<body[^>]*>(.*)</body>', html, re.IGNORECASE | re.DOTALL)
        if body_match:
            body_content = body_match.group(1)
            if len(body_content) <= max_length:
                return body_content
            html = body_content

        # 如果还是太长，截取前面部分
        return html[:max_length] + "\n<!-- ... 内容已截断 ... -->"

    def _extract_site_name(self, url: str, html: str) -> str:
        """
        从 URL 或 HTML 中提取站点名称

        Args:
            url: 目标 URL
            html: HTML 内容

        Returns:
            站点名称
        """
        # 尝试从 title 标签提取
        title_match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
        if title_match:
            title = title_match.group(1).strip()
            # 清理常见后缀
            title = re.sub(r'\s*[-|–—]\s*.*$', '', title)
            if title and len(title) < 50:
                return title

        # 从 URL 提取域名
        parsed = urlparse(url)
        domain = parsed.netloc.replace('www.', '')
        return domain.split('.')[0].title()

    def _generate_config_filename(self, url: str) -> str:
        """
        生成配置文件名

        Args:
            url: 目标 URL

        Returns:
            文件名（不含路径）
        """
        parsed = urlparse(url)
        domain = parsed.netloc.replace('www.', '')

        # 提取主域名
        name = domain.split('.')[0]

        # 添加路径信息（如果有）
        path = parsed.path.strip('/')
        if path:
            path_part = path.replace('/', '_').replace('-', '_')[:20]
            name = f"{name}_{path_part}"

        # 清理非法字符
        name = re.sub(r'[^\w_]', '', name)

        return f"{name.lower()}.yaml"

    async def generate_config(
        self,
        url: str,
        use_js: bool = False,
        output_path: Optional[str] = None,
    ) -> tuple[str, str]:
        """
        生成配置文件

        Args:
            url: 目标 URL
            use_js: 是否使用 JS 渲染抓取
            output_path: 输出路径（可选，默认保存到 config/sites/）

        Returns:
            (配置文件路径, 配置内容)
        """
        logger.info(f"开始为 {url} 生成配置...")

        # 1. 抓取页面
        logger.info("正在抓取页面...")
        html = await self.fetch_page(url, use_js)
        logger.info(f"抓取成功，HTML 长度: {len(html)}")

        # 2. 提取关键 HTML
        html_snippet = self._extract_html_snippet(html)
        logger.info(f"提取 HTML 片段，长度: {len(html_snippet)}")

        # 3. 调用 AI 生成配置
        logger.info("正在调用 AI 生成配置...")
        ai_provider = self._get_ai_provider()

        prompt = CONFIG_GENERATION_PROMPT.format(
            url=url,
            html_snippet=html_snippet,
        )

        system_prompt = (
            "你是一个专业的网页解析专家，擅长分析 HTML 结构并生成精确的 CSS 选择器。"
            "请直接输出 YAML 配置，不要包含 markdown 代码块标记。"
        )

        response = await ai_provider.generate_text(
            prompt=prompt,
            system=system_prompt,
            max_tokens=4096,
            temperature=0.2,
        )

        # 4. 清理 AI 响应（移除可能的 markdown 代码块）
        config_content = self._clean_ai_response(response)

        # 5. 验证 YAML 格式并过滤多余字段
        try:
            parsed = yaml.safe_load(config_content)
            filtered = self._filter_config_dict(parsed)
            config_content = yaml.safe_dump(
                filtered,
                allow_unicode=True,
                sort_keys=False,
            )
            logger.info("YAML 格式验证通过，并已过滤多余字段")
        except yaml.YAMLError as e:
            logger.warning(f"YAML 格式警告: {e}")

        # 6. 确定输出路径
        if output_path:
            config_path = Path(output_path)
        else:
            config_dir = get_config_dir() / "sites"
            config_dir.mkdir(parents=True, exist_ok=True)
            filename = self._generate_config_filename(url)
            config_path = config_dir / filename

        # 7. 保存配置
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write(config_content)

        logger.info(f"配置已保存到: {config_path}")

        return str(config_path), config_content

    def _clean_ai_response(self, response: str) -> str:
        """
        清理 AI 响应

        移除 markdown 代码块标记等

        Args:
            response: AI 原始响应

        Returns:
            清理后的 YAML 内容
        """
        response = response.strip()

        # 移除 markdown 代码块
        if response.startswith('```yaml'):
            response = response[7:]
        elif response.startswith('```'):
            response = response[3:]

        if response.endswith('```'):
            response = response[:-3]

        return response.strip()

    def _filter_config_dict(self, data: dict) -> dict:
        """过滤 AI 输出中的多余字段，仅保留程序可解析的配置"""
        if not isinstance(data, dict):
            return {}

        def pick(source: dict, keys: list[str]) -> dict:
            return {k: source[k] for k in keys if k in source}

        site = data.get("site") or {}
        fetch = data.get("fetch") or {}
        list_parser = data.get("list_parser") or {}
        detail_parser = data.get("detail_parser") or {}
        cleaning = data.get("cleaning") or {}

        if not isinstance(site, dict):
            site = {}
        if not isinstance(fetch, dict):
            fetch = {}
        if not isinstance(list_parser, dict):
            list_parser = {}
        if not isinstance(detail_parser, dict):
            detail_parser = {}
        if not isinstance(cleaning, dict):
            cleaning = {}

        selectors = list_parser.get("selectors", {})
        if not isinstance(selectors, dict):
            selectors = {}

        filtered = {
            "site": pick(site, ["name", "url", "type"]),
            "fetch": pick(fetch, ["prefer_light", "requires_js", "wait_for"]),
            "list_parser": {
                **pick(list_parser, ["container", "url_prefix"]),
                "selectors": selectors,
            },
            "detail_parser": pick(detail_parser, ["enabled", "max_details"]),
            "cleaning": pick(cleaning, ["remove_tags", "extract_text"]),
        }

        # 清理空的 section
        filtered = {
            k: v for k, v in filtered.items()
            if isinstance(v, dict) and v
        }

        return filtered

    async def close(self):
        """关闭资源"""
        pass
