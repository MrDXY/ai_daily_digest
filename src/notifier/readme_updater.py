import os
import re
from pathlib import Path


class ReadmeUpdater:
    """
    README 更新器

    将 daily_insight 报告嵌入到 README.md 中
    """

    def __init__(self, readme_path="README.md", report_dir="output/report"):
        self.readme_path = Path(readme_path)
        self.report_dir = Path(report_dir)
        self.start_marker = "<!-- DIGEST_START -->"
        self.end_marker = "<!-- DIGEST_END -->"

    def _get_recent_insights(self, limit=7):
        """获取最近的洞察报告文件列表，按日期倒序"""
        if not self.report_dir.exists():
            return []

        # 递归查找所有 daily_insight_*.md 文件
        all_insights = list(self.report_dir.glob("**/daily_insight_*.md"))
        # 按文件名（日期格式）倒序排列
        all_insights.sort(key=lambda x: x.name, reverse=True)
        return all_insights[:limit]

    def _extract_insight_content(self, file_path):
        """从洞察报告中提取核心内容"""
        try:
            content = file_path.read_text(encoding="utf-8")

            # 提取宏观风暴部分
            macro_pattern = r"## 🌪️ 宏观风暴.*?(?=\n## )"
            macro_match = re.search(macro_pattern, content, re.DOTALL)
            macro_content = macro_match.group(0).strip() if macro_match else ""

            # 提取核心突破部分
            picks_pattern = r"## ⚡ 核心突破.*?(?=\n## )"
            picks_match = re.search(picks_pattern, content, re.DOTALL)
            picks_content = picks_match.group(0).strip() if picks_match else ""

            # 提取遗珠部分
            gems_pattern = r"## 💎 遗珠/冷思考.*?(?=\n## )"
            gems_match = re.search(gems_pattern, content, re.DOTALL)
            gems_content = gems_match.group(0).strip() if gems_match else ""

            # 提取社区火药味部分
            pulse_pattern = r"## 🗣️ 社区火药味.*?(?=\n---)"
            pulse_match = re.search(pulse_pattern, content, re.DOTALL)
            pulse_content = pulse_match.group(0).strip() if pulse_match else ""

            # 组合内容，将二级标题改为三级标题
            combined = "\n\n".join(filter(None, [
                macro_content,
                picks_content,
                gems_content,
                pulse_content,
            ]))

            # 将 ## 改为 ###，避免破坏 README 结构
            combined = combined.replace("\n## ", "\n### ")
            combined = re.sub(r"^## ", "### ", combined)

            return combined if combined else "暂无洞察内容"

        except Exception as e:
            return f"提取失败: {e}"

    def _generate_html(self, insights):
        """生成折叠框 HTML 结构"""
        if not insights:
            return "\n> 📝 暂无洞察报告生成记录。\n"

        lines = ["\n### 🚀 最近一周 AI 洞察 (Weekly Insight)\n"]

        for i, file_path in enumerate(insights):
            # 从文件名提取日期，例如 daily_insight_2026-02-14.md -> 2026-02-14
            date_str = file_path.stem.replace("daily_insight_", "")
            insight_content = self._extract_insight_content(file_path)
            rel_path = os.path.relpath(file_path, start=".")

            # 第一份报告默认展开 (open)
            is_open = "open" if i == 0 else ""

            item_html = (
                f"<details {is_open}>\n"
                f"  <summary><b>📅 {date_str} AI 洞察速览 (点击展开)</b></summary>\n"
                f"  <blockquote style='margin-top: 10px;'>\n\n"
                f"{insight_content}\n\n"
                f"  <p align='right'><a href='{rel_path}'>🔍 查看完整洞察报告</a></p>\n"
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
        insights = self._get_recent_insights()
        new_content = self._generate_html(insights)

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

        print(f"✅ README.md 已更新，展示了最近 {len(insights)} 天的洞察报告。")
