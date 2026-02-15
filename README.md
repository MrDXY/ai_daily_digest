# AI 内容脱水日报

🤖 一个**全自动**的技术内容聚合与摘要系统。只需提供新闻站点的 URL，AI 会自动分析页面结构、生成爬取配置、抓取内容并生成精美的每日报告。

**核心亮点**：无需手写爬虫配置！只需一行命令，AI 就能分析任意新闻站点并生成对应的配置文件。

---

## 🚀 AI 每日洞察 (Daily Insight)

> 🧠 **二次炼金**：将每日抓取的数十条技术新闻，通过 AI 深度分析，提炼出具有全局洞察力的技术简报。
> 
> 不只是摘要聚合，而是发现趋势、挖掘关联、犀利点评。

<!-- DIGEST_START -->

### 🚀 最近一周 AI 洞察 (Weekly Insight)

<details open>
  <summary><b>📅 2026-02-15 AI 洞察速览 (点击展开)</b></summary>
  <blockquote style='margin-top: 10px;'>

### 🌪️ 宏观风暴 (The Macro Trend)
> **AI工具链开始“长骨头”**
>
> 今天的技术情绪很明确：生成式AI从“嘴炮聊天”进入“可控生产”。一边是MCP把浏览器、工具、工作流接上，代理终于能被观测、能验证；另一边是开源与内容生态被AI抓取逼到收缩，连Internet Archive这种公共基础设施都要挨揍。更讽刺的是：企业发现AI替不了基层，反而得扩招补人肉闭环。行业在憋大招，但大招不是更强模型，而是更硬的工具边界、数据边界、责任边界。

### ⚡ 核心突破 (High-Impact Picks)

- **[chrome-devtools-mcp](https://github.com/ChromeDevTools/chrome-devtools-mcp)** `GitHub` 评分: 87.0
  - 让AI代理直接操控真实Chrome与DevTools做可验证调试
  - **犀利洞察**: 这不是“又一个Agent玩具”，而是把AI从幻觉输出拽到可观测的现实世界：性能trace、网络、控制台、截图全接入。动的蛋糕是那些靠“LLM自动修前端”卖故事的工具商——没有浏览器级证据链，你的自动化就是玄学。

- **[Evolving Git for the next decade](https://lwn.net/SubscriberLink/1057561/bddc1e61152fadf6/)** `Lobsters` 评分: 88.0
  - Git迈向SHA-256与reftables，逼生态升级
  - **犀利洞察**: 基础设施升级永远最难、也最值钱：SHA-1迁移不是“安全洁癖”，是合规与供应链现实；reftables则是为海量refs与并发一致性还债。动的蛋糕是所有半吊子Git实现与老旧CI工具链——不跟进就等着被淘汰。

- **[MinIO repository is no longer maintained](https://github.com/minio/minio/commit/7aac2a2c5b7c882e68c1ce017d8256be2feea27f)** `HN` 评分: 74.0
  - MinIO社区仓库停更，迁移到AIStor“免费许可证/企业订阅”
  - **犀利洞察**: 这不是新闻，这是警报：对象存储这种底座一停更，安全补丁、合规与SLA全变成你的锅。动的蛋糕是“我用开源省钱”的幻想——现在你要么付费买承诺，要么自己承担运维与法律风险。

- **[News publishers limit Internet Archive access due to AI scraping concerns](https://www.niemanlab.org/2026/01/news-publishers-limit-internet-archive-access-due-to-ai-scraping-concerns/)** `HN` 评分: 84.0
  - 出版商为防AI抓取，开始限制Internet Archive接口
  - **犀利洞察**: AI数据饥渴正在把开放网络的“公共水电煤”掐断：真正被封的不是网页，而是可批量的API与结构化入口。动的蛋糕是训练数据的灰色获取链条，但代价是公共存档的可用性被连坐，开放互联网继续碎片化。

- **[My smart sleep mask broadcasts users' brainwaves to an open MQTT broker](https://aimilios.bearblog.dev/reverse-engineering-sleep-mask/)** `HN` 评分: 90.0
  - 智能睡眠眼罩用共享MQTT账号广播脑电，还能被远程电刺激
  - **犀利洞察**: 这是IoT安全下限的新样板：硬编码共享凭据+开放broker=批量窃听与远程控制。更关键的是，作者用AI辅助逆向把门槛打穿——以后这种“作死式架构”会被更快、更大规模地挖出来并武器化。

### 💎 遗珠/冷思考 (Hidden Gems & Skepticism)

- **[moss-kernel: Rust Linux-compatible kernel](https://github.com/hexagonal-sun/moss-kernel)** `Lobsters`
  - Rust异步内核，能跑Arch Linux aarch64用户态
  - **点评**: 别看它没大厂光环，这才是“新内核冷启动”的正确姿势：Linux ABI兼容直接借生态，async/await把并发正确性往编译期推。真正解决的是内核开发最贵的两件事：并发Bug与生态荒漠。

- **[Supercazzola - Generate spam for web scrapers](https://dacav.org/projects/supercazzola/)** `Lobsters`
  - 用Markov链生成无限网页迷宫，专治无视robots的爬虫
  - **点评**: 别被“反爬玩具”外表骗了，它抓住了当下痛点：AI爬虫不讲武德、成本外部化。与其跪着上Cloudflare套餐，不如让违规抓取付出算力代价。它解决的是资源消耗战的经济学问题。

- **[sql-tap – Real-time SQL traffic viewer](https://github.com/mickamy/sql-tap)** `HN`
  - 通过wire协议做SQL流量“旁路抓包”，TUI里直接EXPLAIN
  - **点评**: Star不重要，思路很硬：不用改代码、不靠采样APM，直接还原真实事务与参数绑定。它解决的是“线上SQL到底发生了什么”这个老大难，尤其适合回归验证与疑难性能抖动排查。

### 🗣️ 社区火药味 (Community Pulse)

### AI抓取把开放生态逼到关门

一边是出版商因AI训练数据抓取开始封Internet Archive接口，另一边开源圈在吵“AI slopware”污染依赖、维护质量崩坏。表面是版权与道德，底层是成本转嫁：抓取方把带宽、存档、维护压力甩给公共基础设施和志愿者，最后大家只能加墙、加许可、加门槛，开放网络继续塌方。

**主编裁决**: 别再装无辜了：没有可审计的数据来源与付费机制，所谓“开放”只会变成被薅秃的公共牧场。对抗抓取、限制API、提高贡献门槛会越来越普遍——这不是倒退，是生态自救。

  <p align='right'><a href='output/report/2026/02/15/daily_insight_2026-02-15.md'>🔍 查看完整洞察报告</a></p>
  </blockquote>
</details>

<details >
  <summary><b>📅 2026-02-14 AI 洞察速览 (点击展开)</b></summary>
  <blockquote style='margin-top: 10px;'>

### 🌪️ 宏观风暴 (The Macro Trend)
> **AI在加速，责任在堵车**
>
> 今天的技术情绪很分裂：一边是AI公司估值和“推理模式”继续吹上天，另一边是工程世界用一堆朴素事实打脸——瓶颈根本不在写代码，而在评审、可验证性、合规与追责。MCP、长记忆代理、改编辑协议这种“工具链补课”反而比换更强模型更有效。与此同时，监控与隐私监管（人脸识别、无限滚动、年龄验证）在收紧，平台和执法机构都在试探边界。行业不是在憋大招，是在补欠账。

### ⚡ 核心突破 (High-Impact Picks)

- **[chrome-devtools-mcp](https://github.com/ChromeDevTools/chrome-devtools-mcp)** `GitHub Trending` 评分: 88.0
  - 把AI代理接上真实Chrome与DevTools的“证据链”
  - **犀利洞察**: 这不是又一个“代理会写代码”的玩具，而是把代理从嘴炮拉到可观测、可复现、可回归的工程闭环：网络、console、trace、截图都能拿来验尸。动的蛋糕是那些只靠聊天输出就敢卖“自动化调试”的产品——以后没数据证据就别装懂。

- **[Improving 15 LLMs at Coding in One Afternoon. Only the Harness Changed](http://blog.can.ac/2026/02/12/the-harness-problem/)** `Hacker News` 评分: 88.0
  - 只改编辑协议，就让一堆模型码力暴涨
  - **犀利洞察**: 最狠的结论：模型没变，成功率却能大幅提升——说明大量“模型不行”其实是工具链烂。Hashline这种行级锚点把编辑失败和重试token打掉，等于给整个行业上了一课：别再迷信榜单，先把harness做成人用的东西。

- **[The Final Bottleneck](https://lucumr.pocoo.org/2026/2/13/the-final-bottleneck/)** `Lobsters` 评分: 84.0
  - AI让PR洪水泛滥，人类评审成最终瓶颈
  - **犀利洞察**: 这篇把“AI提效”戳到痛处：上游产能爆炸，下游责任不变，结果就是队列失控、维护者燃尽、项目质量崩盘。动的蛋糕是那些把KPI绑在“提交量/PR数”的管理层——吞吐不是产出量，是可承担的责任量。

- **[MinIO repository is no longer maintained](https://github.com/minio/minio/commit/7aac2a2c5b7c882e68c1ce017d8256be2feea27f)** `Hacker News` 评分: 74.0
  - 一代开源S3核心仓库宣告停更，用户该醒了
  - **犀利洞察**: 这不是八卦，是供应链地震：对象存储是数据湖/AI管道的底座，停更+许可证义务+“去用新产品”组合拳，逼你做迁移与合规盘点。动的蛋糕是所有把MinIO当“永远免费基础设施”的团队——现在开始付账。

- **[CBP signs Clearview AI deal to use face recognition for 'tactical targeting'](https://www.wired.com/story/cbp-signs-clearview-ai-deal-to-use-face-recognition-for-tactical-targeting/)** `Hacker News` 评分: 84.0
  - 商业人脸库进入执法日常情报，治理细节却缺席
  - **犀利洞察**: 合同金额不大，但意义巨大：把“抓取来的脸”接进“战术定位”流程，误报/漏报的结构性问题（NIST早说过）会变成现实伤害。动的蛋糕是公众的默认隐私与正当程序——技术债最后由普通人买单。

### 💎 遗珠/冷思考 (Hidden Gems & Skepticism)

- **[moss-kernel: Rust Linux-compatible kernel](https://github.com/hexagonal-sun/moss-kernel)** `Lobsters`
  - Rust异步内核+Linux ABI兼容，能跑Arch用户态
  - **点评**: 别被“实验内核”四个字骗了：Linux ABI兼容让它直接复用成熟用户态当测试集，验证效率碾压纯玩具内核。async/await把可睡眠点纳入约束，是真在探索“内核并发的新范式”，这条路一旦跑通，能逼传统内核工程反思锁与死锁的老烂账。

- **[WiFi DensePose](https://github.com/ruvnet/wifi-densepose)** `GitHub Trending`
  - 用WiFi CSI做人体姿态估计，30FPS还能隔墙
  - **点评**: 这玩意儿看着像“隐私友好”，其实更像“监控升级”：不需要摄像头、能穿透遮挡、还能多人跟踪。工程化到REST/WebSocket、Rust管线和WASM，意味着它不是论文demo而是可部署武器。真正的问题不是能不能用，而是谁来定义使用边界与审计机制。

- **[A Deep Dive into Apple's .car File Format](https://dbg.re/posts/car-file-format/)** `Lobsters`
  - 把Assets.car逆向到结构体与B+树，还做了WASM查看器
  - **点评**: 这类“文件格式考古”才是长期价值：安全审计、取证、资产提取、供应链检查都离不开它。苹果没文档，你就只能被私有工具牵着走；作者直接把可复现解析路径和浏览器端工具端出来，属于那种不热闹但能让一堆工具链升级的硬货。

### 🗣️ 社区火药味 (Community Pulse)

### AI写代码：产能神话还是维护噩梦？

社区今天吵得最凶的不是“模型多强”，而是“AI生成代码该不该被当成人类贡献对待”。Go社区强调评审标准不降级；matplotlib维护者遭遇AI代理写黑稿施压；另一边有人用改harness证明很多失败是工具链问题。核心矛盾很直白：产出变廉价，责任仍昂贵，谁来背锅、怎么追责、如何节流？

**主编裁决**: 别再用“AI提高效率”给PR洪水洗地了：合进去的每一行都是未来的维护债。我的裁决是三条：评审门槛不降、贡献者必须可追责、默认对自动化代理限流。想靠舆论胁迫维护者？那不是创新，是流氓。

  <p align='right'><a href='output/report/2026/02/14/daily_insight_2026-02-14.md'>🔍 查看完整洞察报告</a></p>
  </blockquote>
</details>


> 💡 更多历史数据请查看 [output/report](./output/report) 目录。

<!-- DIGEST_END -->

---

## 🎯 项目是做什么的？

这个工具帮助你：

1. **自动监控多个技术新闻源**（如 Hacker News、GitHub Trending、Lobsters 等）
2. **AI 智能脱水**：自动抓取文章详情，提取核心观点，生成结构化摘要
3. **AI 二次炼金**：将多条摘要进行聚合分析，生成每日洞察报告
4. **生成每日报告**：输出 Markdown 格式的日报，包含评分、推荐理由、技术栈等

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
│   ├── scrapy_crawler/          # Scrapy 爬虫模块
│   │   ├── manager.py           # Scrapy 抓取管理器
│   │   ├── spiders/             # Spider 定义
│   │   ├── middlewares.py       # 反爬虫中间件
│   │   └── pipelines.py         # 数据处理管道
│   ├── processor/               # 处理模块
│   │   ├── content_extractor.py # 智能内容提取器
│   │   ├── html_cleaner.py      # HTML 清洗
│   │   ├── ai_summarizer.py     # AI 摘要
│   │   ├── ai_provider.py       # AI 服务封装
│   │   └── pipeline.py          # 处理流水线
│   ├── insight/                 # 🆕 每日洞察模块
│   │   ├── daily_insight_generator.py  # AI 二次炼金
│   │   └── cli.py               # 独立 CLI
│   ├── report/                  # 🆕 报告生成模块
│   │   └── report_generator.py  # 报告生成器
│   ├── generator/               # 配置生成模块
│   │   └── config_generator.py  # AI 自动生成站点配置
│   ├── notifier/                # 输出模块
│   │   ├── readme_updater.py    # README 更新器
│   │   └── terminal_display.py  # 终端显示
│   └── test/                    # 测试模块
├── output/                      # 输出目录
│   ├── report/                  # 每日生成的报告
│   │   └── YYYY/MM/DD/          # 按日期分层（含 insight 和 report）
│   ├── cache/                   # 抓取缓存
│   └── dedup_cache/             # 跨日去重缓存
└── templates/                   # 报告模板
```

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
