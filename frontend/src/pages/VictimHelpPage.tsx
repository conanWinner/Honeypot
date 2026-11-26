import { Link } from 'react-router-dom'

const steps = [
  {
    title: 'Gọi ngân hàng, khóa tài khoản và ví',
    body: 'Dùng số tổng đài in trên thẻ hoặc trong ứng dụng chính thức của ngân hàng và ví. Không gọi lại số vừa nhắn cho bạn.',
  },
  {
    title: 'Lưu bằng chứng',
    body: 'Chụp tin nhắn, số điện thoại, số tài khoản, đường dẫn, và giờ giao dịch. Không xóa cuộc trò chuyện.',
  },
  {
    title: 'Trình báo nơi gần nhất',
    body: 'Đến công an phường, xã gần nhất hoặc cổng dịch vụ công. Mang theo căn cước và bằng chứng vừa lưu.',
  },
  {
    title: 'Cảnh giác chiêu “lấy lại tiền”',
    body: 'Người lạ hứa thu hồi tiền rồi đòi phí hồ sơ là một vụ lừa nữa. Công an không thu phí để trả lại tiền.',
  },
]

export function VictimHelpPage() {
  return (
    <div className="mx-auto max-w-2xl space-y-5">
      <div>
        <p className="text-[11px] uppercase tracking-[0.16em] text-seal">Vừa xảy ra</p>
        <h1 className="mt-2 font-display text-4xl">Tôi vừa bị lừa</h1>
        <p className="mt-2 text-sm leading-6 text-ink-soft">Làm bốn việc sau, theo đúng thứ tự. Không chuyển thêm bất kỳ khoản nào.</p>
      </div>
      <ol className="space-y-3">
        {steps.map((step, index) => (
          <li key={step.title} className="dossier rounded-3xl p-5">
            <p className="font-display text-3xl text-seal">{index + 1}</p>
            <h2 className="mt-1 text-lg font-semibold">{step.title}</h2>
            <p className="mt-2 text-sm leading-6 text-ink-soft">{step.body}</p>
          </li>
        ))}
      </ol>
      <p className="text-sm">
        Đọc chiêu lấy lại tiền:{' '}
        <Link className="font-semibold underline" to="/canh-bao#lay-lai-tien-bi-lua">
          Hỗ trợ lấy lại tiền bị lừa
        </Link>
        .
      </p>
    </div>
  )
}
