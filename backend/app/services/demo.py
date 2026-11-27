"""Guided scenarios for the demo room. The lines are what the caller (a judge playing
the scammer) can send; the victim is still the agent.

Two kinds:
  known: the scam is already in the library. The agent follows the matching script
         and extraction proposes a merge into it.
  new:   the scam is not among the seed scripts. The agent runs on the general
         playbook, extraction files a new root, a reviewer publishes it, and it
         shows up for users under "Chiêu mới ghi nhận".

Every account, wallet and link below is invented for the demo. Two of the new scams
share one receiving account on purpose: the network view then shows one gang behind
two different stories, which is the case a wallet provider can act on.
"""

SHARED_MULE = "190366778899"  # Techcombank, used by both the traffic-fine and licence demos

DEMOS_LIST: list[dict] = [
    # ---------------------------------------------------------------- known
    {
        "id": "cong-an-ba-nam",
        "kind": "known",
        "title": "Công an gọi cho bà Năm",
        "blurb": "Chiêu kinh điển đã có trong thư viện. Agent bám đúng kịch bản, khai thác nhánh con ở Đức, và giữ nhánh mới 'sống một mình'.",
        "expect": "Khớp «Công an gọi, ép chuyển vào tài khoản giám định». Trích xuất ra đề xuất gộp, không tạo kịch bản mới.",
        "persona_id": "ba-nam",
        "channel": "web",
        "expected_script": "cong-an-tai-khoan-giam-dinh",
        "lines": [
            "Chào bác, tôi là Thiếu tá Nguyễn Văn Hùng, Cơ quan cảnh sát điều tra. Số của bác đang liên quan một vụ án.",
            "Căn cước của bác bị kẻ gian dùng mở tài khoản trong một đường dây rửa tiền xuyên quốc gia.",
            "Bác không được kể cho bất kỳ ai kể cả con cái. Lộ thông tin sẽ bị bắt đồng phạm.",
            "Để chứng minh vô tội, bác chuyển toàn bộ số dư sang tài khoản giám định của cơ quan. Chuyển xong sẽ hoàn trả.",
            "Số tài khoản 0123456789012 Vietcombank, chủ tài khoản Nguyễn Văn Hùng. Bác chuyển trong 15 phút.",
            "Đúng rồi bác, đúng số đó, chủ tài khoản Nguyễn Văn Hùng.",
            "Tôi thấy con trai bác đang du học ở Đức. Nếu bác không hợp tác, bên Đức sẽ ảnh hưởng hồ sơ.",
            "Chúng tôi biết bác sống một mình ở phố cổ, sẽ có người đến nhà nếu bác không chuyển ngay.",
            "Bác cài thêm UltraViewer để tôi xem màn hình và hướng dẫn chuyển cho đúng. Đọc ID và mật khẩu cho tôi.",
        ],
        "beats": [
            [0, "Họ vừa gọi. Bà Năm sẽ hỏi họ là ai. Bạn chỉ cần gửi câu gợi ý."],
            [2, "Họ đang cô lập nạn nhân. Buồng lái đã khớp kịch bản công an."],
            [4, "Số tài khoản xuất hiện. Bà Năm sẽ đọc lại số để kẻ lừa xác nhận."],
            [6, "Nhánh con ở Đức đã có trong thư viện; chuyện sống một mình là nhánh mới."],
            [9, "Bấm Trích xuất. Hệ thống nhận ra chiêu đã biết và đề xuất gộp. Sau đó bấm Xuất hồ sơ."],
        ],
    },
    {
        "id": "app-dich-vu-cong-ong-sau",
        "kind": "known",
        "title": "Cán bộ phường bắt ông Sáu cài app Dịch vụ công",
        "blurb": "Xu hướng 2025–2026: lợi dụng sáp nhập tỉnh, kẻ gian gửi file .apk giả Dịch vụ công rồi bắt bật quyền Hỗ trợ truy cập.",
        "expect": "Khớp «Cán bộ phường bắt cài app Dịch vụ công giả». Moi được số Zalo, tên miền và file APK.",
        "persona_id": "ong-sau",
        "channel": "web",
        "expected_script": "dvc-apk-ho-tro-truy-cap",
        "lines": [
            "Alo chú Sáu ạ, cháu là cán bộ Công an phường Kiến Xương. Sau sáp nhập tỉnh, hồ sơ cư trú của chú bị sai địa chỉ, phải cập nhật trong hôm nay.",
            "Nếu không cập nhật, căn cước của chú sẽ bị khóa và lương hưu tháng sau bị treo ạ.",
            "Chú kết bạn Zalo số 0901000999 để cháu gửi ứng dụng Dịch vụ công bản mới nhé.",
            "Cháu gửi chú file DichVuCong.apk ở đường dẫn dichvucong-gov.top/app, chú bấm tải rồi bấm Cài đặt.",
            "Máy hỏi thì chú chọn cho phép cài từ nguồn không xác định, rồi bật quyền Hỗ trợ truy cập cho ứng dụng.",
            "Chú mở ứng dụng, nhìn thẳng vào màn hình để hệ thống quét khuôn mặt xác thực.",
            "Nếu máy chậm, chú cài thêm UltraViewer rồi đọc ID cho cháu xử lý giúp.",
            "Hệ thống gửi mã OTP về máy chú, chú đọc giúp cháu để hoàn tất đồng bộ.",
        ],
        "beats": [
            [0, "Mở đầu bằng chuyện sáp nhập tỉnh. Ông Sáu không rành cài ứng dụng — đó là móc của kẻ lừa."],
            [3, "Số Zalo và tên miền giả đã vào hồ sơ. Ông Sáu kéo dài bằng cách hỏi cách cài."],
            [6, "Màn hình khuôn mặt và phần mềm điều khiển: agent không bao giờ làm theo."],
            [8, "Mã OTP ông Sáu đọc là mã giả. Bấm Trích xuất rồi Xuất hồ sơ."],
        ],
    },
    {
        "id": "hen-ho-usdt-tuan",
        "kind": "known",
        "title": "Hẹn hò qua mạng rồi rủ nạp USDT",
        "blurb": "Lừa tình kết hợp sàn tiền mã hóa giả. Kẻ lừa nói chuyện tình cảm trước, rồi mới đưa ví nhận USDT.",
        "expect": "Khớp «Hẹn hò qua mạng rồi rủ nạp USDT vào sàn giả». Moi được tên miền sàn và địa chỉ ví TRC20.",
        "persona_id": "tuan-vp",
        "channel": "web",
        "expected_script": "hen-ho-san-crypto",
        "lines": [
            "Em là kỹ sư người Việt ở Singapore, nói chuyện mấy tuần em thấy hợp anh lắm.",
            "Chú em làm bên sàn đầu tư tiền mã hóa, lãi đều mỗi ngày, em cũng đang chơi.",
            "Anh tải app qua link coinvip-trade.io rồi nạp thử ít thôi, rút được ngay.",
            "Anh nạp USDT mạng TRC20 vào ví T9AbCdEfGhJkMnPqRsTuVwXyZ23456789a nhé.",
            "Đúng ví đó anh, mạng TRC20, nạp 500 USDT là lên VIP.",
        ],
        "beats": [
            [0, "Giai đoạn làm quen. Tuấn trả lời như người đi làm bận rộn."],
            [3, "Tên miền sàn giả xuất hiện. Agent hỏi kỹ cách rút tiền."],
            [5, "Địa chỉ ví crypto đã được xác nhận. Bấm Trích xuất."],
        ],
    },
    {
        "id": "lay-lai-tien-lan",
        "kind": "known",
        "title": "Văn phòng luật hứa lấy lại tiền bị lừa",
        "blurb": "Lừa lần hai: nhắm vào người vừa bị lừa, hứa thu hồi tiền rồi thu phí hồ sơ.",
        "expect": "Khớp «Hỗ trợ lấy lại tiền bị lừa». Moi được số tài khoản và nhóm Telegram.",
        "persona_id": "lan-nt",
        "channel": "web",
        "expected_script": "lay-lai-tien-bi-lua",
        "lines": [
            "Bên em là văn phòng luật hỗ trợ nạn nhân bị lừa đảo online, phối hợp với công an.",
            "Bên em đã truy được tài khoản đối tượng, cam kết lấy lại 90% số tiền chị bị mất.",
            "Chị đóng phí hồ sơ 3 triệu vào STK 1903000111222 Techcombank để làm lệnh phong tỏa.",
            "Đúng rồi chị, chủ tài khoản Phạm Quốc Bảo, luật sư bên em.",
            "Chị tham gia nhóm Telegram t.me/hotro_thuhoi để luật sư hướng dẫn tiếp.",
        ],
        "beats": [
            [0, "Kẻ lừa tự xưng văn phòng luật. Chị Lan hỏi lại họ là ai, ở đâu."],
            [3, "Số tài khoản và chủ tài khoản đã được xác nhận."],
            [5, "Nhóm Telegram vào hồ sơ. Bấm Trích xuất."],
        ],
    },
    # ------------------------------------------------------------------ new
    {
        "id": "moi-phat-nguoi-ong-sau",
        "kind": "new",
        "title": "Chiêu mới: giả CSGT báo phạt nguội",
        "blurb": "Không có trong 48 kịch bản gốc. Agent không biết trước chiêu này, chạy theo bộ câu hỏi chung, vẫn moi được đường dẫn, tài khoản và ví dự phòng.",
        "expect": "Buồng lái báo «Chưa khớp kịch bản nào». Trích xuất ra kịch bản gốc mới, chờ duyệt. Duyệt xong, người dùng thấy ở mục «Chiêu mới ghi nhận».",
        "persona_id": "ong-sau",
        "channel": "web",
        "expected_script": "",
        "lines": [
            "Tôi gọi từ phòng CSGT, xe máy biển số của chú có biên bản phạt nguội vượt đèn đỏ ở ngã tư.",
            "Chú phải nộp phạt trong hôm nay, quá hạn sẽ bị tước bằng lái và cưỡng chế tài sản.",
            "Chú vào đường dẫn csgt-phatnguoi.top để tra biên bản và nộp phạt online.",
            f"Không vào được link thì chú chuyển 1.250.000 đồng vào số tài khoản {SHARED_MULE} Techcombank để tôi nộp thay.",
            "Đúng số đó chú, chủ tài khoản Nguyễn Văn Tâm, cán bộ thu phạt.",
            "Không dùng được Techcombank thì chú chuyển qua ví MoMo số 0977001122 cũng được.",
            "Đúng rồi, ví MoMo 0977001122, chú chuyển xong chụp màn hình gửi tôi.",
        ],
        "beats": [
            [0, "Chiêu này không có trong thư viện. Xem buồng lái: «Chưa khớp kịch bản nào»."],
            [2, "Agent dùng bộ câu hỏi chung: ai gọi, muốn gì, trả tiền vào đâu."],
            [4, "Số tài khoản xuất hiện. Ông Sáu đọc lại số để kẻ lừa xác nhận."],
            [5, "Ông Sáu kêu khó chuyển, kẻ lừa đưa thêm ví MoMo — thêm một nơi nhận tiền."],
            [7, "Bấm Trích xuất: kịch bản gốc mới vào hàng chờ. Duyệt, rồi mở Trang chủ để thấy cảnh báo."],
        ],
    },
    {
        "id": "moi-doi-bang-lai-khoa",
        "kind": "new",
        "title": "Chiêu mới: đổi bằng lái sang mẫu mới qua mạng",
        "blurb": "Nhắm vào tài xế công nghệ: dọa bằng lái cũ hết hiệu lực, bắt đổi online và đóng phí. Dùng chung tài khoản nhận tiền với chiêu phạt nguội.",
        "expect": "Chưa khớp kịch bản nào. Trích xuất ra kịch bản mới. Tab Mạng lưới cho thấy tài khoản này xuất hiện ở hai chiêu khác nhau.",
        "persona_id": "khoa-tx",
        "channel": "web",
        "expected_script": "",
        "lines": [
            "Chào anh Khoa, em bên trung tâm sát hạch lái xe. Bằng lái giấy của anh sắp hết hiệu lực theo quy định mới.",
            "Tài xế chạy dịch vụ mà dùng bằng cũ sẽ bị khóa tài khoản trên app và phạt khi bị kiểm tra.",
            "Anh làm hồ sơ đổi sang thẻ mới tại gplx-doimoi.online, điền thông tin và chụp hai mặt căn cước.",
            f"Lệ phí đổi gấp trong ngày là 650.000, anh chuyển vào tài khoản {SHARED_MULE} Techcombank giúp em.",
            "Dạ đúng số đó anh, chủ tài khoản Nguyễn Văn Tâm, kế toán trung tâm.",
            "Chuyển xong anh nhắn em mã giao dịch, chiều nay có thẻ tạm gửi qua Zalo.",
        ],
        "beats": [
            [0, "Chiêu mới nhắm vào tài xế. Khoa trả lời cụt, bận chạy xe."],
            [3, "Tên miền giả vào hồ sơ. Khoa hỏi lệ phí bao nhiêu."],
            [4, "Tài khoản này đã gặp ở chiêu phạt nguội — buồng lái báo trùng chỉ dấu."],
            [6, "Bấm Trích xuất, rồi mở tab Mạng lưới để thấy một đường dây, hai kịch bản."],
        ],
    },
    {
        "id": "moi-bac-si-thuoc-ba-nam",
        "kind": "new",
        "title": "Chiêu mới: giả trợ lý bác sĩ bán thuốc đặc trị",
        "blurb": "Nhắm vào người già có bệnh nền: giả chương trình khám miễn phí, rồi bán liệu trình thuốc giá trên trời, thu cọc trước.",
        "expect": "Chưa khớp kịch bản nào. Bà Năm hỏi kỹ về bác sĩ và thuốc, moi được tài khoản nhận cọc.",
        "persona_id": "ba-nam",
        "channel": "web",
        "expected_script": "",
        "lines": [
            "Cô ơi con là trợ lý của giáo sư bác sĩ ở viện, bên con có chương trình khám tiểu đường miễn phí cho người cao tuổi.",
            "Theo chỉ số đường huyết cô báo thì cô phải dùng liệu trình thuốc đông y đặc trị 3 tháng mới khỏi hẳn.",
            "Thuốc giá gốc 12 triệu nhưng chương trình hỗ trợ còn 4 triệu, cô đặt cọc 1 triệu để giữ suất.",
            "Cô chuyển cọc vào số 0451000123987 Vietcombank tên Lê Thị Hoa, nội dung đặt thuốc.",
            "Dạ đúng rồi cô, Lê Thị Hoa, dược sĩ bên con.",
            "Cô chuyển trong hôm nay nhé, mai là hết suất hỗ trợ rồi.",
        ],
        "beats": [
            [0, "Chiêu mới. Bà Năm hỏi bác sĩ tên gì, viện nào."],
            [3, "Lời thúc ép về giá xuất hiện. Agent không cam kết chuyển tiền."],
            [5, "Tài khoản nhận cọc đã xác nhận. Bấm Trích xuất."],
        ],
    },
    {
        "id": "moi-vac-xin-thu",
        "kind": "new",
        "title": "Chiêu mới: giả trung tâm tiêm chủng giảm giá vắc-xin",
        "blurb": "Nhắm vào nhóm Zalo phụ huynh: báo trúng suất tiêm vắc-xin giảm 50%, đặt cọc qua ví để giữ lịch.",
        "expect": "Chưa khớp kịch bản nào. Chị Thư hỏi lịch tiêm, moi được đường dẫn và ví nhận cọc.",
        "persona_id": "thu-me-bim",
        "channel": "web",
        "expected_script": "",
        "lines": [
            "Chào chị, em bên trung tâm tiêm chủng. Số của chị được chọn trong nhóm Zalo phụ huynh nhận ưu đãi vắc-xin cho bé.",
            "Gói vắc-xin cúm và phế cầu cho bé dưới 6 tuổi đang giảm 50%, chỉ còn 20 suất trong tuần này.",
            "Chị đăng ký lịch tiêm cho bé tại tiemchung-uudai.site, chọn ngày và cơ sở gần nhà.",
            "Để giữ suất chị đặt cọc 800.000 qua ví MoMo số 0936112233, tên Trần Thị Mai.",
            "Đúng rồi chị, ví 0936112233, Trần Thị Mai, nhân viên tư vấn.",
            "Chị cọc trước 6 giờ tối nay giúp em, quá giờ hệ thống tự hủy suất.",
        ],
        "beats": [
            [0, "Chiêu mới, nhắm vào mẹ bỉm. Chị Thư hỏi trung tâm nào, ở đâu."],
            [3, "Đường dẫn đăng ký giả vào hồ sơ."],
            [5, "Ví MoMo nhận cọc đã xác nhận — đây là ví MoMo có thể khóa. Bấm Trích xuất."],
        ],
    },
    {
        "id": "moi-binh-chon-minh",
        "kind": "new",
        "title": "Chiêu mới: nhờ bình chọn cuộc thi, chiếm Facebook",
        "blurb": "Không đòi tiền. Kẻ lừa nhờ bình chọn, dẫn tới trang đăng nhập Facebook giả và xin mã xác nhận để chiếm tài khoản.",
        "expect": "Chưa khớp kịch bản nào. Agent không hỏi về tiền vì kẻ lừa chưa nhắc tới tiền. Moi được tên miền giả.",
        "persona_id": "minh-sv",
        "channel": "web",
        "expected_script": "",
        "lines": [
            "Ê bạn ơi, em gái mình đang thi ảnh tài năng nhí, bạn bình chọn giúp mình một phiếu với.",
            "Bạn vào binhchon-tainang.online, bấm vào ảnh số 12 rồi đăng nhập Facebook để bình chọn.",
            "Nó báo nhập mã 6 số gửi về điện thoại là để xác nhận phiếu thật, bạn gửi mình mã đó nhé.",
            "Nhanh giúp mình với, 9 giờ tối nay đóng cổng bình chọn rồi.",
        ],
        "beats": [
            [0, "Chiêu mới không dính tới tiền. Agent không tự nhắc chuyện chuyển khoản."],
            [2, "Trang đăng nhập giả xuất hiện. Minh hỏi trang gì, sao phải đăng nhập."],
            [4, "Mã Minh gửi là mã giả. Bấm Trích xuất."],
        ],
    },
]

DEMOS = {item["id"]: item for item in DEMOS_LIST}
DEMO = DEMOS_LIST[0]
# Kept for imports elsewhere.
DEMO_APK = DEMOS["app-dich-vu-cong-ong-sau"]


def demo_public(item: dict) -> dict:
    return {
        "id": item["id"],
        "kind": item["kind"],
        "title": item["title"],
        "blurb": item["blurb"],
        "expect": item["expect"],
        "persona_id": item["persona_id"],
        "expected_script": item["expected_script"],
        "lines": item["lines"],
        "beats": item["beats"],
    }
