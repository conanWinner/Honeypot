"""Giả Nạn API. One process: agent, library, and the moderation queue."""

import logging
import threading
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


def _backfill(factory, provider) -> None:
    if provider.is_mock:
        return

    def run() -> None:
        try:
            with factory() as session:
                count = backfill_embeddings(session, provider)
                session.commit()
            if count:
                log.info("Đã gắn embedding cho %s kịch bản.", count)
        except Exception:
            log.warning("Chưa gắn được embedding. Tìm theo từ khóa vẫn chạy.", exc_info=True)

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
            session.commit()
        _backfill(factory, app.state.provider)
        yield
        engine.dispose()

    app = FastAPI(
        title="Giả Nạn",
        version="1.0.0",
        summary="Nền tảng bóc kịch bản lừa đảo: agent đóng vai nạn nhân và giữ cuộc thoại.",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router, prefix="/api")

    @app.exception_handler(LLMError)
    async def llm_error(_request, exc: LLMError):
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=502, content={"detail": f"Mô hình không phản hồi. {exc}"})

    return app


app = create_app()
