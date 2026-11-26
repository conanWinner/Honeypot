"""Re-embed every library script with the configured embedding model.

    cd backend && python -m app.reembed          # only rows from another model or missing
    cd backend && python -m app.reembed --all    # clear and re-embed everything
"""

import sys

from app.config import get_settings
from app.database import init_database, make_engine, make_session_factory
from app.llm.factory import build_provider
from app.services.library import backfill_embeddings, embedding_marker


def main(argv: list[str]) -> int:
    settings = get_settings()
    provider = build_provider(settings)
    if getattr(provider, "embeddings_mock", True):
        print("Chưa cấu hình embedding (EMBED_PROVIDER / khóa router).")
        return 1
    engine = make_engine(settings.database_url)
    init_database(engine)
    factory = make_session_factory(engine)
    with factory() as session:
        before = embedding_marker(session) or "(chưa có)"
        count = backfill_embeddings(session, provider, force="--all" in argv)
        session.commit()
    print(f"Model cũ: {before}. Model mới: {provider.embed_model}. Đã gắn embedding cho {count} kịch bản.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
