import os
import re
from pathlib import Path
from datetime import datetime


class ReadmeUpdater:
    def __init__(self, readme_path="README.md", report_dir="output/report"):
        self.readme_path = Path(readme_path)
        self.report_dir = Path(report_dir)
        self.start_marker = "<!-- DIGEST_START -->"
        self.end_marker = "<!-- DIGEST_END -->"

    def _get_recent_reports(self, limit=7):
        """获取最近的报告文件列表，按日期倒序"""
        if not self.report_dir.exists():
            return []

        # 递归查找所有 .md 文件
        all_reports = list(self.report_dir.glob("**/*.md"))
        # 按文件名（日期格式）倒序排列
        all_reports.sort(key=lambda x: x.name, reverse=True)
        return all_reports[:limit]

    def _extract_highlights(self, file_path):
        """从报告中提取核心精华内容（如高质量项目部分）"""
        try:
            content = file_path.read_text(encoding="utf-8")
            # 匹配 "## 🌟 高质量项目" 到下一个 "---" 或文件末尾之间的内容
            pattern = r"## 🌟 高质量项目(.*?)(?=\n---|\Z)"
            match = re.search(pattern, content, re.DOTALL)

            if match:
                highlights = match.group(1).strip()
                # 将内容中的二级标题改为三级或更小，避免破坏 README 结构
                highlights = highlights.replace("\n### ", "\n#### ")
                return highlights
            return "暂无核心摘要"
        except Exception as e:
            return f"提取失败: {e}"

    def _generate_html(self, reports):
        """生成折叠框 HTML 结构"""
        if not reports:
            return "\n> 📝 暂无报告生成记录。\n"

        lines = ["\n### 🚀 最近一周内容脱水 (Weekly Digest)\n"]

        for i, file_path in enumerate(reports):
            # 从文件名提取日期，例如 daily_report_2026-02-13.md -> 2026-02-13
            date_str = file_path.stem.replace("daily_report_", "")
            highlights = self._extract_highlights(file_path)
            rel_path = os.path.relpath(file_path, start=".")

            # 第一份报告默认展开 (open)
            is_open = "open" if i == 0 else ""

            item_html = (
                f"<details {is_open}>\n"
                f"  <summary><b>📅 {date_str} 重点速览 (点击展开)</b></summary>\n"
                f"  <blockquote style='margin-top: 10px;'>\n\n"
                f"{highlights}\n\n"
                f"  <p align='right'><a href='{rel_path}'>🔍 查看完整报告详情</a></p>\n"
                f"  </blockquote>\n"
                f"</details>\n"
            )
            lines.append(item_html)

        lines.append(f"\n> 💡 更多历史数据请查看 [output/report](./output/report) 目录。\n")
        return "\n".join(lines)

    def update(self):
        """执行更新操作"""
        if not self.readme_path.exists():
            print(f"Error: {self.readme_path} not found.")
            return

        # 1. 获取内容
        reports = self._get_recent_reports()
        new_content = self._generate_html(reports)

        # 2. 读取原 README
        with open(self.readme_path, "r", encoding="utf-8") as f:
            readme_text = f.read()

        # 3. 使用正则替换标记间的内容
        pattern = f"{re.escape(self.start_marker)}.*?{re.escape(self.end_marker)}"
        replacement = f"{self.start_marker}\n{new_content}\n{self.end_marker}"

        if not re.search(pattern, readme_text, re.DOTALL):
            print("Error: Markers not found in README.md")
            return

        updated_text = re.sub(pattern, replacement, readme_text, flags=re.DOTALL)

        # 4. 写回文件
        with open(self.readme_path, "w", encoding="utf-8") as f:
            f.write(updated_text)

        print(f"✅ README.md 已更新，展示了最近 {len(reports)} 天的报告。")