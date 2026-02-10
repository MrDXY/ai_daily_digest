"""
报告生成器
生成 Markdown 和 JSON 格式的日报
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import aiofiles
from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..core.models import Article, DigestReport
from ..core.config import AppConfig, get_output_dir


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

## 🌟 高质量项目 (评分 ≥ 8)

{% for article in high_quality_articles %}
### {{ loop.index }}. [{{ article.title }}]({{ article.url }})

{% if article.stars %}⭐ {{ article.stars }} stars {% endif %}{% if article.language %}| 🔤 {{ article.language }}{% endif %}

**评分**: {{ "⭐" * (article.score | int) }} ({{ article.score }}/10)

**核心价值**: {{ article.core_value }}

**技术栈**: {{ article.tech_stack | join(", ") if article.tech_stack else "N/A" }}

**摘要**: {{ article.summary }}

**推荐理由**: {{ article.recommendation }}

---

{% endfor %}

{% if other_articles %}
## 📚 其他项目

{% for article in other_articles %}
### {{ loop.index }}. [{{ article.title }}]({{ article.url }}) - {{ article.score }}/10

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
        errors: list[dict[str, Any]] = None,
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
        # 创建报告对象
        report = DigestReport(
            date=datetime.now().strftime("%Y-%m-%d"),
            total_fetched=total_fetched,
            articles=articles,
            errors=errors or [],
            processing_time_seconds=processing_time,
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
                <p class="score">评分: {article.score}/10</p>
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
