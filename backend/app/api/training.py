"""Practice-simulation routes. They never create scripts or indicators."""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.services.training import (
    TrainingError,
    build_quiz,
    create_training_session,
    list_scenarios,
    post_training_action,
    post_training_hint,
    post_training_message,
    session_public,
    training_debrief,
    _load,
    _script,
)

router = APIRouter(tags=["training"])


def get_db(request: Request):
    session = request.app.state.Session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _run(action):
    try:
        return action()
    except TrainingError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.detail) from exc


class SessionIn(BaseModel):
    script_id: str | None = None
    group: str | None = None
    difficulty: str = "vua"
    mode: str = "thu_thach"


class MessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=500)


class ActionIn(BaseModel):
    action: str


@router.get("/training/scenarios")
def scenarios(group: str = "", session=Depends(get_db)):
    return _run(lambda: list_scenarios(session, group.strip()))


@router.get("/training/quiz")
def quiz(n: int = 8, session=Depends(get_db)):
    return build_quiz(session, n)


@router.post("/training/sessions")
def open_session(body: SessionIn, session=Depends(get_db)):
    return _run(
        lambda: create_training_session(
            session,
            script_id=(body.script_id or "").strip() or None,
            group=(body.group or "").strip() or None,
            difficulty=body.difficulty,
            mode=body.mode,
        )
    )


@router.get("/training/sessions/{session_id}")
def read_session(session_id: str, session=Depends(get_db)):
    def load():
        row = _load(session, session_id)
        return session_public(row, _script(session, row.script_id))

    return _run(load)


@router.post("/training/sessions/{session_id}/messages")
def send_message(session_id: str, body: MessageIn, request: Request, session=Depends(get_db)):
    return _run(lambda: post_training_message(session, request.app.state.provider, session_id, body.text))


@router.post("/training/sessions/{session_id}/action")
def send_action(session_id: str, body: ActionIn, session=Depends(get_db)):
    return _run(lambda: post_training_action(session, session_id, body.action))


@router.post("/training/sessions/{session_id}/hint")
def send_hint(session_id: str, session=Depends(get_db)):
    return _run(lambda: post_training_hint(session, session_id))


@router.get("/training/sessions/{session_id}/debrief")
def debrief(session_id: str, session=Depends(get_db)):
    return _run(lambda: training_debrief(session, session_id))
