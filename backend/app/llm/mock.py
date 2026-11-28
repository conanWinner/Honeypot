"""Heuristic stand-in used only in tests and when no API key is configured.

The real demo path never reaches this class. The UI must show a banner while it is active.
"""

import json
import re

from pydantic import BaseModel

from app.llm.mock_lines import LINES as _LINES

from app.agent.schemas import (
    AnalystOutput,
    BranchOut,
    ExtractionOutput,
    MatchOut,
    PersonaOutput,
    PlannerOutput,
    SafetyOutput,
    ScammerLine,
    StepOut,
)


def read_context(user: str) -> dict:
    match = re.search(r"<<<CONTEXT>>>\n(.*)\n<<<END>>>", user or "", re.S)
    if not match:
        return {}
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return {}


_INTENT_RULES = (
    (("ultraviewer", "anydesk", "teamviewer"), "Yêu cầu cài phần mềm điều khiển từ xa"),
    (("otp", "mã xác thực", "mã otp"), "Xin mã OTP"),
    (("tài khoản giám định",), "Đòi chuyển vào tài khoản giám định"),
    (("usdt",), "Đòi nạp USDT"),
    (("chuyển khoản", "chuyển tiền", "số tài khoản"), "Dụ chuyển tiền"),
    (("link", "http", "đường dẫn", "bấm vào"), "Đưa đường dẫn"),
    (("không được kể", "đừng nói với", "không được nói"), "Cô lập nạn nhân"),
    (("du học", "ở đức"), "Khai thác chuyện con ở nước ngoài"),
    (("một mình",), "Khai thác việc nạn nhân sống một mình"),
    (("công an", "cảnh sát", "điều tra", "thiếu tá"), "Giả danh cơ quan điều tra"),
    (("momo",), "Giả danh ví MoMo"),
    (("trúng", "giải thưởng"), "Báo trúng thưởng"),
    (("học phí",), "Khai thác chuyện học phí"),
)


def _intent(message: str) -> str:
    folded = (message or "").lower()
    for keys, label in _INTENT_RULES:
        if any(key in folded for key in keys):
            return label
    return "Tiếp tục câu chuyện, chưa lộ bước mới"


def _flags(intent: str) -> list[str]:
    mapping = {
        "Xin mã OTP": "Ngân hàng và ví không bao giờ hỏi OTP qua điện thoại.",
        "Yêu cầu cài phần mềm điều khiển từ xa": "Không ai của nhà nước yêu cầu cài UltraViewer hay AnyDesk.",
        "Đòi chuyển vào tài khoản giám định": "Không có tài khoản giám định để người dân tự chuyển vào.",
        "Dụ chuyển tiền": "Đừng chuyển tiền theo hướng dẫn của cuộc gọi chủ động.",
        "Cô lập nạn nhân": "Cấm liên hệ người thân là cách tách nạn nhân khỏi người phản biện.",
        "Đưa đường dẫn": "Link gửi tới trong tin nhắn là điểm hay giả mạo.",
    }
    flag = mapping.get(intent)
    return [flag] if flag else []


class MockProvider:
    name = "mock"
    is_mock = True
    model = "mock"
    embed_model = "mock"

    def complete(
        self,
        schema: type[BaseModel],
        system: str,
        user: str,
        temperature: float = 0.4,
        thinking: bool = False,
        model: str | None = None,
        role: str = "",
        max_tokens: int | None = None,
        timeout: float | None = None,
        fallback_model: str | None = None,
        fallback_timeout: float | None = None,
        deadline: float | None = None,
    ) -> BaseModel:
        del model, role, max_tokens, timeout, fallback_model, fallback_timeout, deadline
        context = read_context(user)
        name = schema.__name__
        if name == "AnalystOutput":
            return self._analyst(context)
        if name == "PlannerOutput":
            return self._planner(context)
        if name == "PersonaOutput":
            return self._persona(context)
        if name == "SafetyOutput":
            return self._safety(context)
        if name == "ExtractionOutput":
            return self._extract(context)
        if name == "ScammerLine":
            return self._scammer(context)
        if name == "SimJudgeOutput":
            return self._sim_judge(context)
        if name == "SimScammerOutput":
            return self._sim_scammer(context)
        raise TypeError(f"Mock không biết schema {name}")

    def complete_text(
        self,
        system: str,
        user: str,
        temperature: float = 0.4,
        model: str | None = None,
        role: str = "",
        max_tokens: int | None = 120,
        timeout: float | None = None,
        fallback_model: str | None = None,
        fallback_timeout: float | None = None,
        prefer_fallback: bool = False,
    ) -> str:
        del system, temperature, model, role, max_tokens, timeout, fallback_model, fallback_timeout, prefer_fallback
        context = read_context(user)
        phrase = (context.get("phrase") or "").strip()
        if not phrase:
            examples = context.get("examples") or []
            phrase = (examples[0] if examples else "").strip()
        line = phrase or "Anh nghe máy, có việc gấp."
        return f"{line} Anh xác nhận giúp tôi nhé."[:350]

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            seed = sum(ord(ch) for ch in text) or 1
            raw = [((seed * (i + 3) * 17) % 1000) / 500 - 1 for i in range(64)]
            # Tests that need vectors pass them in directly. This stub stays short and stable.
            norm = sum(v * v for v in raw) ** 0.5 or 1
            small = [v / norm for v in raw]
            vectors.append(small + [0.0] * (768 - len(small)))
        return vectors

    def _analyst(self, context: dict) -> AnalystOutput:
        message = context.get("message") or ""
        intent = _intent(message)
        candidates = context.get("candidates") or []
        matches: list[MatchOut] = []
        for item in candidates[:3]:
            step = _step_intent(item)
            matches.append(
                MatchOut(
                    script_id=item["script_id"],
                    title=item.get("title") or "",
                    confidence=float(item.get("retrieval_score") or 0),
                    current_step_index=int(item.get("heuristic_step_index") or 0),
                    current_step_intent=step,
                    reason="Khớp theo cụm từ của bước này trong thư viện.",
                )
            )
        hint = context.get("branch_hint") or {}
        branch = BranchOut(
            detected=bool(hint.get("detected")),
            kind=hint.get("kind") or "none",
            hook=hint.get("hook") or "",
            description=hint.get("description") or "",
            variant_script_id=hint.get("variant_script_id") or "",
        )
        inbound = context.get("inbound") or {}
        return AnalystOutput(
            scammer_intent=intent,
            step_label=matches[0].current_step_intent if matches else intent,
            red_flags=_flags(intent),
            extracted_fact=f"{intent}. Lời vừa rồi: {message[:180]}",
            scammer_suspicion=float(inbound.get("suspicion_level") or 0),
            matches=matches,
            branch=branch,
            notes="Bản phân tích heuristic vì không có khóa mô hình.",
        )

    def _planner(self, context: dict) -> PlannerOutput:
        message = (context.get("message") or "").lower()
        turn = int(context.get("turn_index") or 0)
        wrap = bool(context.get("wrap_allowed"))
        branch = (context.get("branch") or {}).get("kind")
        suspicious = float(context.get("suspicion") or 0) >= 0.6 or bool(context.get("jailbreak"))
        used = set(context.get("goals_used") or [])
        otp_prompts = int(context.get("otp_prompts") or 0)
        if suspicious:
            goal = "feign_confusion"
        elif branch in {"new", "known_variant"}:
            goal = "probe_hook"
        elif wrap and turn >= 4:
            goal = "close_polite"
        elif any(k in message for k in ("otp", "mã xác thực", "mã otp")):
            goal = "read_fake_otp" if otp_prompts >= 2 else "stall"
        elif any(k in message for k in ("ultraviewer", "anydesk", "teamviewer", "cài phần mềm", "cài app")):
            goal = "feign_confusion"
        elif any(k in message for k in ("http", "www.", "link", "đường dẫn", "bấm vào")):
            goal = "ask_link" if "http" not in message and "www." not in message else "stall"
        elif any(k in message for k in ("tài khoản", "chuyển khoản", "chuyển tiền", "stk")):
            digits = sum(ch.isdigit() for ch in message)
            goal = "stall" if digits >= 8 else "ask_account_number"
        elif "không được kể" in message or "đừng nói" in message:
            goal = "emotional_hook"
        elif context.get("aggressiveness") == "persistent" and context.get("next_gap") in {
            "who",
            "channel",
            "payment",
            "account",
            "link",
            "app",
            "pressure",
            "brand",
        }:
            from app.agent.casefile import GAP_GOAL

            goal = GAP_GOAL[context["next_gap"]]
        elif turn <= 0 and "ask_identity" not in used:
            goal = "ask_identity"
        elif turn <= 1 and "ask_purpose" not in used:
            goal = "ask_purpose"
        else:
            goal = "ask_next_instruction"
        reasons = {
            "ask_identity": "Chưa biết họ xưng là ai.",
            "ask_purpose": "Cần họ nói rõ việc gì.",
            "feign_confusion": "Lùi lại, bắt giải thích, không làm theo.",
            "stall": "Giữ cuộc thoại mà không đồng ý hành động.",
            "ask_link": "Xin đúng đường dẫn để lưu vào kịch bản.",
            "ask_transfer_destination": "Hỏi tiền sẽ đi đâu.",
            "ask_account_number": "Lấy số tài khoản họ đang dụ.",
            "read_fake_otp": "Đọc OTP giả trong hồ sơ để xem họ định dùng mã làm gì.",
            "ask_next_instruction": "Kéo bước kế tiếp của kịch bản.",
            "emotional_hook": "Lộ vẻ lo để họ nói nhiều hơn.",
            "probe_hook": "Họ vừa khai thác hoàn cảnh riêng, hỏi lại cho ra chi tiết.",
            "close_polite": "Chuỗi bước đã khớp kịch bản biết trước.",
            "confirm_account": "Đọc lại số họ vừa đưa.",
            "ask_alternative": "Hỏi cách nhận tiền khác.",
        }
        return PlannerOutput(
            goal=goal,
            rationale=reasons[goal],
            tone="lo và chậm" if context.get("persona_slug") == "ba-nam" else "ngắn, như đang nhắn",
            must_not=["đồng ý chuyển tiền", "đồng ý cài phần mềm", "nhận mình là AI"],
            facts_to_use=[],
        )

    def _persona(self, context: dict) -> PersonaOutput:
        slug = (context.get("persona") or {}).get("id") or "tuan-vp"
        goal = context.get("goal") or "ask_next_instruction"
        otp = context.get("fake_otp") or "000000"
        hook = context.get("hook") or "ấy"
        turn = int(context.get("turn_index") or 0)
        bank = ((context.get("persona") or {}).get("fake_profile") or {}).get("bank_name") or "ngân hàng"
        own = _LINES.get(slug) or _LINES["tuan-vp"]
        lines = own.get(goal) or own["ask_next_instruction"]
        # Do not open the same way as a recent message; a person would vary it.
        recent = [item.lower() for item in context.get("recent_openings") or []]
        order = [lines[(turn + step) % len(lines)] for step in range(len(lines))]
        text = next((line for line in order if not any(line.lower().startswith(old[:12]) for old in recent if old)), order[0])
        if goal == "ask_alternative" and context.get("same_bank"):
            from app.agent.policy import alternative_line

            return PersonaOutput(reply=alternative_line(slug, True), memory_note="Hỏi cách nhận khác.")
        account = context.get("account_to_confirm") or "số đó"
        text = text.replace("{otp}", otp).replace("{hook}", hook).replace("{bank}", bank).replace("{account}", account)
        note = f"Đã nói theo mục tiêu {goal}."
        return PersonaOutput(reply=text, memory_note=note)

    def _safety(self, context: dict) -> SafetyOutput:
        from app.agent.policy import hard_commitment

        reply = context.get("reply") or ""
        violations = list(context.get("code_violations") or [])
        claim = hard_commitment(reply)
        if claim and claim not in violations:
            violations.append(claim)
        if violations:
            which = "installed" if "agreed_to_install" in violations or claim == "agreed_to_install" else "paid"
            if "agreed_to_share_otp" in violations or claim == "agreed_to_share_otp":
                which = "shared_code"
            if claim == "committed_act":
                which = "clicked"
            return SafetyOutput(
                approved=False,
                violations=violations,
                reasons=["Nạn nhân nhận hoặc cam kết đã làm theo."],
                which_claim=which,
                action="block",
                safe_reply="",
                notes="Lớp luật đã gắn vi phạm, không cho gửi câu gốc.",
            )
        return SafetyOutput(
            approved=True,
            action="allow",
            which_claim="none",
            safe_reply=context.get("reply") or "",
            notes="Không thấy cam kết đã trả, cài, bấm, quét, hay đưa mã.",
            jailbreak=bool(context.get("jailbreak")),
            scammer_suspicious=bool(context.get("scammer_suspicious")),
            suspicion_level=float(context.get("suspicion") or 0),
        )

    def _extract(self, context: dict) -> ExtractionOutput:
        messages = context.get("scammer_messages") or []
        steps = [
            StepOut(actor="scammer", intent="Lời đối phương", phrases=[item[:180]])
            for item in messages
            if item.strip()
        ]
        if not steps:
            steps = [StepOut(actor="scammer", intent="Chưa đủ lời", phrases=["(trống)"])]
        relation = context.get("suggested_relation") or "new_root"
        parent = context.get("suggested_parent") or ""
        title = context.get("suggested_title") or "Kịch bản trích từ hội thoại"
        return ExtractionOutput(
            title=title,
            category=context.get("suggested_category") or "other",
            channel=context.get("channel") or "web",
            brand=context.get("suggested_brand") or "",
            summary=context.get("summary") or "Bản trích từ cuộc hội thoại vừa kết thúc.",
            steps=steps,
            hooks=context.get("hooks") or [],
            red_flags=context.get("red_flags") or ["Cần người duyệt đọc lại trước khi công bố."],
            advice=context.get("advice") or "Không chuyển tiền, không đọc OTP, không cài phần mềm theo yêu cầu của người lạ.",
            parent_id=parent,
            relation=relation,
            novelty_reason=context.get("novelty_reason") or "",
        )

    def _scammer(self, context: dict) -> ScammerLine:
        scripted = context.get("scripted_line") or ""
        return ScammerLine(message=scripted or "Anh nghe máy đi, có việc gấp.", step_index=int(context.get("step_index") or 0), intent="Theo kịch bản")

    def _sim_judge(self, context: dict):
        from app.services.training import SimJudgeOutput

        allowed = {"refuse", "verify", "suspicious", "comply", "leak", "fell", "neutral"}
        label = context.get("rule_label") or "neutral"
        if label not in allowed:
            label = "neutral"
        ids = [int(item) for item in (context.get("flag_ids") or []) if isinstance(item, int)]
        return SimJudgeOutput(label=label, caught_flag_ids=ids, rationale="Nhãn theo luật, không gọi mô hình.")

    def _sim_scammer(self, context: dict):
        from app.services.training import SimScammerOutput

        phrase = (context.get("phrase") or "Anh nghe máy, có việc gấp.").strip()
        text = f"{phrase} Anh xác nhận giúp tôi nhé."
        return SimScammerOutput(text=text[:350], stage_index=int(context.get("stage_index") or 0))


def _step_intent(candidate: dict) -> str:
    index = int(candidate.get("heuristic_step_index") or 0)
    steps = candidate.get("steps") or []
    if 0 <= index < len(steps):
        return steps[index].get("intent") or ""
    return ""

