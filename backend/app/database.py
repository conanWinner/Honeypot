"""Engine setup. Postgres gets the pgvector column; SQLite is for tests only."""

import logging

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool

log = logging.getLogger("gianan.db")


class Base(DeclarativeBase):
    pass


def normalize_database_url(url: str) -> str:
    """Render and Railway hand out postgres:// URLs. SQLAlchemy needs the psycopg driver."""
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]
    if url.startswith("postgresql://") and "+" not in url.split("://", 1)[0]:
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


def make_engine(url: str):
    url = normalize_database_url(url)
    kwargs: dict = {"future": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        if ":memory:" in url or "mode=memory" in url:
            kwargs["poolclass"] = StaticPool
    return create_engine(url, **kwargs)


def make_session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def _ensure_column(engine, table: str, column: str, ddl: str) -> None:
    from sqlalchemy import inspect

    try:
        names = {item["name"] for item in inspect(engine).get_columns(table)}
    except Exception:
        return
    if column in names:
        return
    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))


def init_database(engine) -> None:
    from app import models  # noqa: F401

    if engine.dialect.name == "postgresql":
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(engine)
    _ensure_column(engine, "scripts", "indicators", "JSON")
    _ensure_column(engine, "scripts", "relation", "VARCHAR(16) DEFAULT ''")
    _ensure_column(engine, "scripts", "merge_target", "VARCHAR(64)")
    if engine.dialect.name != "postgresql":
        return
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE scripts ADD COLUMN IF NOT EXISTS embedding_vec vector(768)"))
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_scripts_embedding_hnsw "
                    "ON scripts USING hnsw (embedding_vec vector_cosine_ops)"
                )
            )
    except Exception:
        log.warning("Bỏ qua chỉ mục HNSW, tìm gần đúng vẫn chạy bằng quét vector.", exc_info=True)
