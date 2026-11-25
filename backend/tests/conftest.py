import os
import tempfile

_fd, _PATH = tempfile.mkstemp(prefix="gianan-", suffix=".sqlite")
os.close(_fd)
os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{_PATH}"
os.environ["LLM_PROVIDER"] = "mock"
os.environ["GEMINI_API_KEY"] = ""
os.environ["OPENAI_API_KEY"] = ""
os.environ["ADMIN_TOKEN"] = ""

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_app

get_settings.cache_clear()


@pytest.fixture(scope="session")
def app():
    application = create_app()
    with TestClient(application) as client:
        application.state.client = client
        yield application


@pytest.fixture(scope="session")
def client(app):
    return app.state.client


@pytest.fixture(autouse=True)
def _clean(app):
    yield
    from app.models import Conversation, Message, Script, TurnLog

    with app.state.Session() as session:
        session.query(TurnLog).delete()
        session.query(Message).delete()
        session.query(Conversation).delete()
        session.query(Script).filter(Script.status != "published").delete()
        session.commit()
