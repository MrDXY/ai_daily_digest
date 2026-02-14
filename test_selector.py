import unittest
import asyncio

try:
    from fastembed import TextEmbedding
except ImportError:
    TextEmbedding = None

from src.core.config import AppConfig
from src.core.models import Article
from src.notifier.report_generator import ReportGenerator


class DedupTestCase(unittest.TestCase):
    def setUp(self) -> None:
        config = AppConfig()
        config.digest.semantic_dedup_enabled = True
        config.digest.semantic_backend = "fastembed"
        config.digest.semantic_threshold = 0.8
        self.generator = ReportGenerator(config)

    def test_semantic_dedup_for_similar_articles(self) -> None:
        if TextEmbedding is None:
            self.skipTest("fastembed not installed")

        articles = [
            Article(
                id="e8256639-ee13-48d6-ac22-6361b1e558d1",
                title="I Improved 15 LLMs at Coding in One Afternoon. Only the Harness Changed",
                url="https://blog.can.ac/2026/02/12/the-harness-problem/",
                source="Lobsters",
                summary=(
                    "文章指出“LLM 编码能力”的瓶颈不只在模型本身，更常见的是编码代理（harness）里的"
                    "编辑工具/编辑格式设计。作者在自己的开源 coding agent harness（oh-my-pi，基于 Pi）中"
                    "仅替换了编辑工具为“Hashline”格式，就在 16 个模型的真实文件修复基准上让 15 个模型"
                    "的成功率显著提升，并通常节省 20–30% tokens。基准结果显示：传统 patch/diff 对多数"
                    "非特化模型失败率高，而 Hashline 通过给每行加短哈希锚点，减少对“精确复述旧文本”的"
                    "依赖，从而显著降低机械性编辑失败。"
                ),
                core_value=(
                    "用一种轻量、可验证的“行级哈希锚点”编辑协议（Hashline）解决了 LLM 在代码编辑中"
                    "常见的对齐/定位不稳定问题，把大量失败从“模型不懂”纠正为“工具表达不稳”。证明了"
                    "改 harness/编辑接口能带来堪比甚至超过模型升级的收益，且无需训练成本。"
                ),
                tech_stack=[
                    "LLM Coding Agent/Harness",
                    "代码编辑协议（apply_patch/str_replace/Hashline）",
                    "基准测试与评测（pass@1/多轮运行）",
                    "React 代码库（任务夹具来源）",
                    "Diff/patch 工具链",
                    "Rust（N-API，文中提及）",
                ],
                recommendation=(
                    "如果你在做 IDE/Agent/自动修复工具，这篇文章提供了可直接落地的接口改造思路："
                    "用稳定锚点替代“复述旧内容”的编辑方式，显著提升跨模型鲁棒性并降低 token 浪费。"
                    "它也提醒评测与产品优化应把“harness 变量”纳入核心关注点，而不是只追逐更强模型。"
                ),
                score=88.0,
                stars=None,
                language=None,
            ),
            Article(
                id="17f230e9-8b6a-407a-b764-26f49fb5a98b",
                title="Improving 15 LLMs at Coding in One Afternoon. Only the Harness Changed",
                url="http://blog.can.ac/2026/02/12/the-harness-problem/",
                source="Hacker News",
                summary=(
                    "文章指出“LLM 编码能力差异”常被高估，真正的瓶颈往往在编码代理/IDE 的编辑执行"
                    "层（harness）与编辑格式上，而不是模型本身。作者在自研开源代理 oh-my-pi 中仅替换"
                    "了编辑工具/格式，引入按行短哈希标记的 Hashline，使 16 个模型在真实编辑任务基准上"
                    "普遍显著提分并减少 token 消耗。基准结果显示 Hashline 在 14/16 模型上优于 patch，且"
                    "通常节省 20–30% tokens，弱模型收益尤其大（如 Grok Code Fast 1 从 6.7% 提升到 68.3%）。"
                ),
                core_value=(
                    "用“可验证的行级锚点（短哈希）”替代依赖精确复现旧文本的 patch/replace，从机制"
                    "上降低编辑失败与重试循环，让模型的真实编码能力不再被编辑协议吞噬。证明了改 harness"
                    "（编辑接口/格式）可以带来接近甚至超过模型升级的收益，且无需训练成本。"
                ),
                tech_stack=[
                    "LLM Coding Agent/IDE Harness",
                    "代码编辑协议（apply_patch/str_replace）",
                    "Hashline（行级内容哈希锚点）",
                    "Benchmarking/评测框架",
                    "React 代码库任务构造",
                    "Rust",
                    "Node.js N-API",
                    "ripgrep（rg）",
                ],
                recommendation=(
                    "对做 AI 编码产品/代理的人非常有参考价值：它把“编辑落地”从模型问题拆出来，用"
                    "低成本的协议设计显著提升成功率并降 token。文中给出可复现的评测思路与跨模型对比，"
                    "能直接指导你改造工具调用、错误处理与状态管理等 harness 关键环节。"
                ),
                score=88.0,
                stars=None,
                language=None,
            ),
        ]

        deduped = asyncio.run(self.generator._deduplicate_articles(articles, history_cache=None))

        # fastembed 需要首次下载模型；如果本机网络/权限导致模型缺失，会自动降级禁用语义去重。
        # 这种情况下 dedup 结果可能是 2（仅靠字符/词集合规则未必命中），这里跳过断言，避免测试不稳定。
        if not getattr(self.generator._semantic, "enabled", True):
            self.skipTest("fastembed model unavailable on this machine; semantic dedup disabled")

        self.assertEqual(len(deduped), 1)


if __name__ == "__main__":
    unittest.main()
