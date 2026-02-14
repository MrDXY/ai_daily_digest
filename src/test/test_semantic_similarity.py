import unittest
import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.core.semantic_similarity import SemanticSimilarity

try:
    from fastembed import TextEmbedding
except ImportError:
    TextEmbedding = None

from src.core.config import AppConfig
from src.core.models import Article
from src.notifier.report_generator import ReportGenerator


class SemanticTestCase(unittest.TestCase):
    def setUp(self) -> None:
        config = AppConfig()
        config.digest.semantic_dedup_enabled = True
        config.digest.semantic_threshold = 0.8
        self.generator = ReportGenerator(config)
        self._semantic = SemanticSimilarity(
            backend="fastembed",
            model_name="BAAI/bge-small-en",
            enabled= True,
        )

    def test_semantic_dedup_for_similar_articles(self) -> None:
        if TextEmbedding is None:
            self.skipTest("fastembed not installed")

        articles = [
            "文章指出“LLM 编码能力”的瓶颈不只在模型本身，更常见的是编码代理（harness）里的"
            "编辑工具/编辑格式设计。作者在自己的开源 coding agent harness（oh-my-pi，基于 Pi）中"
            "仅替换了编辑工具为“Hashline”格式，就在 16 个模型的真实文件修复基准上让 15 个模型"
            "的成功率显著提升，并通常节省 20–30% tokens。基准结果显示：传统 patch/diff 对多数"
            "非特化模型失败率高，而 Hashline 通过给每行加短哈希锚点，减少对“精确复述旧文本”的"
            "依赖，从而显著降低机械性编辑失败。",

            "文章指出“LLM 编码能力差异”常被高估，真正的瓶颈往往在编码代理/IDE 的编辑执行"
            "层（harness）与编辑格式上，而不是模型本身。作者在自研开源代理 oh-my-pi 中仅替换"
            "了编辑工具/格式，引入按行短哈希标记的 Hashline，使 16 个模型在真实编辑任务基准上"
            "普遍显著提分并减少 token 消耗。基准结果显示 Hashline 在 14/16 模型上优于 patch，且"
            "通常节省 20–30% tokens，弱模型收益尤其大（如 Grok Code Fast 1 从 6.7% 提升到 68.3%）。",
        ]

        articles2 = [
            "No",
            "slime is an LLM post-training framework for RL Scaling.",
        ]


        semantic_score = asyncio.run(self._semantic.similarity(
            articles2[0],
            articles2[1]
        ))
        print("semantic score = ", semantic_score)


if __name__ == "__main__":
    unittest.main()
