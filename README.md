# AI 内容脱水日报

🤖 一个**全自动**的技术内容聚合与摘要系统。只需提供新闻站点的 URL，AI 会自动分析页面结构、生成爬取配置、抓取内容并生成精美的每日报告。

## 🎯 项目是做什么的？

这个工具帮助你：

1. **自动监控多个技术新闻源**（如 Hacker News、GitHub Trending、Lobsters 等）
2. **AI 智能脱水**：自动抓取文章详情，提取核心观点，生成结构化摘要
3. **生成每日报告**：输出 Markdown 格式的日报，包含评分、推荐理由、技术栈等

**核心亮点**：无需手写爬虫配置！只需一行命令，AI 就能分析任意新闻站点并生成对应的配置文件。

---

## 🚀 快速开始

### 1. 安装

```bash
cd ai_daily_digest
pip install -r requirements.txt

# 安装 Playwright 浏览器（用于 JS 渲染的页面）
playwright install chromium
```

### 2. 配置 API Key

```bash
# 选择一个 AI 服务
export ANTHROPIC_API_KEY="your-api-key"      # Claude
export OPENAI_API_KEY="your-api-key"         # 或 OpenAI
```

### 3. 运行日报生成

```bash
python main.py
```

---

## ✨ 一键添加新闻站点（核心功能）

**最简单的方式添加新站点**：只需提供目标 URL，AI 会自动生成配置！

### 快速添加示例

```bash
# 添加 Product Hunt
python main.py --generate-config "https://www.producthunt.com/"

# 添加 Reddit 的 r/programming
python main.py --generate-config "https://www.reddit.com/r/programming/"

# 添加 TechCrunch
python main.py --generate-config "https://techcrunch.com/"
```

### 需要 JS 渲染的站点

如果站点内容是动态加载的（如 SPA 页面），使用 `--use-js` 参数：

```bash
python main.py --generate-config "https://example.com/news" --use-js
```

### 指定输出路径

```bash
python main.py --generate-config "https://example.com" --output config/sites/my_site.yaml
```

### 完整流程

```bash
# 1. 生成配置（AI 自动分析页面结构）
python main.py --generate-config "https://news.ycombinator.com/best"

# 2. 检查生成的配置文件
cat config/sites/news_ycombinator_best.yaml

# 3. 将新站点添加到主配置 config/config.yaml 的 sites 列表：
#    sites:
#      - name: news_ycombinator_best
#        enabled: true

# 4. 运行日报
python main.py
```

---

## 📁 项目结构

```
ai_daily_digest/
├── main.py                      # 主入口
├── requirements.txt             # 依赖清单
├── config/
│   ├── config.yaml              # 主配置文件
│   └── sites/                   # 站点配置（自动生成或手动编写）
│       ├── github_trending.yaml
│       ├── hacker_news.yaml
│       └── lobsters.yaml
├── src/
│   ├── core/                    # 核心模块
│   │   ├── config.py            # 配置加载
│   │   ├── models.py            # 数据模型
│   │   ├── queue.py             # 异步队列
│   │   └── exceptions.py        # 自定义异常
│   ├── crawler/                 # 爬虫模块
│   │   ├── light_fetcher.py     # curl_cffi 轻量抓取
│   │   ├── heavy_fetcher.py     # Playwright 重量抓取
│   │   ├── cache.py             # 缓存管理
│   │   └── manager.py           # 抓取管理器
│   ├── processor/               # 处理模块
│   │   ├── html_cleaner.py      # HTML 清洗
│   │   ├── ai_summarizer.py     # AI 摘要
│   │   ├── ai_provider.py       # AI 服务封装
│   │   └── pipeline.py          # 处理流水线
│   ├── generator/               # 配置生成模块
│   │   └── config_generator.py  # AI 自动生成站点配置
│   └── notifier/                # 输出模块
│       ├── report_generator.py  # 报告生成
│       └── terminal_display.py  # 终端显示
├── output/                      # 输出目录
│   ├── report/                  # 每日生成的报告
│   │   └── YYYY/MM/DD/           # 按日期分层
│   │       ├── daily_report_*.md
│   │       └── daily_report_*.json
│   └── cache/                   # 抓取缓存
└── templates/                   # 报告模板
```

---

## 🧾 报告目录

所有报告按日期分层存放在 [output/report](output/report)，结构为 YYYY/MM/DD。

---

## 🌟 特性一览

| 特性 | 描述 |
|------|------|
| 🤖 **AI 自动生成配置** | 只需提供 URL，自动分析页面结构生成爬取配置 |
| 🚀 **轻重结合抓取** | 优先使用 `curl_cffi` 快速抓取，失败自动回退到 `Playwright` |
| 🧠 **多 AI 模型支持** | Claude、OpenAI、Azure OpenAI、自定义模型 |
| 🛡️ **反检测能力** | `playwright-stealth` + TLS 指纹模拟 |
| ⚡ **异步高并发** | 异步架构，支持并发抓取和处理 |
| 📦 **智能缓存** | 自动缓存抓取内容，避免重复请求 |
| 📊 **精美报告** | Markdown 报告 + Rich 终端显示 |

---

## ⚙️ 配置说明

### 主配置 (config/config.yaml)

```yaml
# AI 模型配置
ai:
  default_provider: "claude"  # claude | openai | azure_openai | custom
  
  claude:
    api_key: "${ANTHROPIC_API_KEY}"
    model: "claude-sonnet-4-20250514"
  
  openai:
    api_key: "${OPENAI_API_KEY}"
    model: "gpt-4o"
  
  # 自定义模型（兼容 OpenAI API 格式）
  custom:
    api_base: "http://localhost:8000/v1"  # vLLM / LocalAI / Ollama
    api_key: "optional-key"
    model: "llama-3"

# 爬虫配置
crawler:
  concurrency: 5
  timeout: 30
  cache:
    enabled: true
    keep_days: 7

# 摘要配置
digest:
  score_threshold: 6.0  # 只显示评分 >= 6 的内容

# 启用的站点
sites:
  - name: hacker_news
    enabled: true
  - name: github_trending
    enabled: true
```

### 站点配置示例 (config/sites/hacker_news.yaml)

```yaml
site:
  name: "Hacker News"
  url: "https://news.ycombinator.com/best"
  type: "structured"

fetch:
  prefer_light: true
  requires_js: false

list_parser:
  container: "tr.athing"
  selectors:
    title: "span.titleline > a"
    url: "span.titleline > a"

detail_parser:
  enabled: true
  max_details: 30
  use_readability: true
```

---

## 📝 命令行参数

```bash
python main.py [OPTIONS]

选项:
  -c, --config PATH          指定配置文件路径
  -p, --provider PROVIDER    指定 AI provider (claude/openai/azure_openai/custom)
  --dry-run                  试运行（不调用 AI）
  -v, --verbose              详细输出

配置生成:
  --generate-config URL      根据 URL 自动生成站点配置
  --use-js                   使用 JS 渲染抓取页面
  --output PATH              配置文件输出路径
```

---

## 📄 输出示例

### Markdown 报告

```markdown
# 🗞️ AI 内容脱水日报

📅 日期: 2026-02-10

## 📊 今日概览
- 抓取数量: 50
- 高质量项目: 12
- 平均评分: 7.2

## 🌟 高质量项目

### 1. [Rust GUI Framework](https://example.com) ⭐ 1.2k stars

**评分**: ⭐⭐⭐⭐⭐⭐⭐⭐ (8.5/10)
**核心价值**: 使用 Rust 实现的跨平台 GUI 框架，性能优异
**技术栈**: Rust, WebGPU, Wasm
**推荐理由**: 对于需要高性能桌面应用的开发者非常值得关注
```

---

## 🐳 Docker 部署

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . .

RUN pip install -r requirements.txt && \
    playwright install chromium --with-deps

CMD ["python", "main.py"]
```

---

## 📜 License

MIT License
