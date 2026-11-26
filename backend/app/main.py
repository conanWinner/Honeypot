"""Honeypot API. One process: the Giả Nạn victim agent, the library, and the moderation queue."""

import logging
import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import Settings, get_settings
from app.database import init_database, make_engine, make_session_factory
from app.llm.base import LLMError
from app.llm.factory import build_provider
from app.services.library import backfill_embeddings, seed

log = logging.getLogger("gianan")


def _warm_llm(provider, background: bool) -> dict:
    """One short router ping so the first real turn does not pay the cold start."""
    report = {"ok": True, "mock": bool(provider.is_mock), "latency_ms": 0, "model": getattr(provider, "model", ""), "error": "", "warming": background}

    def run() -> None:
        started = time.perf_counter()
        try:
            from app.agent.schemas import PersonaOutput

            provider.complete(PersonaOutput, "Trả một JSON ngắn.", "ping", 0, role="persona", max_tokens=16, timeout=8)
            report["ok"] = True
            report["error"] = ""
        except Exception as exc:  # noqa: BLE001
            report["ok"] = False
            report["error"] = str(exc)[:180]
        report["latency_ms"] = int((time.perf_counter() - started) * 1000)
        report["model"] = getattr(provider, "model", "")
        report["warming"] = False

    if not background:
        return report
    threading.Thread(target=run, name="llm-warmup", daemon=True).start()
    return report


def _backfill(factory, provider) -> None:
    if provider.is_mock or getattr(provider, "embeddings_mock", False):
        return

    def run() -> None:
        try:
            with factory() as session:
                count = backfill_embeddings(session, provider)
                session.commit()
            if count:
                log.info("Đã gắn embedding cho %s kịch bản.", count)
        except Exception as exc:
            from app.llm.gemini import note_embed_failure

            note_embed_failure(exc, "Chưa gắn được embedding. Tìm theo từ khóa vẫn chạy.")

    threading.Thread(target=run, name="embed-backfill", daemon=True).start()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO), format="%(message)s")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine = make_engine(settings.database_url)
        init_database(engine)
        factory = make_session_factory(engine)
        app.state.engine = engine
        app.state.Session = factory
        app.state.provider = build_provider(settings)
        with factory() as session:
            seed(session)
            from app.services.training import purge_old_sessions

            purge_old_sessions(session)
            session.commit()
        _backfill(factory, app.state.provider)
        app.state.llm_health = _warm_llm(app.state.provider, background=not app.state.provider.is_mock)
        yield
        engine.dispose()

    app = FastAPI(
        title="Honeypot",
        version="1.0.0",
        summary="Honeypot — AI đóng vai nạn nhân, bóc kịch bản lừa đảo. Vai Giả Nạn giữ cuộc thoại.",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    from app.api.training import router as training_router

    app.include_router(router, prefix="/api")
    app.include_router(training_router, prefix="/api")

    @app.exception_handler(LLMError)
    async def llm_error(_request, exc: LLMError):
        from fastapi.responses import JSONResponse

        log.warning("LLM lỗi, không trả nội dung upstream: %s", type(exc).__name__)
        return JSONResponse(status_code=503, content={"detail": "Mô hình đang bận. Thử lại sau."})

    return app


app = create_app()
