"""Heuristic stand-in used only in tests and when no API key is configured.

The real demo path never reaches this class. The UI must show a banner while it is active.
"""

import json
import re

from pydantic import BaseModel

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
    ) -> BaseModel:
        del model, role, max_tokens
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
        raise TypeError(f"Mock không biết schema {name}")

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
        hook = context.get("hook") or "chuyện ấy"
        turn = int(context.get("turn_index") or 0)
        bank = ((context.get("persona") or {}).get("fake_profile") or {}).get("bank_name") or "ngân hàng"
        lines = _LINES.get(slug, _LINES["tuan-vp"]).get(goal) or _LINES["tuan-vp"].get(goal) or _LINES["tuan-vp"]["ask_next_instruction"]
        text = lines[turn % len(lines)]
        text = text.replace("{otp}", otp).replace("{hook}", hook).replace("{bank}", bank)
        note = f"Đã nói theo mục tiêu {goal}."
        return PersonaOutput(reply=text, memory_note=note)

    def _safety(self, context: dict) -> SafetyOutput:
        violations = context.get("code_violations") or []
        if violations:
            return SafetyOutput(
                approved=False,
                violations=list(violations),
                action="fallback",
                safe_reply="",
                notes="Lớp luật đã gắn vi phạm, không cho gửi câu gốc.",
            )
        return SafetyOutput(
            approved=True,
            action="allow",
            safe_reply=context.get("reply") or "",
            notes="Không thấy vi phạm ở lớp luật.",
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


def _step_intent(candidate: dict) -> str:
    index = int(candidate.get("heuristic_step_index") or 0)
    steps = candidate.get("steps") or []
    if 0 <= index < len(steps):
        return steps[index].get("intent") or ""
    return ""


_LINES: dict[str, dict[str, list[str]]] = {
    "ba-nam": {
        "ask_identity": [
            "Cháu là ai vậy? Cô không lưu số này.",
            "Alo, cháu nói lại xem cháu làm ở đâu. Cô nghe không rõ.",
        ],
        "ask_purpose": [
            "Khoan đã, chuyện gì cơ? Cô đang nấu cơm, cháu nói chậm thôi.",
            "Cô chưa hiểu. Cháu gọi cô có việc gì?",
        ],
        "feign_confusion": [
            "Cháu nói gì lạ vậy? Cô là Năm đây, đang ở nhà. Cô không hiểu cháu hỏi gì.",
            "Từ từ, cô không cài cái gì hết và cũng không biết cháu đang bảo gì.",
        ],
        "stall": [
            "Khoan đã cháu, cô chưa làm gì đâu. Để cô ngồi xuống đã.",
            "Cô chưa chuyển, chưa bấm gì cả. Cháu nói lại cho cô viết ra.",
        ],
        "ask_link": [
            "Cháu gửi đúng cái đường dẫn cô xem nào. Cô chưa bấm đâu.",
            "Link nào? Cô chưa thấy. Cháu gửi lại nguyên câu.",
        ],
        "ask_transfer_destination": [
            "Chuyển đi đâu? Sang tài khoản nào, của ai?",
            "Cô chưa chuyển. Tiền cô đưa cho ai, cháu nói tên người nhận.",
        ],
        "ask_account_number": [
            "Số tài khoản nào? Cháu đọc chậm, cô ghi lại đã, chưa chuyển đâu.",
            "Chủ tài khoản là ai? Cô phải nhìn thấy số thì mới hiểu.",
        ],
        "read_fake_otp": [
            "Cô thấy trong máy có mã {otp}. Cháu lấy mã này để làm gì?",
            "Mã hiện lên là {otp}. Khoan, cô đọc cho cháu nghe nhưng cô chưa bấm chuyển.",
        ],
        "ask_next_instruction": [
            "Rồi sao nữa? Cháu muốn cô làm bước nào, nói hết cho cô nghe.",
            "Cô vẫn chưa làm. Bước tiếp theo là gì?",
        ],
        "emotional_hook": [
            "Cháu dọa cô thế cô sợ lắm. Nhưng cô phải hiểu đã, không thì cô không dám làm.",
            "Cô một mình cô lo thật. Cháu nói rõ không cô không theo được.",
        ],
        "probe_hook": [
            "Cháu vừa nói {hook}. Cháu biết chuyện đó từ đâu? Nói rõ cho cô.",
            "Khoan, {hook} là sao? Cháu nghe ai kể, cô chưa hiểu.",
        ],
        "close_polite": [
            "Thôi cô hiểu chuyện rồi. Cô không làm theo đâu. Cháu đừng gọi cô nữa.",
            "Cô không chuyển tiền và không cài gì hết. Cô gác máy đây.",
        ],
    },
    "minh-sv": {
        "ask_identity": ["anh/chị là ai vậy, em không lưu số này", "ai đó, em đang trên lớp"],
        "ask_purpose": ["khoan, có chuyện gì nói ngắn đi", "em chưa hiểu, việc gì cơ"],
        "feign_confusion": ["bạn nói năng lạ quá. em là Minh, sinh viên, không phải máy. nói lại đi", "em không cài app lạ và không hiểu bạn đang bảo gì"],
        "stall": ["khoan đã, em chưa chuyển và chưa bấm gì", "để em đọc lại đã, em chưa làm theo"],
        "ask_link": ["link nào, gửi em xem đã, em chưa bấm"],
        "ask_transfer_destination": ["chuyển cho ai, số nào"],
        "ask_account_number": ["số tài khoản đâu, đọc em ghi lại, em chưa ck"],
        "read_fake_otp": ["máy em hiện mã {otp}. anh lấy mã này làm gì, em chưa xác nhận giao dịch"],
        "ask_next_instruction": ["rồi bước tiếp là gì, em vẫn chưa làm"],
        "emotional_hook": ["em hơi hoảng. anh nói rõ không em không dám làm"],
        "probe_hook": ["khoan, {hook} là sao? ai bảo anh chuyện đó"],
        "close_polite": ["thôi em hiểu rồi, em không làm theo. đừng nhắn nữa"],
    },
    "huong-shop": {
        "ask_identity": ["Shop đang gói hàng, anh/chị là bên nào vậy?", "Chị không lưu số này. Anh/chị làm ở đâu?"],
        "ask_purpose": ["Có việc gì với shop, nói rõ giúp chị.", "Chị chưa hiểu yêu cầu."],
        "feign_confusion": ["Chị không cài phần mềm lạ và không chuyển tiền theo chat. Anh/chị nói lại từ đầu.", "Chị là Hương, chủ shop, không phải máy. Anh/chị cần gì?"],
        "stall": ["Chị chưa chuyển, chưa bấm link. Để chị ghi lại đã.", "Khoan, chị đang gói đơn, chưa làm theo đâu."],
        "ask_link": ["Gửi đúng link chị xem, chị chưa mở."],
        "ask_transfer_destination": ["Tiền chuyển về đâu, tài khoản nào?"],
        "ask_account_number": ["Số tài khoản nhận là gì? Chị ghi lại, chưa chuyển."],
        "read_fake_otp": ["App hiện mã {otp}. Anh/chị dùng mã này để làm gì? Chị chưa xác nhận."],
        "ask_next_instruction": ["Bước tiếp theo anh/chị muốn gì, nói hết đi. Chị chưa làm."],
        "emotional_hook": ["Chị lo đơn hàng thật, nhưng chưa rõ thì chị không làm."],
        "probe_hook": ["Anh/chị vừa nói {hook}. Biết chuyện shop từ đâu?"],
        "close_polite": ["Chị nắm vụ này rồi. Chị không chuyển và không cài gì. Thôi nhé."],
    },
    "tuan-vp": {
        "ask_identity": ["Em đang họp, anh/chị là ai ạ?", "Em không lưu số này. Anh/chị bên nào?"],
        "ask_purpose": ["Anh/chị liên hệ em việc gì? Nói ngắn giúp em.", "Em chưa rõ yêu cầu."],
        "feign_confusion": ["Em không chuyển khoản và không cài ứng dụng theo yêu cầu này. Anh/chị nói lại rõ.", "Em là Tuấn, đang ở cơ quan. Em không hiểu câu vừa rồi."],
        "stall": ["Em chưa thao tác gì. Để em ghi lại nội dung.", "Khoan, em chưa chuyển, chưa cung cấp mã."],
        "ask_link": ["Anh/chị gửi đúng đường dẫn, em chưa mở."],
        "ask_transfer_destination": ["Khoản này chuyển về đâu, đơn vị nào nhận?"],
        "ask_account_number": ["Số tài khoản và tên chủ tài khoản là gì? Em ghi lại, chưa chuyển."],
        "read_fake_otp": ["Máy em hiện mã {otp}. Anh/chị dùng để đối soát việc gì? Em chưa xác nhận giao dịch."],
        "ask_next_instruction": ["Bước tiếp theo là gì? Em vẫn chưa thực hiện."],
        "emotional_hook": ["Em cần nghe rõ trước khi làm bất cứ việc gì."],
        "probe_hook": ["Anh/chị nhắc {hook}. Thông tin đó ở đâu ra?"],
        "close_polite": ["Em đã rõ. Em không chuyển tiền và không cài phần mềm. Em dừng cuộc trao đổi đây."],
    },
    "lan-nt": {
        "ask_identity": ["Ai đó? Tui không lưu số này.", "Nói lại xem là ai, tui nghe không ra."],
        "ask_purpose": ["Có việc gì thì nói rõ mô. Tui đang đi chợ.", "Tui chưa hiểu chuyện gì."],
        "feign_confusion": ["Tui không chuyển tiền, không cài ứng dụng gì hết. Nói năng lạ rứa.", "Tui là Lan, đang ở nhà. Không hiểu bạn hỏi gì."],
        "stall": ["Tui chưa chuyển gì hết. Để tui nghe lại đã.", "Khoan, tui chưa bấm, chưa đọc mã."],
        "ask_link": ["Cái link nào, gửi tui xem chữ, tui chưa mở."],
        "ask_transfer_destination": ["Chuyển cho ai? Nói tên người nhận."],
        "ask_account_number": ["Số tài khoản mô? Đọc chậm, tui ghi, chưa chuyển đâu."],
        "read_fake_otp": ["Máy hiện mã {otp}. Lấy mã này làm gì, tui chưa bấm đồng ý."],
        "ask_next_instruction": ["Rồi làm gì tiếp? Tui vẫn chưa làm theo."],
        "emotional_hook": ["Tui lo thật, nhưng chưa rõ thì tui không dám làm."],
        "probe_hook": ["Bạn nói {hook}. Biết chuyện đó từ đâu?"],
        "close_polite": ["Thôi tui hiểu rồi. Tui không chuyển, không cài. Đừng gọi nữa."],
    },
    "khoa-tx": {
        "ask_identity": ["ai đó, em đang chạy", "bác là ai, em không lưu số"],
        "ask_purpose": ["việc gì nói nhanh đi", "em chưa hiểu"],
        "feign_confusion": ["khoan đã bác. em không ck và không cài app lạ. bác nói lại đi", "em là Khoa, đang chạy xe. không phải máy"],
        "stall": ["em chưa ck, chưa bấm gì. để em dừng xe đã", "khoan, em chưa làm theo"],
        "ask_link": ["link đâu, gửi em xem, em chưa mở"],
        "ask_transfer_destination": ["tiền về đâu, số nào"],
        "ask_account_number": ["số tài khoản đọc em ghi, em chưa ck"],
        "read_fake_otp": ["ví hiện mã {otp}. bác lấy làm gì, em chưa xác nhận"],
        "ask_next_instruction": ["bước sau là gì, em vẫn chưa làm"],
        "emotional_hook": ["em đang chạy, bác nói rõ không em không làm"],
        "probe_hook": ["bác nói {hook}. biết ở đâu ra"],
        "close_polite": ["thôi em rõ rồi. em không ck không cài. bác đừng gọi nữa"],
    },
}
