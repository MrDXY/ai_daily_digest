"""
Semantic similarity helper using embeddings.
"""

import logging
import os
import shutil
from pathlib import Path
from typing import Any, Optional

import httpx

try:
    from fastembed import TextEmbedding
except ImportError:  # pragma: no cover - optional dependency
    TextEmbedding = None


logger = logging.getLogger(__name__)


class SemanticSimilarity:
    def __init__(
        self,
        backend: str,
        model_name: str,
        enabled: bool = True,
        threshold: float = 0.86,
        max_text_length: int = 1200,
        api_key: str = "",
        api_base: str = "",
        api_version: str = "",
        deployment: str = "",
    ) -> None:
        self.backend = backend
        self.model_name = model_name
        self.enabled = enabled
        self.threshold = threshold
        self.max_text_length = max_text_length
        self.api_key = api_key
        self.api_base = api_base.rstrip("/") if api_base else ""
        self.api_version = api_version
        self.deployment = deployment
        self._embedder: Optional[Any] = None
        self._client: Optional[httpx.AsyncClient] = None
        self._warned_missing = False
        self._warned_fastembed_failure = False
        self._fastembed_retry_done = False

    def _fastembed_cache_root(self) -> Path:
        # fastembed 默认缓存：$FASTEMBED_CACHE_PATH 或系统临时目录下 fastembed_cache
        override = os.environ.get("FASTEMBED_CACHE_PATH") or os.environ.get("FASTEMBED_CACHE_DIR")
        if override:
            return Path(override)
        tmp = os.environ.get("TMPDIR") or "/tmp"
        return Path(tmp) / "fastembed_cache"

    def _safe_clear_fastembed_model_cache(self) -> bool:
        """Best-effort 清理当前模型缓存，避免残缺下载导致的 NO_SUCHFILE。"""
        try:
            root = self._fastembed_cache_root()
            if not root.exists():
                return False

            # fastembed 通常用 huggingface 风格目录：models--ORG--NAME
            safe_model_dir = "models--" + self.model_name.replace("/", "--")
            target = root / safe_model_dir
            if target.exists() and target.is_dir():
                shutil.rmtree(target, ignore_errors=True)
                return True
            return False
        except Exception as exc:  # pragma: no cover
            logger.debug(f"Failed to clear fastembed cache: {exc}")
            return False

    def _disable_semantic_dedup(self, reason: str) -> None:
        self.enabled = False
        if not self._warned_fastembed_failure:
            logger.warning(f"Semantic dedup disabled: {reason}")
            self._warned_fastembed_failure = True

    def _load_fastembed(self) -> Optional[Any]:
        if not self.enabled:
            return None
        if TextEmbedding is None:
            if not self._warned_missing:
                logger.warning("fastembed is not installed; semantic dedup disabled")
                self._warned_missing = True
            return None

        if self._embedder is not None:
            return self._embedder

        # fastembed 第一次初始化时可能因为缓存残缺导致 onnx 文件缺失（NO_SUCHFILE）。
        # 这里做一次清缓存重试，仍失败则直接降级禁用语义去重。
        try:
            self._embedder = TextEmbedding(model_name=self.model_name)
            return self._embedder
        except Exception as exc:
            if not self._fastembed_retry_done:
                self._fastembed_retry_done = True
                cleared = self._safe_clear_fastembed_model_cache()
                logger.warning(
                    "fastembed init failed (%s). cache_cleared=%s. retrying once...",
                    exc,
                    cleared,
                )
                try:
                    self._embedder = TextEmbedding(model_name=self.model_name)
                    return self._embedder
                except Exception as exc2:
                    self._disable_semantic_dedup(f"fastembed init failed after retry: {exc2}")
                    return None

            self._disable_semantic_dedup(f"fastembed init failed: {exc}")
            return None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    def _prepare_text(self, text: str) -> str:
        if not text:
            return ""
        cleaned = " ".join(text.split())
        return cleaned[: self.max_text_length]

    async def embed(self, text: str) -> Optional[list[float]]:
        if not self.enabled:
            return None
        prepared = self._prepare_text(text)
        if not prepared:
            return None

        if self.backend == "fastembed":
            embedder = self._load_fastembed()
            if embedder is None:
                return None
            try:
                vector = next(iter(embedder.embed([prepared])), None)
            except Exception as exc:
                # 这里常见是 ONNXRuntimeError / 文件缺失 / 模型损坏
                self._disable_semantic_dedup(f"fastembed embed failed: {exc}")
                return None
            if vector is None:
                return None
            return self._normalize_vector(list(vector))

        if self.backend in ("openai", "azure_openai"):
            vector = await self._embed_remote(prepared)
            return self._normalize_vector(vector) if vector else None

        return None

    async def _embed_remote(self, text: str) -> Optional[list[float]]:
        if not self.api_key:
            logger.warning("Semantic embedding API key missing; semantic dedup disabled")
            return None

        client = await self._get_client()
        headers = {}
        url = ""
        payload = {"input": text}

        if self.backend == "openai":
            headers["Authorization"] = f"Bearer {self.api_key}"
            url = (self.api_base or "https://api.openai.com") + "/v1/embeddings"
            payload["model"] = self.model_name
        elif self.backend == "azure_openai":
            if not self.api_base or not self.api_version or not self.deployment:
                logger.warning("Azure OpenAI embedding config missing; semantic dedup disabled")
                return None
            headers["api-key"] = self.api_key
            url = (
                f"{self.api_base}/openai/deployments/{self.deployment}/embeddings"
                f"?api-version={self.api_version}"
            )
        else:
            return None

        try:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            vector = data.get("data", [{}])[0].get("embedding")
            if not vector:
                return None
            return vector
        except Exception as exc:
            logger.warning(f"Semantic embedding request failed: {exc}")
            return None

    async def similarity(
        self,
        text: str,
        other_text: str,
        embedding: Optional[list[float]] = None,
        other_embedding: Optional[list[float]] = None,
    ) -> Optional[float]:
        if not self.enabled:
            return None
        if embedding is None:
            embedding = await self.embed(text)
        if other_embedding is None:
            other_embedding = await self.embed(other_text)
        if embedding is None or other_embedding is None:
            return None
        return self._dot(embedding, other_embedding)

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @staticmethod
    def _normalize_vector(vector: list[float]) -> list[float]:
        if not vector:
            return vector
        norm = sum(x * x for x in vector) ** 0.5
        if norm == 0.0:
            return vector
        return [x / norm for x in vector]

    @staticmethod
    def _dot(a: list[float], b: list[float]) -> float:
        return sum(x * y for x, y in zip(a, b))
