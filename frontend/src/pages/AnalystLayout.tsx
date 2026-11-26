import { useEffect, useState } from 'react'
import { NavLink, Outlet, useOutletContext } from 'react-router-dom'
import type { ShellState } from '../components/Shell'
import { Banner } from '../components/ui'
import { api } from '../lib/api'
import { cn } from '../lib/utils'

const tabs = [
  { to: '/phan-tich/hoi-thoai', label: 'Hội thoại' },
  { to: '/phan-tich/mang-luoi', label: 'Mạng lưới' },
  { to: '/phan-tich/kiem-duyet', label: 'Kiểm duyệt' },
  { to: '/phan-tich/demo', label: 'Demo' },
  { to: '/phan-tich', label: 'Trạng thái hệ thống', end: true },
  { to: '/phan-tich/kien-truc', label: 'Kiến trúc agent' },
]

export function AnalystLayout() {
  const state = useOutletContext<ShellState>()
  return (
    <div className="space-y-5">
      <div>
        <p className="text-[11px] uppercase tracking-[0.16em] text-gold">Dành cho người vận hành</p>
        <h1 className="mt-1 font-display text-3xl">Phòng phân tích</h1>
      </div>
      <nav className="flex flex-wrap gap-2">
        {tabs.map((tab) => (
          <NavLink
            key={tab.to}
            to={tab.to}
            end={tab.end}
            className={({ isActive }) =>
              cn('rounded-full px-3 py-1.5 text-sm', isActive ? 'bg-ink text-paper' : 'border border-line bg-card text-ink-soft')
            }
          >
            {tab.label}
          </NavLink>
        ))}
      </nav>
      <Outlet context={state} />
    </div>
  )
}

export function SystemStatusPage() {
  const { health, llm, offline } = useOutletContext<ShellState>()
  return (
    <section className="dossier space-y-3 rounded-3xl p-5">
      <h2 className="font-display text-2xl">Trạng thái hệ thống</h2>
      {offline && <Banner tone="danger">Không nối được máy chủ. Kiểm tra API đang chạy ở cổng 8091.</Banner>}
      {health?.llm.mock && (
        <Banner tone="warn">
          Chưa cấu hình khóa API — đang chạy chế độ mô phỏng. Gắn <b>LLM_API_KEY</b> cho router và <b>GEMINI_API_KEY</b> cho
          embedding, rồi khởi động lại. Luồng trên màn hình vẫn là pipeline thật, chỉ có lời của mô hình là heuristic.
        </Banner>
      )}
      {health && !health.llm.mock && (
        <Banner tone="ok">
          Đang dùng mô hình thật: {health.llm.provider} · {health.llm.model}. Embedding: {health.embeddings.ready}/
          {health.embeddings.published} kịch bản.
          {llm && !llm.mock && (
            <span>
              {' '}
              Router {llm.warming ? 'đang làm nóng' : llm.ok ? `đã nóng ${llm.latency_ms} ms` : 'chưa trả lời'}.
            </span>
          )}
        </Banner>
      )}
      {!health && !offline && <p className="text-sm text-ink-soft">Đang hỏi máy chủ…</p>}
    </section>
  )
}

const nodes = [
  ['Phân tích', 'Mỗi lượt của đối phương được tách ý định, bước, cờ đỏ, rồi đối chiếu thư viện bằng embedding và rerank.'],
  ['Lập kế hoạch', 'Agent chọn mục tiêu kế tiếp: hỏi danh tính, xin link, hỏi số tài khoản, trì hoãn, hoặc đào một nhánh mới.'],
  ['Đóng vai', 'Một persona Việt có hồ sơ giả, nhớ những gì đã nói, nhắn theo đúng giọng, và không nhận mình là máy.'],
  ['An toàn', 'Luật chặn nhận là AI, đồng ý chuyển tiền, cài phần mềm, hoặc lộ số không có trong hồ sơ giả. Mô hình không được tự bỏ luật.'],
]

export function ArchitecturePage() {
  const [stats, setStats] = useState<{ published_scripts: number; pending_scripts: number; conversations: number } | null>(null)
  useEffect(() => {
    api<{ published_scripts: number; pending_scripts: number; conversations: number }>('/api/stats')
      .then(setStats)
      .catch(() => setStats(null))
  }, [])
  return (
    <div className="space-y-4">
      <aside className="dossier rounded-3xl p-5">
        <p className="text-[11px] uppercase tracking-[0.16em] text-seal">Vấn đề</p>
        <p className="mt-2 font-display text-5xl text-seal">32%</p>
        <p className="mt-1 text-sm leading-6 text-ink-soft">
          nạn nhân trình báo, theo khảo sát NCA. 68% còn lại không để lại kịch bản cho ai học.
        </p>
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
      </aside>
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
