import hashlib
import json
import math
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

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


class DashScopeEmbeddingModelAdapter(EmbeddingModelPort):
    """Bounded OpenAI-compatible adapter for Alibaba Cloud Model Studio embeddings."""

    def __init__(self, api_key: str, model: str, base_url: str) -> None:
        parsed = urlparse(base_url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise DomainError("MODEL_NOT_CONFIGURED", "百炼 Embedding 地址必须是 HTTPS URL")
        self._api_key = api_key
        self._model = model
        self._endpoint = f"{base_url.rstrip('/')}/embeddings"

    def embed(self, request: EmbeddingRequest) -> EmbeddingResult:
        payload = {
            "model": self._model,
            "input": request.text,
            "dimensions": _DIMENSIONS,
            "encoding_format": "float",
        }
        http_request = Request(
            self._endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(http_request, timeout=30) as response:
                body = json.loads(response.read().decode("utf-8"))
            vector = body["data"][0]["embedding"]
        except (KeyError, IndexError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DomainError("MODEL_SCHEMA_INVALID", "百炼 Embedding 返回格式无效") from exc
        except HTTPError as exc:
            raise DomainError("MODEL_UNAVAILABLE", f"百炼 Embedding 调用失败（HTTP {exc.code}）") from exc
        except (URLError, TimeoutError) as exc:
            raise DomainError("MODEL_UNAVAILABLE", "百炼 Embedding 当前不可用") from exc
        if (
            not isinstance(vector, list)
            or len(vector) != _DIMENSIONS
            or not all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in vector)
        ):
            raise DomainError("MODEL_SCHEMA_INVALID", "Embedding 向量维度或数据类型与 pgvector 索引不兼容")
        return EmbeddingResult(provider="dashscope", model=self._model, vector=[float(value) for value in vector])


def embedding_index_version(parser_version: str, result: EmbeddingResult) -> str:
    return f"{parser_version}|embedding:{result.provider}:{result.model}:d{len(result.vector)}"


def create_embedding_model(settings: Settings) -> EmbeddingModelPort:
    if settings.embedding_provider == "dashscope":
        if not settings.dashscope_api_key:
            raise DomainError("MODEL_NOT_CONFIGURED", "百炼 Embedding 尚未配置 API Key")
        return DashScopeEmbeddingModelAdapter(
            settings.dashscope_api_key,
            settings.dashscope_embedding_model,
            settings.dashscope_base_url,
        )
    if settings.embedding_provider == "gemini":
        if not settings.gemini_api_key:
            raise DomainError("MODEL_NOT_CONFIGURED", "Gemini Embedding 尚未配置 API Key")
        return GeminiEmbeddingModelAdapter(settings.gemini_api_key, settings.gemini_embedding_model)
    raise DomainError("MODEL_NOT_CONFIGURED", "未知的 Embedding 提供方")
