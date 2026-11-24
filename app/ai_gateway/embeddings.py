import math
from typing import Any

from app.config import settings


class OpenAIEmbeddingClient:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        dims: int | None = None,
        batch_size: int = 50,
    ) -> None:
        resolved_api_key = api_key or (
            settings.OPENAI_API_KEY.get_secret_value()
            if settings.OPENAI_API_KEY is not None
            else None
        )
        if not resolved_api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        if batch_size < 1:
            raise ValueError("batch_size must be greater than zero")
        resolved_dims = dims if dims is not None else settings.EMBEDDING_DIMS
        if resolved_dims < 1:
            raise ValueError("dims must be greater than zero")

        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(api_key=resolved_api_key)
        self.model = model or settings.OPENAI_EMBEDDING_MODEL
        self.dims = resolved_dims
        self.batch_size = batch_size

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return await self._embed(texts)

    async def embed_query(self, text: str) -> list[float]:
        embeddings = await self._embed([text])
        return embeddings[0]

    async def _embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        vectors: list[list[float]] = []

        for start in range(0, len(texts), self.batch_size):
            batch = texts[start : start + self.batch_size]
            response: Any = await self._client.embeddings.create(
                model=self.model,
                input=batch,
                dimensions=self.dims,
            )
            embeddings = response.data
            if len(embeddings) != len(batch):
                raise RuntimeError(
                    "OpenAI returned an unexpected number of embeddings "
                    f"(expected {len(batch)})"
                )

            for embedding in sorted(embeddings, key=lambda item: item.index):
                values = [float(value) for value in embedding.embedding]
                if len(values) != self.dims:
                    raise RuntimeError(
                        f"OpenAI returned {len(values)} dimensions; expected {self.dims}"
                    )
                norm = math.sqrt(sum(value * value for value in values))
                if norm == 0:
                    raise RuntimeError("OpenAI returned a zero-length embedding")
                vectors.append([value / norm for value in values])

        return vectors
