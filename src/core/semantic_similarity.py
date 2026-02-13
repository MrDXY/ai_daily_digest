"""
Semantic similarity helper using embeddings.
"""

import logging
from typing import Optional

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
        self._embedder: Optional[TextEmbedding] = None
        self._client: Optional[httpx.AsyncClient] = None
        self._warned_missing = False

    def _load_fastembed(self) -> Optional[TextEmbedding]:
        if not self.enabled:
            return None
        if TextEmbedding is None:
            if not self._warned_missing:
                logger.warning("fastembed is not installed; semantic dedup disabled")
                self._warned_missing = True
            return None
        if self._embedder is None:
            self._embedder = TextEmbedding(model_name=self.model_name)
        return self._embedder

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
            vector = next(iter(embedder.embed([prepared])), None)
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

