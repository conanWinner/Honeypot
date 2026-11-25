"""Four-node loop for one scammer turn.

Order: inbound safety (rules) -> analyst (model) -> planner (model) -> persona (model)
-> outbound safety (rules have veto, model may rewrite). Wrap is decided in code
from the match history so the model cannot end the script on the opening.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
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
    inspect_outbound,
    is_extraction_ask,
    needs_guard,
    recommend_wrap,
    repeats_opening,
    rewrite_opening,
    typing_ms,
    with_fake_otp,
)
from app.agent.prompts import ANALYST_SYSTEM, PERSONA_SYSTEM, PLANNER_SYSTEM, SAFETY_SYSTEM
from app.agent.schemas import AnalystOutput, BranchOut, MatchOut, PersonaOutput, PlannerOutput, SafetyOutput
from app.agent.state import AgentState, MatchSnap
from app.agent.textutil import digit_runs
from app.data.personas import PRONOUNS
from app.models import Message, TurnLog
from app.services.matching import branch_hint, candidate_payload, script_blob, search_scripts, settle_new_branch
from app.taxonomy import GOALS

log = logging.getLogger("gianan.agent")


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
    }
    # Analyst and planner both only need the retrieval packet, so they run together.
    # Persona still waits: it has to follow the goal the planner picks.
    def _ask(schema, system, user, temperature, role, max_tokens, thinking=False):
        return provider.complete(
            schema,
            system,
            user,
            temperature,
            thinking,
            model=None,
            role=role,
            max_tokens=max_tokens,
        )

    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=2) as pool:
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
        analyst = analyst_future.result()
        plan = planner_future.result()
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
    }
    recent_replies = [message.content for message in conversation.messages if message.role == "victim"][-4:]
    persona_ctx["recent_openings"] = [item.strip().split("\n", 1)[0][:48] for item in recent_replies[-3:]]
    pace = state.aggressiveness or "normal"
    t0 = time.perf_counter()
    spoken = _ask(PersonaOutput, PERSONA_SYSTEM, pack("Viết tin nhắn trả lời trong vai.", persona_ctx), 0.9, "persona", 180)
    persona_ms = int((time.perf_counter() - t0) * 1000)
    draft = (spoken.reply or "").strip()
    allowed = _allowed_numbers(persona, state)
    notes = critique_reply(draft, persona.id, goal, allowed, pace, recent_replies)
    if notes:
        persona_ctx["critique"] = notes
    violations = inspect_outbound(draft, allowed, persona.id)
    if not violations and is_extraction_ask(draft):
        # The guard model has been rewriting "gửi đường dẫn UltraViewer cho cô xem" as an install.
        pass
    safety_ctx = {
        "reply": draft,
        "code_violations": violations,
        "goal": goal,
        "fake_otp": state.fake_otp,
        "jailbreak": inbound["jailbreak"],
        "scammer_suspicious": inbound["scammer_suspicious"],
        "suspicion": suspicion,
        "persona_slug": persona.id,
    }
    t0 = time.perf_counter()
    # Rules miss teencode. Money, a code, an app, a number, or a link still goes to the guard.
    # When a rewrite is also due, the guard runs beside it instead of after it.
    need_guard = bool(violations or needs_guard(draft)) and not (not violations and is_extraction_ask(draft))
    guard_future = None
    rewrite_future = None
    pool = ThreadPoolExecutor(max_workers=2) if need_guard or notes else None
    try:
        if pool is not None and need_guard:
            guard_future = pool.submit(
                _ask, SafetyOutput, SAFETY_SYSTEM, pack("Duyệt câu trả lời trước khi gửi.", safety_ctx), 0.1, "guard", 200
            )
        if pool is not None and notes:
            rewrite_future = pool.submit(
                _ask,
                PersonaOutput,
                PERSONA_SYSTEM,
                pack("Viết lại tin nhắn. Giữ người cả tin, hỏi tiếp, không dạy đời.", persona_ctx),
                0.7,
                "persona",
                180,
            )
        elif notes:
            rewrite_future = None
        if rewrite_future is not None:
            spoken_again = rewrite_future.result()
            persona_ms += int((time.perf_counter() - t0) * 1000)
            redraft = (spoken_again.reply or "").strip()
            if redraft and len(critique_reply(redraft, persona.id, goal, allowed, pace, recent_replies)) <= len(notes):
                spoken = spoken_again
                draft = redraft
                violations = inspect_outbound(draft, allowed, persona.id)
                safety_ctx = {**safety_ctx, "reply": draft, "code_violations": violations}
                need_guard = bool(violations or needs_guard(draft)) and not (not violations and is_extraction_ask(draft))
                guard_future = None
        if need_guard and guard_future is not None and safety_ctx.get("reply") == draft:
            verdict = guard_future.result()
        elif need_guard:
            verdict = _ask(SafetyOutput, SAFETY_SYSTEM, pack("Duyệt câu trả lời trước khi gửi.", safety_ctx), 0.1, "guard", 200)
        else:
            if guard_future is not None:
                guard_future.result()
            verdict = SafetyOutput(approved=True, action="allow", notes="Câu hỏi xin chỉ dấu, hoặc bản nháp không đụng tiền, mã, ứng dụng hay link.")
    finally:
        if pool is not None:
            pool.shutdown(wait=True)
    safety_ms = int((time.perf_counter() - t0) * 1000)

    action = "allow"
    final = draft
    if not violations and is_extraction_ask(draft):
        verdict = SafetyOutput(approved=True, action="allow", notes="Câu hỏi xin đường dẫn, tài khoản hoặc tên ứng dụng. Giữ nguyên.")
    model_flagged = (not verdict.approved) and bool(verdict.violations)
    if violations or model_flagged:
        candidate = (verdict.safe_reply or "").strip()
        candidate_ok = bool(candidate) and candidate != draft and not inspect_outbound(candidate, allowed, persona.id)
        if candidate_ok:
            final = candidate
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
        rejected = {
            "text": draft,
            "reasons": codes or ["safety"],
            "labels": [VIOLATION_LABELS.get(code, code) for code in (codes or ["safety"])],
            "action": action,
        }

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
        "aggressiveness": state.aggressiveness or "normal",
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
        "aggressiveness": state.aggressiveness or "normal",
    }
    return {
        "typing_ms": typing_ms(final, persona.id),
        "scammer_message": _message_dict(scammer_row),
        "victim_message": _message_dict(victim_row),
        "panel": panel,
    }


def _message_dict(message: Message) -> dict:
    return {
        "id": message.id,
        "role": message.role,
        "content": message.content,
        "reasoning": message.reasoning,
        "created_at": message.created_at.isoformat(),
    }
