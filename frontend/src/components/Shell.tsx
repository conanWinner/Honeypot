import { Flag, GraduationCap, House, Shield, TriangleAlert } from 'lucide-react'
import { useEffect, useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { api, type Health, type LlmHealth } from '../lib/api'
import { cn } from '../lib/utils'

const desktop = [
  { to: '/', label: 'Trang chủ', end: true },
  { to: '/luyen-tap', label: 'Luyện tập', end: false },
  { to: '/canh-bao', label: 'Cảnh báo', end: false },
  { to: '/xu-huong', label: 'Xu hướng', end: false },
]

const mobile = [
  { to: '/', label: 'Trang chủ', icon: House, end: true },
  { to: '/luyen-tap', label: 'Luyện tập', icon: GraduationCap, end: false },
  { to: '/canh-bao', label: 'Cảnh báo', icon: TriangleAlert, end: false },
  { to: '/bao-cao', label: 'Báo cáo', icon: Flag, end: false },
]

export type ShellState = {
  health: Health | null
  llm: LlmHealth | null
  offline: boolean
}

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

  const state: ShellState = { health, llm, offline }

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-30 border-b border-line/80 bg-[#f7f1e6]/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center gap-3 px-4 py-3">
          <NavLink to="/" className="flex items-center gap-3">
            <img src="/favicon.svg" alt="" width={36} height={36} />
            <span>
              <span className="block font-display text-xl leading-none text-ink">Honeypot</span>
              <span className="text-[11px] uppercase tracking-[0.16em] text-ink-soft">Chống lừa đảo</span>
            </span>
          </NavLink>
          <nav className="ml-4 hidden items-center gap-1 lg:flex">
            {desktop.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                end={link.end}
                className={({ isActive }) =>
                  cn('rounded-full px-3 py-1.5 text-sm text-ink-soft', isActive && 'bg-ink text-paper')
                }
              >
                {link.label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <NavLink
              to="/phan-tich"
              className={({ isActive }) =>
                cn(
                  'hidden rounded-full border border-dashed border-ink/30 px-3 py-1.5 text-xs text-ink-soft md:inline-flex',
                  isActive && 'border-ink text-ink',
                )
              }
            >
              Phòng phân tích
            </NavLink>
            <NavLink to="/bao-cao" className="rounded-full bg-seal px-4 py-2 text-sm font-semibold text-white">
              Báo cáo lừa đảo
            </NavLink>
          </div>
        </div>
      </header>
      {offline && (
        <div className="mx-auto max-w-6xl px-4 pt-4">
          <p className="rounded-2xl border border-line bg-card px-4 py-3 text-sm text-ink-soft">
            Chưa nối được máy chủ. Một số số liệu sẽ hiện khi API chạy lại.
          </p>
        </div>
      )}
      <main className="mx-auto max-w-6xl px-4 py-6 pb-28 md:pb-10">
        <Outlet context={state} />
      </main>
      {health?.llm.mock && (
        <p className="px-4 pb-2 text-center text-xs text-ink-soft md:hidden">Chế độ mô phỏng — chưa gắn khóa model</p>
      )}
      <nav className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-4 border-t border-line bg-[#f7f1e6] md:hidden">
        {mobile.map((link) => {
          const Icon = link.icon
          return (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.end}
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
          <Shield size={14} /> Honeypot — nhận diện lừa đảo, luyện phản xạ, và giữ kịch bản cho người sau.
        </span>
        <span>{health?.llm.mock ? 'Chế độ mô phỏng — chưa gắn khóa model' : 'Anti-fraud · hạn sơ khảo 03/12/2026'}</span>
      </footer>
    </div>
  )
}
