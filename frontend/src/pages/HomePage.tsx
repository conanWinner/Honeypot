import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'
import { Button } from '../components/ui'

type Stats = { published_scripts: number; pending_scripts: number; conversations: number }

const nodes = [
  ['Phân tích', 'Mỗi lượt của đối phương được tách ý định, bước, cờ đỏ, rồi đối chiếu thư viện bằng embedding và rerank.'],
  ['Lập kế hoạch', 'Agent chọn mục tiêu kế tiếp: hỏi danh tính, xin link, hỏi số tài khoản, trì hoãn, hoặc đào một nhánh mới.'],
  ['Đóng vai', 'Một persona Việt có hồ sơ giả, nhớ những gì đã nói, nhắn theo đúng giọng, và không nhận mình là máy.'],
  ['An toàn', 'Luật chặn nhận là AI, đồng ý chuyển tiền, cài phần mềm, hoặc lộ số không có trong hồ sơ giả. Mô hình không được tự bỏ luật.'],
]

export function HomePage() {
  const [stats, setStats] = useState<Stats | null>(null)
  useEffect(() => {
    api<Stats>('/api/stats').then(setStats).catch(() => setStats(null))
  }, [])

  return (
    <div className="space-y-8">
      <section className="grid items-end gap-8 lg:grid-cols-[1.3fr_0.7fr]">
        <div>
          <p className="text-[11px] uppercase tracking-[0.18em] text-seal">Anti-fraud · sơ khảo 03/12/2026</p>
          <h1 className="mt-3 max-w-3xl font-display text-5xl leading-[1.05] text-ink md:text-6xl">
            Biết mình đang bị lừa? Để một người giả đóng nạn nhân.
          </h1>
          <p className="mt-4 max-w-2xl text-lg leading-8 text-ink-soft">
            Giả Nạn nhận cuộc thoại, đóng vai người bị gọi, và kéo đối phương nói hết kịch bản. Mỗi cuộc thành một hồ sơ
            có bước, cờ đỏ và lời khuyên, đưa vào thư viện để người khác khỏi mắc.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Button asChild variant="seal">
              <Link to="/hoi-thoai">Mở cuộc hội thoại</Link>
            </Button>
            <Button asChild variant="ghost">
              <Link to="/demo">Chạy demo một nhịp</Link>
            </Button>
            <Button asChild variant="quiet">
              <Link to="/thu-vien">Xem thư viện</Link>
            </Button>
          </div>
        </div>
        <aside className="dossier rounded-3xl p-5">
          <p className="text-[11px] uppercase tracking-[0.16em] text-ink-soft">Đang có trong tủ</p>
          <dl className="mt-4 grid grid-cols-3 gap-3">
            {[
              ['Kịch bản', stats?.published_scripts],
              ['Chờ duyệt', stats?.pending_scripts],
              ['Hội thoại', stats?.conversations],
            ].map(([label, value]) => (
              <div key={String(label)}>
                <dt className="text-xs text-ink-soft">{label}</dt>
                <dd className="font-display text-3xl">{value ?? '—'}</dd>
              </div>
            ))}
          </dl>
          <p className="mt-4 text-sm leading-6 text-ink-soft">
            28 kịch bản gốc, viết từ các chiêu đã được báo chí và cơ quan chức năng mô tả công khai, kèm nhánh biến thể.
          </p>
        </aside>
      </section>

      <section className="grid gap-3 md:grid-cols-3">
        {[
          ['01', 'Đưa hội thoại', 'Bạn chơi vai kẻ lừa, hoặc dán tin nhắn đầu. Web là kênh đang chạy. Telegram và thoại dùng cùng agent, vận chuyển gắn sau.'],
          ['02', 'Agent giữ nhịp', 'Không dừng ở câu chào. Mỗi lượt cập nhật bước, độ tin cậy, và báo nếu đối phương vừa bịa một hoàn cảnh riêng.'],
          ['03', 'Kịch bản vào tủ', 'Kết thúc là một hồ sơ có cấu trúc. Trùng thì cộng lượt. Nhánh mới thì chờ duyệt trước khi công bố.'],
        ].map(([index, title, body]) => (
          <article key={index} className="dossier rounded-3xl p-5">
            <p className="font-display text-3xl text-seal">{index}</p>
            <h2 className="mt-2 text-lg font-semibold">{title}</h2>
            <p className="mt-2 text-sm leading-6 text-ink-soft">{body}</p>
          </article>
        ))}
      </section>

      <section>
        <h2 className="font-display text-3xl">Bốn nút của agent</h2>
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          {nodes.map(([title, body], index) => (
            <article key={title} className="dossier rounded-3xl p-5">
              <p className="text-[11px] uppercase tracking-[0.16em] text-gold">Nút {index + 1}</p>
              <h3 className="mt-1 text-xl font-semibold">{title}</h3>
              <p className="mt-2 text-sm leading-6 text-ink-soft">{body}</p>
            </article>
          ))}
        </div>
      </section>
    </div>
  )
}
