# AI 内容脱水日报

一个自动化的技术内容聚合与摘要系统，支持多数据源抓取、AI 智能脱水和精美报告生成。

## 🌟 特性

- **轻重结合抓取策略**：优先使用 `curl_cffi` 快速抓取，失败自动回退到 `Playwright`
- **多 AI 模型支持**：Claude、OpenAI、Azure OpenAI、自定义模型
- **反检测能力**：`playwright-stealth` + TLS 指纹模拟
- **异步架构**：高并发处理，可无缝迁移到 KubeRay 分布式环境
- **可配置数据源**：YAML 配置站点规则，易于扩展
- **精美输出**：Markdown 报告 + Rich 终端显示

## 📁 项目结构

```
ai_daily_digest/
├── main.py                      # 主入口
├── requirements.txt             # 依赖清单
├── config/
│   ├── config.yaml              # 主配置文件
│   └── sites/                   # 站点配置
│       ├── github_trending.yaml
│       └── hacker_news.yaml
├── src/
│   ├── core/                    # 核心模块
│   │   ├── config.py            # 配置加载
│   │   ├── models.py            # 数据模型
│   │   ├── queue.py             # 异步队列
│   │   └── exceptions.py        # 自定义异常
│   ├── crawler/                 # 爬虫模块
│   │   ├── base.py              # 抽象基类
│   │   ├── light_fetcher.py     # curl_cffi 轻量抓取
│   │   ├── heavy_fetcher.py     # Playwright 重量抓取
│   │   └── manager.py           # 抓取管理器
│   ├── processor/               # 处理模块
│   │   ├── html_cleaner.py      # HTML 清洗
│   │   ├── ai_summarizer.py     # AI 摘要（多模型）
│   │   └── pipeline.py          # 处理流水线
│   └── notifier/                # 通知模块
│       ├── report_generator.py  # 报告生成
│       └── terminal_display.py  # 终端显示
└── output/                      # 输出目录
```

## 🚀 快速开始

### 1. 安装依赖

```bash
cd ai_daily_digest
pip install -r requirements.txt

# 安装 Playwright 浏览器
playwright install chromium
```

### 2. 配置 API Key

```bash
# Claude
export ANTHROPIC_API_KEY="your-api-key"

# 或 OpenAI
export OPENAI_API_KEY="your-api-key"

# 或 Azure OpenAI
export AZURE_OPENAI_API_KEY="your-api-key"
export AZURE_OPENAI_ENDPOINT="https://your-endpoint.openai.azure.com"
```

### 3. 运行

```bash
# 使用默认配置
python main.py

# 指定 AI provider
python main.py --provider claude

# 试运行（不调用 AI）
python main.py --dry-run

# 使用自定义配置
python main.py --config path/to/config.yaml
```

## ⚙️ 配置说明

### 主配置 (config/config.yaml)

```yaml
# AI 模型配置
ai:
  default_provider: "claude"  # claude | openai | azure_openai | custom
  
  claude:
    api_key: "${ANTHROPIC_API_KEY}"
    model: "claude-sonnet-4-20250514"
  
  azure_openai:
    api_key: "${AZURE_OPENAI_API_KEY}"
    api_base: "${AZURE_OPENAI_ENDPOINT}"
    deployment_name: "gpt-4o"
  
  custom:
    api_base: "https://your-model-endpoint.com/v1"
    model: "your-model-name"
```

### 站点配置 (config/sites/*.yaml)

```yaml
site:
  name: "GitHub Trending"
  url: "https://github.com/trending"
  type: "structured"

list_parser:
  container: "article.Box-row"
  selectors:
    title: "h2 a"
    url: "h2 a"
    description: "p.col-9"
```

## 🔌 扩展 AI 模型

系统支持任何兼容 OpenAI API 格式的模型：

```yaml
ai:
  default_provider: "custom"
  custom:
    api_base: "http://localhost:8000/v1"  # vLLM / LocalAI / Ollama
    api_key: "optional-key"
    model: "llama-3"
    extra_headers:
      X-Custom-Header: "value"
```

## 🐳 Docker 部署

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . .

RUN pip install -r requirements.txt && \
    playwright install chromium --with-deps

CMD ["python", "main.py"]
```

## ☸️ KubeRay 集成

项目设计为可无缝迁移到 Ray 分布式环境：

1. 取消 `requirements.txt` 中 Ray 的注释
2. 修改 `src/core/queue.py` 使用 `RayTaskQueue`
3. 使用 `@ray.remote` 装饰器包装处理函数

## 📄 输出示例

### Markdown 报告

```markdown
# 🗞️ AI 内容脱水日报

📅 日期: 2024-01-15

## 📊 今日概览
- 抓取数量: 50
- 高质量项目: 12
- 平均评分: 7.2

## 🌟 高质量项目

### 1. [Project Name](url) ⭐ 1.2k stars

**评分**: ⭐⭐⭐⭐⭐⭐⭐⭐ (8.5/10)
**核心价值**: ...
**技术栈**: Python, FastAPI, PostgreSQL
**推荐理由**: ...
```

### 终端输出

![Terminal Output](docs/terminal.png)

## 📜 License

MIT License
