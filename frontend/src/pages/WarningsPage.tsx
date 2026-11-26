import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Banner } from '../components/ui'
import { api, type WarningCard } from '../lib/api'

type Payload = { cards: WarningCard[]; stats: { label: string; value: string; url: string }[] }

export function WarningsPage() {
  const [data, setData] = useState<Payload | null>(null)
  const [error, setError] = useState('')
  const [filter, setFilter] = useState<'all' | 'rising'>('all')
  const location = useLocation()
  useEffect(() => {
    api<Payload>('/api/warnings').then(setData).catch((reason: Error) => setError(reason.message))
  }, [])
  useEffect(() => {
    if (!data || !location.hash) return
    document.getElementById(location.hash.slice(1))?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [data, location.hash])
  if (error) return <Banner tone="danger">{error}</Banner>
  if (!data) return <p className="text-ink-soft">Đang tải thẻ cảnh báo…</p>
  const cards = data.cards.filter((card) => filter === 'all' || card.rising)

  async function copy(card: WarningCard) {
    const text = `${card.title}\n${card.how.join('\n')}\nNên làm: ${card.do}`
    try {
      await navigator.clipboard.writeText(text)
    } catch {
      /* clipboard may be blocked */
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <p className="text-[11px] uppercase tracking-[0.16em] text-seal">Thẻ cảnh báo công khai</p>
        <h1 className="mt-2 font-display text-4xl">Các chiêu lừa đang lưu hành</h1>
        <div className="mt-3 flex gap-2">
          <button onClick={() => setFilter('all')} className={`rounded-full px-3 py-1 text-sm ${filter === 'all' ? 'bg-ink text-paper' : 'border border-line bg-card'}`}>
            Tất cả ({data.cards.length})
          </button>
          <button onClick={() => setFilter('rising')} className={`rounded-full px-3 py-1 text-sm ${filter === 'rising' ? 'bg-ink text-paper' : 'border border-line bg-card'}`}>
            Đang nổi ({data.cards.filter((card) => card.rising).length})
          </button>
        </div>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        {cards.map((card) => (
          <article key={card.id} id={card.id} className="dossier scroll-mt-24 rounded-3xl p-5">
            <h2 className="font-display text-2xl leading-tight">{card.title}</h2>
            <p className="mt-1 text-sm text-ink-soft">Nhắm vào: {card.targets}</p>
            <ol className="mt-3 list-decimal space-y-1 pl-5 text-sm">
              {card.how.map((step) => (
                <li key={step}>{step}</li>
              ))}
            </ol>
            <p className="mt-3 rounded-2xl bg-[#e7f3ec] px-3 py-2 text-sm text-pine">{card.do}</p>
            <ul className="mt-3 space-y-0.5 text-xs">
              {card.sources.map((src) => (
                <li key={src.url}>
                  <a className="underline" href={src.url} target="_blank" rel="noreferrer">
                    {src.title}
                  </a>
                </li>
              ))}
            </ul>
            <div className="mt-4 flex gap-2">
              <button onClick={() => void copy(card)} className="rounded-full border border-line bg-card px-3 py-1 text-xs font-semibold">
                Chép để gửi
              </button>
              <Link to={`/thu-vien?category=${card.categories[0]}`} className="rounded-full border border-line bg-card px-3 py-1 text-xs font-semibold">
                Kịch bản liên quan
              </Link>
            </div>
          </article>
        ))}
      </div>
    </div>
  )
}
