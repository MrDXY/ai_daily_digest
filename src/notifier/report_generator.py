"""
报告生成器
生成 Markdown 和 JSON 格式的日报
"""

import json
import logging
import re
from difflib import SequenceMatcher
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import aiofiles
from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..core.models import Article, DigestReport
from ..core.config import AppConfig, get_output_dir


logger = logging.getLogger(__name__)


# Markdown 报告模板
REPORT_TEMPLATE = """# 🗞️ AI 内容脱水日报

📅 **日期**: {{ report.date }}
⏱️ **生成时间**: {{ report.generated_at.strftime('%Y-%m-%d %H:%M:%S') }}

---

## 📊 今日概览

| 指标 | 数值 |
|------|------|
| 📥 抓取数量 | {{ report.total_fetched }} |
| ✅ 处理数量 | {{ report.total_processed }} |
| 🌟 高质量项目 | {{ report.high_quality_count }} |
| 📈 平均评分 | {{ "%.1f"|format(report.avg_score) }} |

### 来源分布
{% for source, count in report.sources.items() %}
- **{{ source }}**: {{ count }} 篇
{% endfor %}

---

## 🌟 高质量项目 (评分 ≥ {{ score_threshold }})

{% for article in high_quality_articles %}
### {{ loop.index }}. [{{ article.title }}]({{ article.url }})

{% if article.stars %}⭐ {{ article.stars }} stars {% endif %}{% if article.language %}| 🔤 {{ article.language }}{% endif %}

**评分**: {{ "⭐" * ((article.score / 10) | int) }} ({{ article.score }}/100)

**核心价值**: {{ article.core_value }}

**技术栈**: {{ article.tech_stack | join(", ") if article.tech_stack else "N/A" }}

**摘要**: {{ article.summary }}

**推荐理由**: {{ article.recommendation }}

---

{% endfor %}

{% if other_articles %}
## 📚 其他项目

{% for article in other_articles %}
### {{ loop.index }}. [{{ article.title }}]({{ article.url }}) - {{ article.score }}/100

{{ article.summary }}

---

{% endfor %}
{% endif %}

---

## 📝 处理日志

{% if report.errors %}
### ⚠️ 错误记录
{% for error in report.errors %}
- {{ error }}
{% endfor %}
{% else %}
✅ 本次处理无错误
{% endif %}

---

> 🤖 由 AI Daily Digest 自动生成
> 
> 处理耗时: {{ "%.2f"|format(report.processing_time_seconds) }} 秒
"""


class ReportGenerator:
    """
    报告生成器

    支持生成：
    - Markdown 格式报告
    - JSON 格式数据
    - 自定义模板
    """

    def __init__(self, config: AppConfig):
        self.config = config
        self.output_dir = get_output_dir(config)

        # 初始化 Jinja2 环境
        template_dir = Path(__file__).parent.parent.parent / "templates"
        if template_dir.exists():
            self.env = Environment(
                loader=FileSystemLoader(str(template_dir)),
                autoescape=select_autoescape(["html", "xml"]),
            )
        else:
            self.env = Environment(autoescape=select_autoescape(["html", "xml"]))

    async def generate(
        self,
        articles: list[Article],
        total_fetched: int = 0,
        errors: list[Any] = None,
        processing_time: float = 0.0,
    ) -> DigestReport:
        """
        生成报告

        Args:
            articles: 文章列表
            total_fetched: 总抓取数
            errors: 错误列表
            processing_time: 处理耗时

        Returns:
            DigestReport 对象
        """
        # 先去重，再排序（价值高到低，受众小的靠后）
        deduped_articles = self._deduplicate_articles(articles)
        sorted_articles = self._sort_articles(deduped_articles)

        # 创建报告对象
        report = DigestReport(
            date=datetime.now().strftime("%Y-%m-%d"),
            total_fetched=total_fetched,
            articles=sorted_articles,
            errors=errors or [],
            processing_time_seconds=processing_time,
            score_threshold=float(self.config.digest.score_threshold),
        )

        # 计算统计信息
        report.calculate_stats()

        # 生成文件
        md_path = await self._generate_markdown(report)

        if self.config.output.generate_json:
            await self._generate_json(report)

        return report

    async def _generate_markdown(self, report: DigestReport) -> Path:
        """生成 Markdown 报告"""
        # 使用内置模板
        from jinja2 import Template
        template = Template(REPORT_TEMPLATE)

        # 分离高质量和其他文章
        high_quality = report.get_high_quality_articles()
        other = [a for a in report.articles if not a.is_high_quality]

        # 渲染模板
        content = template.render(
            report=report,
            high_quality_articles=high_quality,
            other_articles=other,
            score_threshold=report.score_threshold,
        )

        # 生成文件名
        filename = self.config.output.report_filename.format(
            date=report.date
        )
        filepath = self.output_dir / filename

        # 写入文件
        async with aiofiles.open(filepath, "w", encoding="utf-8") as f:
            await f.write(content)

        return filepath

    def _sort_articles(self, articles: list[Article]) -> list[Article]:
        """按价值优先，再按受众规模排序"""
        return sorted(
            articles,
            key=lambda a: (
                -(a.score or 0),
                -self._get_audience_size(a),
                a.title or "",
            ),
        )

    def _deduplicate_articles(self, articles: list[Article]) -> list[Article]:
        """基于标题与摘要相似度去重（跨站点）"""
        if not articles:
            return []

        # 先按评分排序，确保保留质量更高的版本
        candidates = sorted(
            articles,
            key=lambda a: (-(a.score or 0), -(len(a.summary or "")), a.title or ""),
        )

        kept: list[Article] = []
        kept_cache: list[dict[str, Any]] = []
        seen_urls: set[str] = set()

        for article in candidates:
            canonical_url = self._canonicalize_url(article.url or "")
            if canonical_url and canonical_url in seen_urls:
                continue

            title_norm = self._normalize_text(article.title or "")
            text_norm = self._normalize_text(self._build_similarity_text(article))
            text_tokens = self._tokenize(text_norm)

            if self._is_duplicate(title_norm, text_norm, text_tokens, kept_cache):
                continue

            kept.append(article)
            if canonical_url:
                seen_urls.add(canonical_url)
            kept_cache.append(
                {
                    "title_norm": title_norm,
                    "text_norm": text_norm,
                    "tokens": text_tokens,
                }
            )

        removed = len(articles) - len(kept)
        if removed > 0:
            logger.info(f"Deduplicated {removed} similar articles")

        return kept

    def _is_duplicate(
        self,
        title_norm: str,
        text_norm: str,
        text_tokens: list[str],
        kept_cache: list[dict[str, Any]],
    ) -> bool:
        """判断是否与已保留内容语义相似"""
        for cached in kept_cache:
            title_ratio = self._sequence_ratio(title_norm, cached["title_norm"])
            text_ratio = self._sequence_ratio(text_norm, cached["text_norm"])
            jaccard = self._jaccard_similarity(text_tokens, cached["tokens"])

            if (title_ratio >= 0.92 and text_ratio >= 0.86) or text_ratio >= 0.92 or jaccard >= 0.84:
                return True

        return False

    def _build_similarity_text(self, article: Article) -> str:
        """组合用于相似度判断的文本"""
        return "\n".join(
            part
            for part in [article.title, article.summary, article.core_value]
            if part
        )

    def _normalize_text(self, text: str) -> str:
        """清洗并规范化文本"""
        tokens = self._tokenize(text)
        return " ".join(tokens)

    def _tokenize(self, text: str) -> list[str]:
        """简单分词并去除噪声"""
        tokens = re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]+", text.lower())
        cleaned: list[str] = []
        for token in tokens:
            if token.isascii():
                if len(token) > 1:
                    cleaned.append(token)
            else:
                cleaned.append(token)

        return cleaned

    def _sequence_ratio(self, a: str, b: str) -> float:
        if not a or not b:
            return 0.0
        return SequenceMatcher(None, a, b).ratio()

    def _jaccard_similarity(self, a: list[str], b: list[str]) -> float:
        if not a or not b:
            return 0.0
        a_set = set(a)
        b_set = set(b)
        if not a_set or not b_set:
            return 0.0
        return len(a_set & b_set) / len(a_set | b_set)

    def _canonicalize_url(self, url: str) -> str:
        if not url:
            return ""
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return url

            query = parse_qsl(parsed.query, keep_blank_values=True)
            filtered = [
                (k, v)
                for k, v in query
                if not k.lower().startswith("utm_")
            ]
            normalized_query = urlencode(filtered, doseq=True)
            path = parsed.path.rstrip("/")
            return urlunparse(
                (parsed.scheme, parsed.netloc, path, "", normalized_query, "")
            )
        except Exception:
            return url

    def _get_audience_size(self, article: Article) -> int:
        """估算受众规模（stars / metadata 中的热度字段）"""
        if article.stars:
            return int(article.stars)

        candidates = [
            "stars",
            "points",
            "score",
            "votes",
            "upvotes",
            "comments",
            "replies",
            "likes",
            "heat",
            "views",
        ]

        for key in candidates:
            value = article.metadata.get(key) if article.metadata else None
            parsed = self._parse_numeric(value)
            if parsed is not None:
                return parsed

        return 0

    def _parse_numeric(self, value: Any) -> Optional[int]:
        if value is None:
            return None

        try:
            if isinstance(value, (int, float)):
                return int(value)

            if isinstance(value, str):
                v = value.strip().lower().replace(",", "")
                if v.endswith("k"):
                    return int(float(v[:-1]) * 1000)
                if v.endswith("m"):
                    return int(float(v[:-1]) * 1000000)
                return int(float(v))
        except Exception:
            return None

        return None

    async def _generate_json(self, report: DigestReport) -> Path:
        """生成 JSON 数据"""
        filename = f"daily_report_{report.date}.json"
        filepath = self.output_dir / filename

        # 转换为可序列化的字典
        data = {
            "date": report.date,
            "generated_at": report.generated_at.isoformat(),
            "stats": {
                "total_fetched": report.total_fetched,
                "total_processed": report.total_processed,
                "high_quality_count": report.high_quality_count,
                "avg_score": round(report.avg_score, 2),
                "sources": report.sources,
            },
            "articles": [
                {
                    "id": a.id,
                    "title": a.title,
                    "url": a.url,
                    "source": a.source,
                    "summary": a.summary,
                    "core_value": a.core_value,
                    "tech_stack": a.tech_stack,
                    "recommendation": a.recommendation,
                    "score": a.score,
                    "stars": a.stars,
                    "language": a.language,
                }
                for a in report.articles
            ],
            "errors": report.errors,
            "processing_time_seconds": round(report.processing_time_seconds, 2),
        }

        async with aiofiles.open(filepath, "w", encoding="utf-8") as f:
            await f.write(json.dumps(data, ensure_ascii=False, indent=2))

        return filepath

    async def generate_summary_email(
        self,
        report: DigestReport,
    ) -> str:
        """
        生成邮件摘要（HTML 格式）

        可用于邮件通知
        """
        high_quality = report.get_high_quality_articles()

        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; }}
                .header {{ background: #1a1a2e; color: white; padding: 20px; }}
                .stats {{ display: flex; gap: 20px; margin: 20px 0; }}
                .stat-box {{ background: #f5f5f5; padding: 15px; border-radius: 8px; }}
                .article {{ border-bottom: 1px solid #eee; padding: 15px 0; }}
                .score {{ color: #f39c12; font-weight: bold; }}
                .tech-stack {{ color: #3498db; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🗞️ AI 内容脱水日报</h1>
                <p>📅 {report.date}</p>
            </div>
            
            <div class="stats">
                <div class="stat-box">
                    <strong>{report.total_processed}</strong><br/>
                    处理数量
                </div>
                <div class="stat-box">
                    <strong>{report.high_quality_count}</strong><br/>
                    高质量项目
                </div>
                <div class="stat-box">
                    <strong>{report.avg_score:.1f}</strong><br/>
                    平均评分
                </div>
            </div>
            
            <h2>🌟 今日精选</h2>
        """

        for i, article in enumerate(high_quality[:5], 1):
            tech_str = ", ".join(article.tech_stack) if article.tech_stack else ""
            html += f"""
            <div class="article">
                <h3>{i}. <a href="{article.url}">{article.title}</a></h3>
                <p class="score">评分: {article.score}/100</p>
                <p><strong>核心价值:</strong> {article.core_value}</p>
                <p class="tech-stack">技术栈: {tech_str}</p>
                <p>{article.summary}</p>
            </div>
            """

        html += """
            <hr/>
            <p style="color: #888; font-size: 12px;">
                🤖 由 AI Daily Digest 自动生成
            </p>
        </body>
        </html>
        """

        return html
