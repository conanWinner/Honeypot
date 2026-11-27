import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, type FreshScam } from '../lib/api'

function ago(iso: string) {
  const minutes = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000))
  if (minutes < 1) return 'vừa xong'
  if (minutes < 60) return `${minutes} phút trước`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours} giờ trước`
  return `${Math.round(hours / 24)} ngày trước`
}

/** Scams the honeypot caught and a reviewer published. Renders nothing when there are none. */
export function FreshScams({ compact = false }: { compact?: boolean }) {
  const [items, setItems] = useState<FreshScam[]>([])

  useEffect(() => {
    api<{ items: FreshScam[] }>('/api/library/fresh')
      .then((data) => setItems(data.items))
      .catch(() => setItems([]))
  }, [])

  if (items.length === 0) return null
  const shown = compact ? items.slice(0, 3) : items

  return (
    <section className="rounded-3xl border-2 border-seal/40 bg-[#fff1f5] p-5" aria-label="Chiêu mới ghi nhận">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <p className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-seal">
            <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-seal" />
            Chiêu mới ghi nhận
          </p>
          <h2 className="mt-1 font-display text-2xl">Honeypot vừa bắt được {items.length === 1 ? 'một chiêu mới' : `${items.length} chiêu mới`}</h2>
        </div>
        <p className="text-xs text-ink-soft">Kẻ gian tự kể chiêu cho nạn nhân mồi, người duyệt kiểm tra rồi mới công bố.</p>
      </div>
      <div className={`mt-4 grid gap-3 ${compact ? 'md:grid-cols-3' : 'md:grid-cols-2'}`}>
        {shown.map((item) => (
          <article key={item.id} className="rounded-2xl bg-card p-4">
            <p className="text-[11px] text-ink-soft">
              {item.relation === 'variant' ? `Nhánh mới của «${item.parent_title}»` : 'Chiêu mới'} · {ago(item.published_at)}
            </p>
            <h3 className="mt-1 font-display text-lg leading-snug">
              <Link to={`/canh-bao/kich-ban/${item.id}`} className="hover:underline">
                {item.title}
              </Link>
            </h3>
            {!compact && <p className="mt-1 text-sm leading-6 text-ink-soft">{item.summary}</p>}
            {item.red_flags.length > 0 && (
              <ul className="mt-2 flex flex-wrap gap-1 text-[11px]">
                {item.red_flags.map((flag) => (
                  <li key={flag} className="rounded-full border border-line px-2 py-0.5">
                    {flag}
                  </li>
                ))}
              </ul>
            )}
            {!compact && item.advice && <p className="mt-2 rounded-xl bg-[#e7f3ec] px-3 py-2 text-sm text-pine">{item.advice}</p>}
          </article>
        ))}
      </div>
      {compact && (
        <Link to="/canh-bao" className="mt-3 inline-block text-sm font-semibold underline">
          Xem tất cả cảnh báo
        </Link>
      )}
    </section>
  )
}
