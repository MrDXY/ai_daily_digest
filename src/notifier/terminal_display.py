"""
终端显示模块
使用 Rich 库提供美观的终端输出
"""

from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.live import Live
from rich.layout import Layout
from rich.markdown import Markdown

from ..core.models import Article, DigestReport


class TerminalDisplay:
    """
    终端显示器

    提供美观的终端输出，包括：
    - 进度条
    - 统计表格
    - 高亮显示高质量项目
    """

    def __init__(
        self,
        score_threshold: float = 80.0,
        show_low_score: bool = False,
    ):
        self.console = Console()
        self.score_threshold = score_threshold
        self.show_low_score = show_low_score

    def show_banner(self) -> None:
        """显示启动横幅"""
        banner = """
    ╔═══════════════════════════════════════════════════════╗
    ║     🗞️  AI 内容脱水日报 - Daily Digest Generator     ║
    ║                                                       ║
    ║   Fetch → Clean → Summarize → Report                  ║
    ╚═══════════════════════════════════════════════════════╝
        """
        self.console.print(banner, style="bold cyan")

    def show_config(self, config_summary: dict) -> None:
        """显示配置摘要"""
        table = Table(title="📋 Configuration", show_header=True)
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="green")

        for key, value in config_summary.items():
            table.add_row(key, str(value))

        self.console.print(table)
        self.console.print()

    def create_progress(self) -> Progress:
        """创建进度条"""
        return Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("({task.completed}/{task.total})"),
            console=self.console,
        )

    def show_fetch_result(self, success: int, failed: int, total: int) -> None:
        """显示抓取结果"""
        self.console.print()
        self.console.print(
            Panel(
                f"✅ 成功: [green]{success}[/green]  "
                f"❌ 失败: [red]{failed}[/red]  "
                f"📊 总计: [blue]{total}[/blue]",
                title="抓取结果",
                border_style="blue",
            )
        )

    def show_article(self, article: Article, index: int = 0) -> None:
        """显示单篇文章"""
        # 评分颜色
        if article.score >= 90:
            score_style = "bold green"
            score_emoji = "🔥"
        elif article.score >= 80:
            score_style = "bold yellow"
            score_emoji = "⭐"
        elif article.score >= 60:
            score_style = "cyan"
            score_emoji = "📌"
        else:
            score_style = "dim"
            score_emoji = "📄"

        # 构建面板内容
        content = Text()

        # 评分行
        content.append(f"{score_emoji} 评分: ", style="bold")
        content.append(f"{article.score}/100", style=score_style)
        if article.stars:
            content.append(f"  ⭐ {article.stars} stars", style="yellow")
        if article.language:
            content.append(f"  🔤 {article.language}", style="magenta")
        content.append("\n\n")

        # 核心价值
        content.append("💡 核心价值: ", style="bold cyan")
        content.append(f"{article.core_value}\n\n")

        # 技术栈
        if article.tech_stack:
            content.append("🛠️ 技术栈: ", style="bold blue")
            content.append(", ".join(article.tech_stack) + "\n\n")

        # 摘要
        content.append("📝 摘要: ", style="bold")
        content.append(f"{article.summary}\n\n")

        # 推荐理由
        content.append("👍 推荐理由: ", style="bold green")
        content.append(article.recommendation)

        # 标题样式
        title = f"[{index}] {article.title}"
        subtitle = f"🔗 {article.url}"

        panel = Panel(
            content,
            title=title,
            subtitle=subtitle,
            border_style="green" if article.score >= self.score_threshold else "blue",
        )

        self.console.print(panel)
        self.console.print()

    def show_high_quality_articles(self, articles: list[Article]) -> None:
        """显示高质量文章列表"""
        high_quality = [a for a in articles if a.score >= self.score_threshold]

        if not high_quality:
            self.console.print(
                "[yellow]⚠️ 今日没有评分 ≥ {:.0f} 的高质量项目[/yellow]".format(
                    self.score_threshold
                )
            )
            return

        self.console.print()
        self.console.rule(
            f"[bold green]🌟 高质量项目 (评分 ≥ {self.score_threshold})[/bold green]"
        )
        self.console.print()

        # 按价值与受众排序
        high_quality = self._sort_articles(high_quality)

        for i, article in enumerate(high_quality, 1):
            self.show_article(article, i)

    def show_report_summary(self, report: DigestReport) -> None:
        """显示报告摘要"""
        self.console.print()
        self.console.rule("[bold cyan]📊 报告摘要[/bold cyan]")

        # 统计表格
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("指标", style="cyan")
        table.add_column("数值", justify="right", style="green")

        table.add_row("📥 抓取数量", str(report.total_fetched))
        table.add_row("✅ 处理数量", str(report.total_processed))
        table.add_row("🌟 高质量项目", str(report.high_quality_count))
        table.add_row("📈 平均评分", f"{report.avg_score:.1f}")
        table.add_row("⏱️ 处理耗时", f"{report.processing_time_seconds:.2f}s")

        self.console.print(table)

        # 来源分布
        if report.sources:
            self.console.print()
            source_table = Table(title="📚 来源分布", show_header=True)
            source_table.add_column("来源", style="cyan")
            source_table.add_column("数量", justify="right", style="green")

            for source, count in report.sources.items():
                source_table.add_row(source, str(count))

            self.console.print(source_table)

    def show_error(self, message: str) -> None:
        """显示错误信息"""
        self.console.print(f"[bold red]❌ Error:[/bold red] {message}")

    def show_warning(self, message: str) -> None:
        """显示警告信息"""
        self.console.print(f"[bold yellow]⚠️ Warning:[/bold yellow] {message}")

    def show_success(self, message: str) -> None:
        """显示成功信息"""
        self.console.print(f"[bold green]✅ Success:[/bold green] {message}")

    def show_info(self, message: str) -> None:
        """显示信息"""
        self.console.print(f"[bold blue]ℹ️ Info:[/bold blue] {message}")

    def show_completion(self, report_path: str) -> None:
        """显示完成信息"""
        self.console.print()
        self.console.print(
            Panel(
                f"📄 报告已生成: [bold cyan]{report_path}[/bold cyan]\n\n"
                f"🎉 处理完成！",
                title="✅ 任务完成",
                border_style="green",
            )
        )

    def show_articles_table(self, articles: list[Article]) -> None:
        """以表格形式显示文章列表"""
        articles = self._sort_articles(articles)
        table = Table(
            title="📋 文章列表",
            show_header=True,
            header_style="bold magenta",
        )

        table.add_column("#", style="dim", width=3)
        table.add_column("标题", style="cyan", max_width=40)
        table.add_column("来源", style="blue")
        table.add_column("评分", justify="center")
        table.add_column("技术栈", style="green", max_width=30)

        for i, article in enumerate(articles, 1):
            # 评分样式
            if article.score >= 80:
                score_str = f"[bold green]{article.score:.1f}[/bold green]"
            elif article.score >= 60:
                score_str = f"[yellow]{article.score:.1f}[/yellow]"
            else:
                score_str = f"[dim]{article.score:.1f}[/dim]"

            tech = ", ".join(article.tech_stack[:3]) if article.tech_stack else "-"

            table.add_row(
                str(i),
                article.title[:38] + "..." if len(article.title) > 40 else article.title,
                article.source,
                score_str,
                tech,
            )

        self.console.print(table)

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

    def _parse_numeric(self, value):
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
