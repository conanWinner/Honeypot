import { ClipboardCheck, Library, LineChart, MessageSquareText, Network, ScanSearch, Shield, TriangleAlert } from 'lucide-react'
import { useEffect, useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { api, type Health, type LlmHealth } from '../lib/api'
import { cn } from '../lib/utils'
import { Banner } from './ui'

const links = [
  { to: '/hoi-thoai', label: 'Hội thoại', icon: MessageSquareText },
  { to: '/thu-vien', label: 'Thư viện', icon: Library },
  { to: '/kiem-tra', label: 'Kiểm tra', icon: ScanSearch },
  { to: '/xu-huong', label: 'Xu hướng', icon: LineChart },
  { to: '/canh-bao', label: 'Cảnh báo', icon: TriangleAlert },
  { to: '/mang-luoi', label: 'Mạng lưới', icon: Network },
  { to: '/kiem-duyet', label: 'Duyệt', icon: ClipboardCheck },
]

export function Shell() {
  const [health, setHealth] = useState<Health | null>(null)
  const [llm, setLlm] = useState<LlmHealth | null>(null)
  const [offline, setOffline] = useState(false)

  useEffect(() => {
    api<Health>('/api/health')
      .then(setHealth)
      .catch(() => setOffline(true))
    api<LlmHealth>('/api/health/llm')
      .then(setLlm)
      .catch(() => setLlm(null))
  }, [])

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-30 border-b border-line/80 bg-[#f7f1e6]/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center gap-4 px-4 py-3">
          <NavLink to="/" className="flex items-center gap-3">
            <img src="/favicon.svg" alt="" width={36} height={36} />
            <span>
              <span className="block font-display text-xl leading-none text-ink">Honeypot</span>
              <span className="text-[11px] uppercase tracking-[0.16em] text-ink-soft">MoMo Tech Contest 2026</span>
            </span>
          </NavLink>
          <nav className="ml-6 hidden items-center gap-1 md:flex">
            {links.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                className={({ isActive }) =>
                  cn(
                    'rounded-full px-3 py-1.5 text-sm text-ink-soft',
                    isActive && 'bg-ink text-paper',
                  )
                }
              >
                {link.label}
              </NavLink>
            ))}
          </nav>
          <NavLink
            to="/demo"
            className="ml-auto rounded-full bg-seal px-4 py-2 text-sm font-semibold text-white"
          >
            Demo giám khảo
          </NavLink>
        </div>
      </header>
      <div className="mx-auto max-w-6xl px-4 pt-4">
        {offline && (
          <Banner tone="danger">Không nối được máy chủ. Kiểm tra API đang chạy ở cổng 8091.</Banner>
        )}
        {health?.llm.mock && (
          <Banner tone="warn">
            Chưa cấu hình khóa API — đang chạy chế độ mô phỏng. Gắn <b>LLM_API_KEY</b> cho router và{' '}
            <b>GEMINI_API_KEY</b> cho embedding, rồi khởi động lại. Luồng trên màn hình vẫn là pipeline thật, chỉ có lời
            của mô hình là heuristic.
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
      </div>
      <main className="mx-auto max-w-6xl px-4 py-6 pb-24 md:pb-10">
        <Outlet />
      </main>
      <nav className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-5 border-t border-line bg-[#f7f1e6] md:hidden">
        {links.map((link) => {
          const Icon = link.icon
          return (
            <NavLink
              key={link.to}
              to={link.to}
              className={({ isActive }) =>
                cn('flex flex-col items-center gap-1 py-2 text-[11px] text-ink-soft', isActive && 'text-seal')
              }
            >
              <Icon size={18} />
              {link.label}
            </NavLink>
          )
        })}
      </nav>
      <footer className="mx-auto hidden max-w-6xl items-center justify-between px-4 pb-8 text-xs text-ink-soft md:flex">
        <span className="inline-flex items-center gap-2">
          <Shield size={14} /> Honeypot — AI đóng vai nạn nhân, bóc kịch bản lừa đảo. Hồ sơ vai Giả Nạn là giả.
        </span>
        <span>Anti-fraud · hạn sơ khảo 03/12/2026</span>
      </footer>
    </div>
  )
}
