import hashlib
import math
import re

from google import genai

from app.core.config import Settings
from app.domain.errors import DomainError
from app.domain.model_contracts import EmbeddingRequest, EmbeddingResult
from app.domain.ports import EmbeddingModelPort


_TOKEN = re.compile(r"[A-Za-z0-9_]{2,}|[\u4e00-\u9fff]{2,}")
_DIMENSIONS = 768


class FakeEmbeddingModelAdapter(EmbeddingModelPort):
    """Stable local embeddings keep pgvector retrieval runnable without a cloud key."""

    def embed(self, request: EmbeddingRequest) -> EmbeddingResult:
        vector = [0.0] * _DIMENSIONS
        for token in _TOKEN.findall(request.text.lower()):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % _DIMENSIONS
            vector[index] += 1.0 if digest[4] & 1 else -1.0
        norm = math.sqrt(sum(item * item for item in vector))
        if norm:
            vector = [item / norm for item in vector]
        return EmbeddingResult(provider="fake", model="fake-embedding-v1", vector=vector)


class GeminiEmbeddingModelAdapter(EmbeddingModelPort):
    def __init__(self, api_key: str, model: str) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model

    def embed(self, request: EmbeddingRequest) -> EmbeddingResult:
        try:
            response = self._client.models.embed_content(model=self._model, contents=request.text)
            vector = list(response.embeddings[0].values)
        except Exception as exc:
            raise DomainError("MODEL_UNAVAILABLE", "Gemini Embedding 调用不可用") from exc
        if len(vector) != _DIMENSIONS:
            raise DomainError("MODEL_SCHEMA_INVALID", "Embedding 向量维度与 pgvector 索引不兼容")
        return EmbeddingResult(provider="gemini", model=self._model, vector=vector)


def create_embedding_model(settings: Settings) -> EmbeddingModelPort:
    if settings.embedding_provider == "fake":
        return FakeEmbeddingModelAdapter()
    if settings.embedding_provider != "gemini":
        raise DomainError("MODEL_NOT_CONFIGURED", "未知的 Embedding 提供方")
    if not settings.gemini_api_key:
        raise DomainError("MODEL_NOT_CONFIGURED", "Gemini Embedding 尚未配置 API Key")
    return GeminiEmbeddingModelAdapter(settings.gemini_api_key, settings.embedding_model)
