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
│   ├── crawler/                 # 爬虫模块 (原有实现)
│   │   ├── stealth_fetcher.py   # 隐身抓取器（多层反爬虫）
│   │   ├── manager.py           # 抓取管理器
│   │   ├── light_fetcher.py     # curl_cffi 轻量抓取 (备用)
│   │   ├── heavy_fetcher.py     # Playwright 重量抓取 (备用)
│   │   └── cache.py             # 缓存管理
│   ├── scrapy_crawler/          # 🆕 Scrapy 爬虫模块
│   │   ├── manager.py           # Scrapy 抓取管理器
│   │   ├── spiders/             # Spider 定义
│   │   │   ├── base_spider.py   # 基础 Spider
│   │   │   └── site_spider.py   # 动态站点 Spider
│   │   ├── middlewares.py       # 反爬虫中间件
│   │   └── pipelines.py         # 数据处理管道
│   ├── processor/               # 处理模块
│   │   ├── content_extractor.py # 🆕 智能内容提取器
│   │   ├── html_cleaner.py      # HTML 清洗
│   │   ├── ai_summarizer.py     # AI 摘要
│   │   ├── ai_provider.py       # AI 服务封装
│   │   └── pipeline.py          # 处理流水线
│   ├── generator/               # 配置生成模块
│   │   └── config_generator.py  # AI 自动生成站点配置
│   ├── notifier/                # 输出模块
│   │   ├── report_generator.py  # 报告生成
│   │   └── terminal_display.py  # 终端显示
│   └── test/                    # 测试模块
│       ├── test_crawler.py      # 🆕 爬虫测试
│       ├── test_content_extractor.py  # 🆕 内容提取测试
│       └── test_integration.py  # 🆕 集成测试
├── output/                      # 输出目录
│   ├── report/                  # 每日生成的报告
│   │   └── YYYY/MM/DD/          # 按日期分层
│   ├── cache/                   # 抓取缓存
│   └── dedup_cache/             # 跨日去重缓存
└── templates/                   # 报告模板
```

---

## 🧾 报告目录

所有报告按日期分层存放在 [output/report](output/report)，结构为 YYYY/MM/DD。

<!-- DIGEST_START -->

### 🚀 最近一周内容脱水 (Weekly Digest)

<details open>
  <summary><b>📅 2026-02-14 重点速览 (点击展开)</b></summary>
  <blockquote style='margin-top: 10px;'>

(评分 ≥ 80.0)


#### 1. [microgpt](http://karpathy.github.io/2026/02/12/microgpt/)



**评分**: ⭐⭐⭐⭐⭐⭐⭐⭐⭐ (92.0/100)

**核心价值**: 用极简、可读、可端到端运行的方式展示 GPT 训练/推理的“算法本体”，帮助读者理解 LLM 的核心组成而不被工程复杂度（框架、分布式、性能优化）淹没。解决了“想看清 GPT 到底由哪些最小模块构成、梯度如何流动、训练循环如何闭环”的学习门槛问题。

**技术栈**: Python, 自研Autograd(微分计算图/反向传播), 字符级Tokenizer, Transformer/GPT-2风格架构, Adam优化器, 训练循环与采样推理, Google Colab, GitHub Gist

**摘要**: microgpt 是一个仅约 200 行、单文件、零依赖的纯 Python 教学级项目，用最小实现从零训练并推理一个 GPT（类 GPT-2）模型。它把数据集读取、字符级 tokenizer、自制 autograd、Transformer/GPT 网络、Adam 优化器、训练与采样推理全部收敛到一份脚本中，并配套逐段讲解代码。示例使用约 3.2 万个英文名字作为语料，训练后可生成统计上“像名字”的新样本。

**推荐理由**: 它把通常分散在多个库与大量样板代码中的 LLM 关键机制压缩到可通读的最小实现，非常适合做“从原理到代码”的对照学习与教学演示。对想理解 micrograd/makemore/nanogpt 体系脉络、或想自己实现/改造最小 GPT 原型的人尤其有参考价值。

  <p align='right'><a href='output/report/2026/02/14/daily_report_2026-02-14.md'>🔍 查看完整报告详情</a></p>
  </blockquote>
</details>

<details >
  <summary><b>📅 2026-02-13 重点速览 (点击展开)</b></summary>
  <blockquote style='margin-top: 10px;'>

(评分 ≥ 80.0)


#### 1. [google-deepmind /superhuman](https://github.com/google-deepmind/superhuman)

⭐ 304 stars | 🔤 TeX

**评分**: ⭐⭐⭐⭐⭐⭐⭐⭐⭐ (92.0/100)

**核心价值**: 通过开源基准、数据与代理输出，为“如何可靠评测与推进 AI 的强数学推理（含证明）能力”提供可复用的公共基础设施。尤其补齐了证明题评测、短答题评测与自动评分数据等关键环节。

**技术栈**: Python, 大语言模型（Gemini Deep Think）, 数学推理/自动定理证明（几何证明）, 基准测试与数据集构建, 自动评测/评分（grading）

**摘要**: google-deepmind/superhuman 汇集了 DeepMind“Superhuman Reasoning”团队发布的多个数学推理相关项目与数据集，包括 AlphaGeometry/AlphaGeometry2、IMO Bench 以及数学研究代理 Aletheia。项目覆盖从几何自动证明到 IMO 级别评测与自动评分数据，面向提升与评估 AI 的高阶数学推理能力。

**推荐理由**: 同时提供 SOTA 级项目（AlphaGeometry 系列）与系统化评测套件（IMO Bench），对研究“推理能力提升+可靠评估”非常有参考价值。Aletheia 的提示词与输出也为构建可迭代验证/修正的数学研究代理提供了直接素材。

  <p align='right'><a href='output/report/2026/02/13/daily_report_2026-02-13.md'>🔍 查看完整报告详情</a></p>
  </blockquote>
</details>

<details >
  <summary><b>📅 2026-02-12 重点速览 (点击展开)</b></summary>
  <blockquote style='margin-top: 10px;'>

(评分 ≥ 80.0)


#### 1. [microsoft /PowerToys](https://github.com/microsoft/PowerToys)

⭐ 129472 stars | 🔤 C#

**评分**: ⭐⭐⭐⭐⭐⭐⭐⭐⭐ (90.0/100)

**核心价值**: 以“系统级工具箱”的方式解决 Windows 日常操作中高频但分散的效率痛点（窗口管理、剪贴板增强、文件批处理、快捷命令等），显著降低重复操作成本。通过开源与持续发布，使个人用户与企业都能获得可配置、可治理的生产力增强方案。

**技术栈**: Windows, .NET, C#, WinUI/Windows UI, MSIX, WinGet, PowerShell, GitHub Actions/CI, ADMX/GPO(企业策略)

**摘要**: Microsoft PowerToys 是微软官方开源的 Windows 增强工具集，提供 25+ 个小工具以提升生产力与系统可定制性（如窗口布局、快捷启动、批量重命名、取色、文本提取等）。项目通过统一的设置与持续迭代，把分散的“效率插件”能力整合为一套可维护、可部署的系统级工具。近期 0.97.x 版本重点修复稳定性问题，并在 Command Palette、Cursor Wrap、Advanced Paste 等模块持续增强体验与企业可管控性。

**推荐理由**: 工具覆盖面广且贴近真实工作流，安装渠道完善（GitHub/MS Store/WinGet）并保持高频迭代，适合直接落地提升效率。对开发者与企业管理员也有价值：扩展生态（如 Command Palette 扩展）、策略管控（ADMX/GPO）与开源实现便于二次开发与审计。

  <p align='right'><a href='output/report/2026/02/12/daily_report_2026-02-12.md'>🔍 查看完整报告详情</a></p>
  </blockquote>
</details>


> 💡 更多历史数据请查看 [output/report](./output/report) 目录。

<!-- DIGEST_END -->

---

## 🌟 特性一览

| 特性 | 描述 |
|------|------|
| 🤖 **AI 自动生成配置** | 只需提供 URL，自动分析页面结构生成爬取配置 |
| 🛡️ **隐身抓取器** | 🆕 多层反爬虫策略（Crawl4AI + Playwright + httpx），自动回退与重试 |
| 🔍 **智能内容提取** | 🆕 自动识别页面类型，无需复杂配置即可提取列表/文章内容 |
| 🧠 **多 AI 模型支持** | Claude、OpenAI、Azure OpenAI、自定义模型 |
| 🛡️ **反检测能力** | 浏览器指纹伪装、请求头随机化、智能延迟 |
| ⚡ **异步高并发** | 异步架构，支持并发抓取和处理 |
| 📦 **智能缓存** | 自动缓存抓取内容，避免重复请求 |
| 📊 **精美报告** | Markdown 报告 + Rich 终端显示 |
| ✅ **完整测试覆盖** | 🆕 单元测试 + 集成测试确保稳定性 |

---

## 🕷️ 爬虫架构 (v2.0 重构)

### 隐身抓取器 (StealthFetcher)

新的爬虫架构采用多层抓取策略，自动处理反爬虫机制：

```
请求 → [随机延迟] → [指纹伪装] → httpx (轻量)
                                    ↓ 失败或被阻止
                               Crawl4AI (浏览器)
                                    ↓ 失败
                               Playwright (完整浏览器)
```

**特性：**
- 🎭 **浏览器指纹伪装**：随机 User-Agent、Accept-Language、Sec-CH-UA 等请求头
- ⏱️ **智能延迟**：自动添加随机延迟，模拟人类行为
- 🔄 **多层回退**：httpx → Crawl4AI → Playwright 自动回退
- 🛡️ **反爬检测**：自动检测 captcha、403、rate limit、"You can't perform that action" 等反爬页面
- ✅ **内容验证**：针对特定站点（GitHub/HN/Lobsters）验证返回内容是否有效
- 🔁 **指数退避重试**：失败后自动重试，使用指数退避策略

### 智能内容提取器 (SmartContentExtractor)

无需复杂的 CSS 选择器配置，自动识别和提取页面内容：

```python
from src.processor.content_extractor import extract_content

# 自动识别页面类型并提取
result = extract_content(html, url)
# result = {
#     "page_type": "list" | "article",
#     "items": [...],      # 列表页的条目
#     "content": "...",    # 文章页的正文
#     "markdown": "...",   # Markdown 格式
#     "metadata": {...},   # 页面元数据
# }
```

**特性：**
- 📋 **自动识别列表页**：识别常见的列表容器（article、post、item、card 等）
- 📄 **文章正文提取**：使用 readability 算法自动提取正文
- 🔗 **URL 规范化**：自动处理相对/绝对/协议相对 URL
- 📝 **Markdown 输出**：自动将 HTML 转换为 Markdown 格式
- 🧹 **噪声过滤**：移除广告、导航、评论等噪声元素

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

### 语义去重 (semantic dedup)

语义去重使用 `fastembed` 生成向量并做余弦相似度比对，适合在 macOS/Linux 上本地运行。

```yaml
digest:
  semantic_dedup_enabled: true
  semantic_backend: "fastembed"  # fastembed | openai | azure_openai
  semantic_model: "BAAI/bge-small-en"
  semantic_embedding_model: "text-embedding-3-small"
  semantic_embedding_deployment: ""  # Azure 为空则复用 ai.azure_openai.deployment_name
  semantic_threshold: 0.86
  semantic_max_text_length: 1200
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
