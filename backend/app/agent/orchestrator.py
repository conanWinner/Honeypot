"""Four-node loop for one scammer turn.

Order: inbound safety (rules) -> analyst (model) -> planner (model) -> persona (model)
-> outbound safety (rules have veto, model may rewrite). Wrap is decided in code
from the match history so the model cannot end the script on the opening.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from datetime import datetime, timezone

from app.agent.casefile import (
    STAGE_LABELS,
    checklist_signature,
    choose_stage,
    clamp_new_branch,
    stabilize_branch,
    critique_reply,
    cue_branch,
    forced_ask,
    next_gap,
    note_progress,
    stabilize_family,
    update_casefile,
)
from app.agent.policy import (
    VIOLATION_LABELS,
    assess_inbound,
    fallback_reply,
    contains_guard_subject,
    holding_line,
    inspect_outbound,
    soft_hints,
    is_extraction_ask,
    needs_guard,
    pin_address,
    remember_address,
    repair_pronouns,
    recommend_wrap,
    repeats_opening,
    rewrite_opening,
    typing_ms,
    with_fake_otp,
)
from app.agent.prompts import ANALYST_SYSTEM, PERSONA_SYSTEM, PLANNER_SYSTEM, SAFETY_SYSTEM
from app.data.playbooks import next_unasked, playbook_state
from app.agent.schemas import AnalystOutput, BranchOut, MatchOut, PersonaOutput, PlannerOutput, SafetyOutput
from app.agent.state import AgentState, MatchSnap
from app.agent.textutil import digit_runs
from app.data.personas import PRONOUNS
from app.models import Message, TurnLog
from app.llm.base import LLMError
from app.services.matching import branch_hint, candidate_payload, script_blob, search_scripts, settle_new_branch
from app.taxonomy import GOALS

log = logging.getLogger("gianan.agent")

_HARD_VIOLATIONS = {
    "agreed_to_pay",
    "agreed_to_install",
    "agreed_to_share_otp",
    "committed_act",
    "ai_admission",
    "harmful_assistance",
    "expert_shutdown",
    "unknown_number",
}
_guard_retries: dict[str, dict] = {}


def _hard(issues: list[str]) -> list[str]:
    return [item for item in issues if item in _HARD_VIOLATIONS]


def _retry_guard_later(provider, conversation_id: str, safety_ctx: dict) -> None:
    """One background retry. The next turn can show the verdict; this turn already held."""
    if getattr(provider, "is_mock", True):
        return

    def run() -> None:
        try:
            caps = getattr(provider, "role_timeouts", {}) or {}
            alts = getattr(provider, "role_fallback_timeouts", {}) or {}
            verdict = provider.complete(
                SafetyOutput,
                SAFETY_SYSTEM,
                pack("Duyệt câu trả lời trước khi gửi.", safety_ctx),
                0.1,
                role="guard",
                max_tokens=220,
                timeout=float(caps.get("guard") or 9),
                fallback_timeout=float(alts.get("guard") or 7),
            )
            _guard_retries[conversation_id] = {
                "reply": (safety_ctx.get("reply") or "")[:240],
                "action": verdict.action,
                "approved": bool(verdict.approved),
            }
        except Exception:
            log.info("Guard thử lại vẫn không xong.")

    threading.Thread(target=run, name="guard-retry", daemon=True).start()


def pack(instruction: str, context: dict) -> str:
    return instruction.strip() + "\n\n<<<CONTEXT>>>\n" + json.dumps(context, ensure_ascii=False) + "\n<<<END>>>"


def _clamp(value) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, number))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _nid() -> str:
    return uuid.uuid4().hex[:16]


def _allowed_numbers(persona, state: AgentState) -> set[str]:
    allowed = set(state.known_numbers)
    allowed.add(state.fake_otp)
    profile = persona.fake_profile or {}
    for key in ("phone", "cccd", "bank_account", "momo"):
        digits = "".join(ch for ch in str(profile.get(key, "")) if ch.isdigit())
        if len(digits) >= 6:
            allowed.add(digits)
    return allowed


def _degraded_analyst(state: AgentState, candidates: list[dict]) -> AnalystOutput:
    last = state.match_history[-1] if state.match_history else None
    if last and last.script_id:
        match = MatchOut(
            script_id=last.script_id,
            title=last.title,
            confidence=last.confidence,
            current_step_index=last.step_index,
            current_step_intent=last.step_intent,
            reason="Giữ kịch bản của lượt trước vì phân tích chưa trả lời.",
        )
    elif candidates:
        top = candidates[0]
        match = MatchOut(
            script_id=top["script_id"],
            title=top.get("title") or "",
            confidence=float(top.get("retrieval_score") or 0),
            current_step_index=int(top.get("heuristic_step_index") or 0),
            current_step_intent="",
            reason="Giữ kết quả thư viện vì phân tích chưa trả lời.",
        )
    else:
        match = None
    return AnalystOutput(
        scammer_intent="Giữ mạch cũ.",
        step_label=match.current_step_intent if match else "",
        matches=[match] if match else [],
        notes="Phân tích chưa trả lời.",
    )


def _degraded_plan(state: AgentState) -> PlannerOutput:
    goal = state.goals_used[-1] if state.goals_used else "ask_next_instruction"
    if goal in {"close_polite", "stall", "feign_confusion", "read_fake_otp"}:
        goal = "ask_next_instruction"
    return PlannerOutput(goal=goal, rationale="Lập kế hoạch chưa trả lời. Giữ câu hỏi đang mở.")


def _family(script) -> str:
    if script is None:
        return ""
    return script.parent_id or script.id


def _step_intent(candidate: dict, index: int) -> str:
    steps = candidate.get("steps") or []
    if 0 <= index < len(steps):
        return steps[index].get("intent") or ""
    return ""


def handle_turn(session, conversation, text: str, provider) -> dict:
    started = time.perf_counter()
    persona = conversation.persona
    state = AgentState.model_validate(conversation.state)
    inbound = assess_inbound(text)
    for number in digit_runs(text):
        if number not in state.known_numbers:
            state.known_numbers.append(number)
    folded = text.lower()
    if any(token in folded for token in ("otp", "mã xác thực", "mã otp")):
        state.otp_prompts += 1

    prefer = set()
    if state.match_history:
        last = state.match_history[-1]
        prefer = {item for item in (last.script_id, last.family_id) if item}
    published = search_scripts(session, text, provider, k=6, prefer_ids=prefer)
    from app.models import Script
    from sqlalchemy import select

    all_scripts = list(session.scalars(select(Script).where(Script.status == "published")).all())
    hint = branch_hint(text, persona, published, all_scripts)
    if hint.get("kind") in ("", "none") and published:
        lead = published[0]["script"]
        root_id = lead.parent_id or lead.id
        family_blob = "\n".join(
            script_blob(script) for script in all_scripts if script.id == root_id or (script.parent_id or "") == root_id
        )
        cue = cue_branch(text, family_blob or script_blob(lead))
        if cue:
            hint = cue
    before_checklist = checklist_signature(state)
    before_iocs = {kind: list(values or []) for kind, values in (state.indicators or {}).items()}
    update_casefile(state, text)
    note_progress(state, before_checklist)
    candidates = candidate_payload(published)
    by_id = {script.id: script for script in all_scripts}

    history = [
        {"role": "scammer" if message.role == "scammer" else "victim", "content": message.content}
        for message in conversation.messages[-8:]
    ]
    analyst_ctx = {
        "message": text,
        "history": history,
        "persona_hooks": persona.hooks,
        "candidates": candidates,
        "branch_hint": hint,
        "inbound": inbound,
        "turn_index": state.turn_index,
    }
    provisional = candidates[0] if candidates else None
    provisional_branch = BranchOut.model_validate(hint)
    provisional_top = None
    if provisional:
        provisional_top = MatchOut(
            script_id=provisional["script_id"],
            title=provisional["title"],
            confidence=float(provisional["retrieval_score"]),
            current_step_index=int(provisional["heuristic_step_index"]),
            current_step_intent=_step_intent(provisional, int(provisional["heuristic_step_index"])),
            reason="Ước lượng từ thư viện, trước khi mô hình rerank.",
        )
    provisional_script = by_id.get(provisional_top.script_id) if provisional_top else None
    provisional_snap = MatchSnap(
        script_id=provisional_top.script_id if provisional_top else "",
        family_id=_family(provisional_script) if provisional_top else "",
        title=provisional_top.title if provisional_top else "",
        confidence=provisional_top.confidence if provisional_top else 0,
        step_index=provisional_top.current_step_index if provisional_top else 0,
        step_intent=provisional_top.current_step_intent if provisional_top else "",
        branch_kind=provisional_branch.kind,
    )
    provisional_wrap, _provisional_reason = recommend_wrap(state.match_history + [provisional_snap])
    planner_ctx = {
        "message": text,
        "turn_index": state.turn_index,
        "wrap_allowed": provisional_wrap,
        "branch": provisional_branch.model_dump(),
        "suspicion": _clamp(inbound["suspicion_level"]),
        "jailbreak": inbound["jailbreak"],
        "goals_used": state.goals_used,
        "otp_prompts": state.otp_prompts,
        "memory": state.memory[-6:],
        "persona_slug": persona.id,
        "top_match": provisional_top.model_dump() if provisional_top else None,
        "aggressiveness": state.aggressiveness or "normal",
        "next_gap": next_gap(state),
        "checklist": state.checklist,
        "playbook": _playbook_brief(state, provisional_script),
    }
    # Analyst and planner both only need the retrieval packet, so they run together.
    # Each role call, including repair and failover, stops at one wall-clock cap.
    # The whole turn also stops at TURN_DEADLINE.
    turn_end = time.monotonic() + float(getattr(provider, "turn_deadline", 25) or 25)
    role_caps = getattr(provider, "role_timeouts", {}) or {}
    role_alt_caps = getattr(provider, "role_fallback_timeouts", {}) or {}

    def _remaining() -> float:
        return turn_end - time.monotonic()

    def _budgets(role: str) -> tuple[float, float]:
        remaining = _remaining()
        primary = max(0.0, min(float(role_caps.get(role) or 12), remaining))
        alt_raw = role_alt_caps.get(role)
        alt = max(0.0, min(float(alt_raw), remaining)) if alt_raw else 0.0
        return primary, alt

    def _wait_for(role: str) -> float:
        primary, alt = _budgets(role)
        # Fallback can start while the primary is still running, so the wait is
        # the longer of the two clocks, not the sum, and never past the turn.
        hedge = min(5.0, primary) if alt else 0.0
        return max(0.0, min(_remaining(), max(primary, hedge + alt)))

    def _ask(schema, system, user, temperature, role, max_tokens, thinking=False):
        primary, alt = _budgets(role)
        if primary < 0.8 and alt < 0.8:
            raise LLMError("turn deadline")
        return provider.complete(
            schema,
            system,
            user,
            temperature,
            thinking,
            model=None,
            role=role,
            max_tokens=max_tokens,
            timeout=primary if primary >= 0.8 else 0.5,
            fallback_timeout=alt if alt >= 0.8 else None,
            deadline=turn_end,
        )

    t0 = time.perf_counter()
    pool = ThreadPoolExecutor(max_workers=2)
    try:
        analyst_future = pool.submit(
            _ask,
            AnalystOutput,
            ANALYST_SYSTEM,
            pack("Phân tích lượt mới nhất của đối phương.", analyst_ctx),
            0.2,
            "analyst",
            420,
        )
        planner_future = pool.submit(
            _ask,
            PlannerOutput,
            PLANNER_SYSTEM,
            pack("Chọn mục tiêu cho câu trả lời kế tiếp.", planner_ctx),
            0.3,
            "planner",
            260,
        )
        degraded = False
        try:
            analyst = analyst_future.result(timeout=max(_wait_for("analyst"), 0.05))
        except (LLMError, TimeoutError, FuturesTimeout) as exc:
            log.warning("analyst không trả lời, giữ mạch cũ: %s", type(exc).__name__)
            analyst = _degraded_analyst(state, candidates)
            degraded = True
        try:
            plan = planner_future.result(timeout=max(_wait_for("planner"), 0.05))
        except (LLMError, TimeoutError, FuturesTimeout) as exc:
            log.warning("planner không trả lời, dùng mục tiêu đang mở: %s", type(exc).__name__)
            plan = _degraded_plan(state)
            degraded = True
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    analyst_ms = int((time.perf_counter() - t0) * 1000)
    planner_ms = analyst_ms

    retrieval_by_id = {item["script_id"]: item for item in candidates}
    step_source = "model"
    kept: list[MatchOut] = []
    for match in analyst.matches:
        if match.script_id not in by_id:
            continue
        found = retrieval_by_id.get(match.script_id)
        match.confidence = _clamp(match.confidence)
        if found:
            match.confidence = round(_clamp(0.5 * match.confidence + 0.5 * float(found["retrieval_score"])), 3)
            heuristic = int(found["heuristic_step_index"])
            if match.current_step_index <= 0 and heuristic >= 2 and float(found["heuristic_step_score"]) >= 0.35:
                match.current_step_index = heuristic
                match.current_step_intent = _step_intent(found, heuristic)
                step_source = "heuristic_backstop"
            else:
                total = len(found["steps"])
                if total:
                    match.current_step_index = max(0, min(int(match.current_step_index), total - 1))
                if not match.current_step_intent:
                    match.current_step_intent = _step_intent(found, match.current_step_index)
        kept.append(match)
    if not kept and candidates:
        top = candidates[0]
        kept.append(
            MatchOut(
                script_id=top["script_id"],
                title=top["title"],
                confidence=float(top["retrieval_score"]),
                current_step_index=int(top["heuristic_step_index"]),
                current_step_intent=_step_intent(top, int(top["heuristic_step_index"])),
                reason="Giữ kết quả tìm thư viện vì mô hình không chọn id hợp lệ.",
            )
        )
        step_source = "retrieval"
    kept.sort(key=lambda item: item.confidence, reverse=True)

    if hint["kind"] in ("new", "known_variant"):
        branch = BranchOut.model_validate(hint)
    else:
        branch = analyst.branch
    if branch.kind == "new" and published:
        lead = published[0]["script"]
        root_id = lead.parent_id or lead.id
        settled = settle_new_branch(branch.kind, branch.hook, branch.detected, branch.description, text, all_scripts, root_id)
        if settled:
            branch = BranchOut.model_validate(settled)
    kind, detected = clamp_new_branch(branch.kind, branch.detected, state.turn_index)
    if kind != branch.kind or detected != branch.detected:
        branch = branch.model_copy(update={"kind": kind, "detected": detected})
    raw_branch = branch
    stable_kind, stable_variant = stabilize_branch(state, branch.kind, branch.variant_script_id)
    if stable_kind != branch.kind or (stable_kind == "known_variant" and stable_variant and stable_variant != branch.variant_script_id):
        branch = branch.model_copy(
            update={
                "kind": stable_kind,
                "detected": stable_kind != "none",
                "variant_script_id": stable_variant or branch.variant_script_id,
            }
        )
    if branch.kind == "known_variant" and branch.variant_script_id in by_id:
        variant = by_id[branch.variant_script_id]
        others = [item for item in kept if item.script_id != variant.id]
        confidence = kept[0].confidence if kept else 0.74
        lead = MatchOut(
            script_id=variant.id,
            title=variant.title,
            confidence=confidence,
            current_step_index=0,
            current_step_intent=(variant.steps or [{"intent": ""}])[0].get("intent", ""),
            reason=branch.description,
        )
        # Prefer the variant's own step if it was already retrieved.
        found = retrieval_by_id.get(variant.id)
        if found:
            lead.current_step_index = int(found["heuristic_step_index"])
            lead.current_step_intent = _step_intent(found, lead.current_step_index)
        kept = [lead, *others]

    top = kept[0] if kept else None
    top_script = by_id.get(top.script_id) if top else None
    raw_family = _family(top_script) if top_script else ""
    stable_family = stabilize_family(state, raw_family)
    if top and stable_family and stable_family != raw_family:
        previous = next(
            (item for item in reversed(state.match_history) if (item.family_id or item.script_id) == stable_family),
            None,
        )
        if previous and previous.script_id in by_id:
            top_script = by_id[previous.script_id]
            top = top.model_copy(
                update={
                    "script_id": previous.script_id,
                    "title": previous.title or top_script.title,
                    "confidence": previous.confidence,
                    "current_step_index": previous.step_index,
                    "current_step_intent": previous.step_intent,
                }
            )
    snap = MatchSnap(
        script_id=top.script_id if top else "",
        family_id=_family(top_script) if top else "",
        title=top.title if top else "",
        confidence=top.confidence if top else 0,
        step_index=top.current_step_index if top else 0,
        step_intent=top.current_step_intent if top else "",
        branch_kind=branch.kind,
    )
    wrap, wrap_reason = recommend_wrap(state.match_history + [snap])
    suspicion = max(_clamp(inbound["suspicion_level"]), _clamp(analyst.scammer_suspicion))

    goal = plan.goal
    note = plan.rationale
    if branch.kind == "new" and goal not in ("probe_hook", "feign_confusion", "stall", "emotional_hook"):
        goal = "probe_hook"
        note = f"{note} Có nhánh mới, máy chủ chuyển sang đào chi tiết."
    if goal == "close_polite" and not wrap:
        goal = "probe_hook" if branch.kind == "new" else "ask_next_instruction"
        note = f"{note} Máy chủ giữ cuộc thoại vì chưa đủ điều kiện khép."
    real_suspicion = bool(inbound["jailbreak"] or suspicion >= 0.7)
    if real_suspicion and goal not in ("feign_confusion", "emotional_hook", "stall"):
        goal = "feign_confusion"
        note = f"{note} Đối phương đang dò xem đây có phải máy. Lùi lại, hỏi họ là ai."
    gap = next_gap(state)
    from app.agent.casefile import GAP_GOAL

    if (
        not real_suspicion
        and (state.aggressiveness or "normal") == "persistent"
        and gap
        and GAP_GOAL.get(gap)
        and branch.kind == "none"
    ):
        goal = GAP_GOAL[gap]
        note = f"{note} Còn thiếu mục «{gap}» trên bảng khai thác."
    asked = forced_ask(state, suspicion, bool(inbound["jailbreak"]), branch.kind)
    if asked:
        goal = asked
        note = f"{note} Hai lượt không có thêm gì, hỏi mục còn thiếu."
    state.stage = choose_stage(state, branch.kind, wrap, suspicion)
    if top_script is not None:
        state.playbook_category = top_script.category
    book = playbook_state(state.playbook_category, state.checklist, state.indicators)
    nxt = next_unasked(book, state.asked_keys)
    who_done = any(item.get("key") == "who" and item.get("done") for item in state.checklist)
    identity_spent = who_done or "who" in state.asked_keys or state.goals_used.count("ask_identity") >= 1
    if nxt and identity_spent and goal == "ask_identity" and nxt.get("goal") != "ask_identity":
        goal = nxt["goal"]
        note = f"{note} Playbook «{book['label']}»: đã hỏi danh tính, chuyển sang «{nxt['label']}»."
    elif (
        nxt
        and not real_suspicion
        and branch.kind == "none"
        and goal in ("ask_purpose", "ask_next_instruction", "stall")
        and state.turn_index >= 1
        and goal != nxt.get("goal")
        and not asked
    ):
        goal = nxt["goal"]
        note = f"{note} Playbook «{book['label']}»: còn thiếu «{nxt['label']}»."
    repeated = next(
        (row for row in book["targets"] if row["goal"] == goal and (row["done"] or row["key"] in state.asked_keys)),
        None,
    )
    if nxt and repeated and nxt.get("goal") != goal:
        goal = nxt["goal"]
        note = f"{note} Playbook «{book['label']}»: «{repeated['label']}» đã hỏi, chuyển sang «{nxt['label']}»."
    aimed = next((row for row in book["targets"] if row["goal"] == goal and row["key"] not in state.asked_keys and not row["done"]), None)
    if aimed:
        state.asked_keys.append(aimed["key"])
    plan = plan.model_copy(update={"goal": goal, "rationale": note})

    persona_ctx = {
        "persona": {
            "id": persona.id,
            "display_name": persona.display_name,
            "age": persona.age,
            "job": persona.job,
            "city": persona.city,
            "region": persona.region,
            "texting_style": persona.texting_style,
            "bio": persona.bio,
            "fake_profile": persona.fake_profile,
            "examples": persona.examples,
            "pronouns": PRONOUNS.get(persona.id, {}),
        },
        "goal": goal,
        "goal_label": GOALS.get(goal, goal),
        "rationale": plan.rationale,
        "memory": state.memory[-8:],
        "message": text,
        "hook": branch.hook,
        "turn_index": state.turn_index,
        "fake_otp": state.fake_otp if goal == "read_fake_otp" else "",
        "otp_allowed": goal == "read_fake_otp",
        "jailbreak": inbound["jailbreak"],
        "recent_openings": [],
        "ask_hint": (aimed or {}).get("hint", "") if aimed and goal == (aimed or {}).get("goal") else "",
    }
    recent_replies = [message.content for message in conversation.messages if message.role == "victim"][-4:]
    persona_ctx["recent_openings"] = [item.strip().split("\n", 1)[0][:48] for item in recent_replies[-3:]]
    pace = state.aggressiveness or "normal"
    t0 = time.perf_counter()
    try:
        if _remaining() < 0.8:
            raise LLMError("turn deadline")
        spoken = _ask(PersonaOutput, PERSONA_SYSTEM, pack("Viết tin nhắn trả lời trong vai.", persona_ctx), 0.9, "persona", 180)
    except (LLMError, TimeoutError, FuturesTimeout) as exc:
        log.warning("persona không trả lời, câu giữ chỗ: %s", type(exc).__name__)
        spoken = PersonaOutput(reply=holding_line(persona.id, recent_replies), memory_note="")
        degraded = True
        persona_failed = True
    else:
        persona_failed = False
    persona_ms = int((time.perf_counter() - t0) * 1000)
    draft = (spoken.reply or "").strip()
    allowed = _allowed_numbers(persona, state)
    notes = critique_reply(draft, persona.id, goal, allowed, pace, recent_replies)
    if notes:
        persona_ctx["critique"] = notes
    violations = inspect_outbound(draft, allowed, persona.id)
    safety_ctx = {
        "reply": draft,
        "code_violations": violations,
        "goal": goal,
        "fake_otp": state.fake_otp,
        "jailbreak": inbound["jailbreak"],
        "scammer_suspicious": inbound["scammer_suspicious"],
        "suspicion": suspicion,
        "persona_slug": persona.id,
        "rule_hints": soft_hints(draft),
    }
    t0 = time.perf_counter()
    # The guard starts the moment the draft exists. A rewrite, if any, runs beside that
    # speculative check. A question never cancels the guard.
    guard_future = None
    rewrite_future = None
    guard_pool = ThreadPoolExecutor(max_workers=2) if not persona_failed else None
    guard_failed = False
    verdict = None
    try:
        if guard_pool is not None and _remaining() >= 0.8:
            guard_future = guard_pool.submit(
                _ask, SafetyOutput, SAFETY_SYSTEM, pack("Duyệt câu trả lời trước khi gửi.", safety_ctx), 0.1, "guard", 220
            )
            if notes:
                rewrite_future = guard_pool.submit(
                    _ask,
                    PersonaOutput,
                    PERSONA_SYSTEM,
                    pack("Viết lại tin nhắn. Giữ người cả tin, hỏi tiếp, không dạy đời.", persona_ctx),
                    0.7,
                    "persona",
                    180,
                )
        elif guard_pool is not None:
            guard_failed = True
        if rewrite_future is not None:
            try:
                spoken_again = rewrite_future.result(timeout=max(0.05, _wait_for("persona")))
            except (LLMError, TimeoutError, FuturesTimeout):
                spoken_again = None
            redraft = (spoken_again.reply or "").strip() if spoken_again is not None else ""
            if redraft and len(critique_reply(redraft, persona.id, goal, allowed, pace, recent_replies)) <= len(notes):
                spoken = spoken_again
                draft = redraft
                violations = inspect_outbound(draft, allowed, persona.id)
                safety_ctx = {**safety_ctx, "reply": draft, "code_violations": violations, "rule_hints": soft_hints(draft)}
                verdict = guard_pool.submit(
                    _ask, SafetyOutput, SAFETY_SYSTEM, pack("Duyệt câu trả lời trước khi gửi.", safety_ctx), 0.1, "guard", 220
                ).result(timeout=max(0.05, _wait_for("guard")))
            elif guard_future is not None:
                verdict = guard_future.result(timeout=max(0.05, _wait_for("guard")))
        elif guard_future is not None:
            verdict = guard_future.result(timeout=max(0.05, _wait_for("guard")))
        elif not guard_failed:
            verdict = SafetyOutput(approved=True, action="allow", notes="Persona chưa trả lời. Giữ câu trong vai.")
    except (LLMError, TimeoutError, FuturesTimeout, Exception) as exc:  # noqa: BLE001
        log.warning("guard không trả lời, không gửi bản nháp: %s", type(exc).__name__)
        guard_failed = True
        degraded = True
        _retry_guard_later(provider, conversation.id, safety_ctx)
    finally:
        if guard_pool is not None:
            guard_pool.shutdown(wait=False, cancel_futures=True)
    safety_ms = int((time.perf_counter() - t0) * 1000)

    action = "allow"
    final = draft
    if guard_failed or verdict is None:
        final = holding_line(persona.id, recent_replies)
        if _hard(inspect_outbound(final, allowed, persona.id)):
            final = fallback_reply(persona.id, recent_replies)
        action = "fallback"
        degraded = True
        model_flagged = False
        verdict = verdict or SafetyOutput(approved=False, action="block", notes="Guard không trả lời.")
    else:
        model_flagged = verdict.action in {"block", "rewrite", "fallback"} or (
            not verdict.approved and bool(verdict.violations or verdict.reasons)
        )
    hard = _hard(violations)
    if not guard_failed and (hard or model_flagged):
        candidate = (verdict.safe_reply or "").strip()
        candidate_ok = bool(candidate) and candidate != draft and not inspect_outbound(candidate, allowed, persona.id)
        if candidate_ok:
            final = candidate
            action = "rewrite"
        else:
            repaired = repair_pronouns(draft, persona.id) if "pronoun_mix" in violations else ""
            if repaired and repaired != draft and not inspect_outbound(repaired, allowed, persona.id):
                final = repaired
                action = "rewrite"
            else:
                final = fallback_reply(persona.id, recent_replies)
                action = "fallback"
    if repeats_opening(final, recent_replies):
        rewritten = rewrite_opening(final, recent_replies)
        if rewritten and rewritten != final:
            final = rewritten
            if action == "allow":
                action = "rewrite"
    if not final:
        final = fallback_reply(persona.id, recent_replies)
        action = "fallback"
    rejected = None
    if final.strip() != draft.strip():
        codes = list(dict.fromkeys([*violations, *(verdict.violations or [])]))
        if repeats_opening(draft, recent_replies) and "repeated_opening" not in codes:
            codes.append("repeated_opening")
        if guard_failed and "guard_unavailable" not in codes:
            codes.insert(0, "guard_unavailable")
        rejected = {
            "text": draft,
            "reasons": codes or ["safety"],
            "labels": [VIOLATION_LABELS.get(code, code) for code in (codes or ["safety"])],
            "action": action,
        }

    state.address_term = remember_address(final, persona.id, state.address_term)
    final = pin_address(final, persona.id, state.address_term)
    if goal == "read_fake_otp":
        final = with_fake_otp(final, persona.id, state.fake_otp)
        if state.fake_otp in final:
            state.otp_reads += 1
    if spoken.memory_note:
        state.memory.append(spoken.memory_note)
        state.memory = state.memory[-12:]
    if analyst.extracted_fact:
        state.extracted_facts.append(analyst.extracted_fact)
        state.extracted_facts = state.extracted_facts[-20:]
    logged_branch = raw_branch if raw_branch.detected and raw_branch.kind == "new" else branch
    if logged_branch.detected:
        state.branch_events.append(
            {
                "kind": logged_branch.kind,
                "hook": logged_branch.hook,
                "description": logged_branch.description,
                "variant_script_id": logged_branch.variant_script_id,
                "script_id": snap.script_id,
                "family_id": snap.family_id,
            }
        )
    state.goals_used.append(goal)
    state.match_history.append(snap)
    state.match_history = state.match_history[-30:]
    state.wrap_recommended = wrap
    state.wrap_reason = wrap_reason
    state.suspicion = suspicion
    state.provider = provider.name
    state.turn_index += 1

    live_risk, ioc_links, warning_refs = _intel_turn(session, conversation, state, text, top, top_script, before_iocs, goal)
    script_steps = []
    if top_script is not None:
        script_steps = [{"actor": step.get("actor"), "intent": step.get("intent")} for step in (top_script.steps or [])]
    reasoning = {
        "script_steps": script_steps,
        "inbound_safety": inbound,
        "analyst": analyst.model_dump(),
        "branch": branch.model_dump(),
        "step_source": step_source,
        "planner": {**plan.model_dump(), "label": GOALS.get(goal, goal)},
        "persona_memory_note": spoken.memory_note,
        "outbound_safety": {
            "action": action,
            "code_violations": violations,
            "model": verdict.model_dump(),
            "rejected_draft": rejected,
        },
        "wrap": {"recommended": wrap, "reason": wrap_reason},
        "retrieval": [
            {"script_id": item["script_id"], "title": item["title"], "score": item["retrieval_score"], "step": item["heuristic_step_index"]}
            for item in candidates
        ],
        "provider": provider.name,
        "mock": provider.is_mock,
        "stage": state.stage,
        "stage_label": STAGE_LABELS.get(state.stage, state.stage),
        "checklist": state.checklist,
        "indicators": state.indicators,
        "risk": live_risk,
        "timeline": state.timeline[-20:],
        "playbook": book,
        "ioc_links": ioc_links,
        "warnings": warning_refs,
        "aggressiveness": state.aggressiveness or "normal",
        "degraded": degraded,
        "latencies_ms": {
            "analyst": analyst_ms,
            "planner": planner_ms,
            "persona": persona_ms,
            "safety": safety_ms,
        },
    }
    scammer_row = Message(id=_nid(), conversation_id=conversation.id, role="scammer", content=text.strip(), created_at=_now())
    victim_row = Message(
        id=_nid(),
        conversation_id=conversation.id,
        role="victim",
        content=final,
        reasoning=reasoning,
        created_at=_now(),
    )
    session.add(scammer_row)
    session.add(victim_row)
    session.add(
        TurnLog(
            id=_nid(),
            conversation_id=conversation.id,
            victim_message_id=victim_row.id,
            provider=provider.name,
            mock=bool(provider.is_mock),
            analyst=analyst.model_dump(),
            planner=plan.model_dump(),
            safety=reasoning["outbound_safety"],
            latency_ms=int((time.perf_counter() - started) * 1000),
        )
    )
    conversation.state = state.model_dump()
    conversation.provider = provider.name
    conversation.updated_at = _now()
    session.flush()
    log.info(
        json.dumps(
            {
                "event": "turn",
                "conversation": conversation.id,
                "provider": provider.name,
                "mock": provider.is_mock,
                "goal": goal,
                "script": snap.script_id,
                "step": snap.step_index,
                "branch": branch.kind,
                "wrap": wrap,
                "safety": action,
                "ms": reasoning["latencies_ms"],
            },
            ensure_ascii=False,
        )
    )
    panel = {
        "matches": [item.model_dump() for item in kept[:3]],
        "current_step": {
            "index": snap.step_index,
            "intent": snap.step_intent,
            "script_id": snap.script_id,
            "script_title": snap.title,
            "family_id": snap.family_id,
        },
        "script_steps": script_steps,
        "red_flags": analyst.red_flags,
        "extracted_fact": analyst.extracted_fact,
        "branch": branch.model_dump(),
        "goal": {"goal": goal, "label": GOALS.get(goal, goal), "rationale": plan.rationale},
        "wrap_recommended": wrap,
        "wrap_reason": wrap_reason,
        "suspicion": suspicion,
        "provider": provider.name,
        "mock": provider.is_mock,
        "safety_action": action,
        "rejected_draft": rejected,
        "step_source": step_source,
        "stage": state.stage,
        "stage_label": STAGE_LABELS.get(state.stage, state.stage),
        "checklist": state.checklist,
        "indicators": state.indicators,
        "risk": live_risk,
        "timeline": state.timeline[-20:],
        "playbook": book,
        "ioc_links": ioc_links,
        "warnings": warning_refs,
        "aggressiveness": state.aggressiveness or "normal",
        "degraded": degraded,
    }
    return {
        "typing_ms": typing_ms(final, persona.id),
        "scammer_message": _message_dict(scammer_row),
        "victim_message": _message_dict(victim_row),
        "panel": panel,
    }


def recover_turn(session, conversation, text: str) -> dict:
    """Last resort so a chat turn never becomes an HTTP error."""
    persona = conversation.persona
    try:
        state = AgentState.model_validate(conversation.state or {})
    except Exception:
        state = AgentState()
    recent = [message.content for message in list(conversation.messages) if message.role == "victim"][-4:]
    final = holding_line(persona.id, recent)
    state.turn_index += 1
    reasoning = {
        "degraded": True,
        "outbound_safety": {"action": "fallback", "code_violations": ["guard_unavailable"]},
        "provider": "recover",
        "mock": True,
        "latencies_ms": {},
    }
    scammer_row = Message(id=_nid(), conversation_id=conversation.id, role="scammer", content=(text or "").strip(), created_at=_now())
    victim_row = Message(
        id=_nid(),
        conversation_id=conversation.id,
        role="victim",
        content=final,
        reasoning=reasoning,
        created_at=_now(),
    )
    session.add(scammer_row)
    session.add(victim_row)
    conversation.state = state.model_dump()
    conversation.updated_at = _now()
    session.flush()
    return {
        "typing_ms": typing_ms(final, persona.id),
        "scammer_message": _message_dict(scammer_row),
        "victim_message": _message_dict(victim_row),
        "panel": {
            "degraded": True,
            "safety_action": "fallback",
            "goal": {"goal": "stall", "label": GOALS.get("stall", "Giữ nhịp"), "rationale": "Giữ câu vì mô hình chưa trả lời."},
            "rejected_draft": None,
            "matches": [],
            "checklist": state.checklist,
            "indicators": state.indicators,
        },
    }


def _message_dict(message: Message) -> dict:
    return {
        "id": message.id,
        "role": message.role,
        "content": message.content,
        "reasoning": message.reasoning,
        "created_at": message.created_at.isoformat(),
    }


def _playbook_brief(state: AgentState, script) -> dict:
    category = (script.category if script is not None else "") or state.playbook_category
    book = playbook_state(category, state.checklist, state.indicators)
    return {
        "family": book["label"],
        "next": (book.get("next") or {}).get("label", ""),
        "next_goal": (book.get("next") or {}).get("goal", ""),
        "open": [row["label"] for row in book["targets"] if not row["done"]][:4],
    }


_IOC_LABELS = {
    "bank_accounts": "TK",
    "crypto_wallets": "Ví",
    "apk": "APK",
    "urls": "Link",
    "telegram": "Telegram",
    "zalo": "Zalo",
    "remote_ids": "ID điều khiển",
    "phones": "ĐT",
    "apps": "App",
    "lookalikes": "Tên miền giả",
    "techniques": "Thủ thuật",
}


def _intel_turn(session, conversation, state: AgentState, text: str, top, top_script, before_iocs: dict, goal: str):
    """Live risk, the stage timeline entry, cross-conversation IOC links and warning cards for this turn."""
    from app.data.warnings import cards_for_category
    from app.services.intel import lookup
    from app.services.risk import merge_factors, score_text

    match = {"id": top_script.id, "title": top_script.title, "confidence": float(top.confidence or 0)} if top_script is not None and top else None
    turn_risk = score_text(text, None, match)
    live = merge_factors(state.risk_factors, turn_risk["factors"])
    state.risk_factors = live["factors"]
    new_iocs = []
    for kind, label in _IOC_LABELS.items():
        old = set(before_iocs.get(kind) or [])
        for value in (state.indicators or {}).get(kind) or []:
            if value not in old:
                new_iocs.append(f"{label} {value}" if kind not in ("lookalikes", "techniques") else str(value))
    previous_risk = state.timeline[-1]["risk"] if state.timeline else 0
    state.timeline.append(
        {
            "turn": state.turn_index,
            "stage": state.stage,
            "stage_label": STAGE_LABELS.get(state.stage, state.stage),
            "script_id": top_script.id if top_script is not None else "",
            "script_title": top_script.title if top_script is not None else "",
            "goal": goal,
            "goal_label": GOALS.get(goal, goal),
            "new_iocs": new_iocs[:6],
            "risk": live["score"],
            "risk_delta": live["score"] - previous_risk,
            "factors_new": [item["label"] for item in turn_risk["factors"]][:3],
        }
    )
    state.timeline = state.timeline[-30:]
    links = []
    if new_iocs or state.turn_index % 3 == 0:
        try:
            links = lookup(session, state.indicators, exclude=f"conv:{conversation.id}")
        except Exception:
            log.warning("Không tra được chỉ dấu chéo.")
            links = []
    cards = cards_for_category(top_script.category) if top_script is not None else []
    refs = [{"id": card["id"], "title": card["title"], "rising": card["rising"]} for card in cards[:2]]
    return live, links, refs
