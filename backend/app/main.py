from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.infrastructure.idempotency import abort, complete, replay_or_reserve


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Keep startup side-effect free; migrations are an explicit operation."""

    yield


settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "If-Match"],
)


@app.middleware("http")
async def idempotency_middleware(request, call_next):
    reserved = await replay_or_reserve(request)
    if reserved is None:
        return await call_next(request)
    if not isinstance(reserved, tuple):
        return reserved
    record, request_hash = reserved
    try:
        response = await call_next(request)
        body = b"".join([chunk async for chunk in response.body_iterator])
        return complete(record.id, request_hash, response, body)
    except Exception:
        abort(record.id, request_hash)
        raise


app.include_router(api_router)
