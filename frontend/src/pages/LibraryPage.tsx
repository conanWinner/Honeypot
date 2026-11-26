import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Banner } from '../components/ui'
import { api, type Script } from '../lib/api'
import { formatDay } from '../lib/utils'

type Meta = { categories: { id: string; label: string }[]; channels: { id: string; label: string }[] }

export function LibraryPage({ embedded = false }: { embedded?: boolean }) {
  const [params, setParams] = useSearchParams()
  const [meta, setMeta] = useState<Meta | null>(null)
  const [items, setItems] = useState<Script[] | null>(null)
  const [error, setError] = useState('')
  const q = params.get('q') ?? ''
  const category = params.get('category') ?? ''
  const channel = params.get('channel') ?? ''
  const roots = params.get('roots') !== '0'

  useEffect(() => {
    api<Meta>('/api/meta').then(setMeta).catch(() => setMeta(null))
  }, [])

  useEffect(() => {
    const query = new URLSearchParams()
    if (q) query.set('q', q)
    if (category) query.set('category', category)
    if (channel) query.set('channel', channel)
    if (roots && !q) query.set('roots_only', 'true')
    setItems(null)
    api<{ items: Script[] }>(`/api/scripts?${query.toString()}`)
      .then((data) => setItems(data.items))
      .catch((reason: Error) => setError(reason.message))
  }, [q, category, channel, roots])

  function update(next: Record<string, string>) {
    const merged = new URLSearchParams(params)
    Object.entries(next).forEach(([key, value]) => {
      if (value) merged.set(key, value)
      else merged.delete(key)
    })
    setParams(merged)
  }

  return (
    <div>
      {!embedded && (
        <>
          <p className="text-[11px] uppercase tracking-[0.16em] text-seal">Thư viện kịch bản</p>
          <h1 className="mt-2 font-display text-4xl">Cây kịch bản, không phải một đống tin nhắn</h1>
        </>
      )}
      <p className="mt-2 max-w-2xl text-sm leading-6 text-ink-soft">
        Mỗi gốc có các nhánh biến thể. Bản mới từ hội thoại nằm ở hàng chờ cho đến khi được duyệt.
      </p>
      <div className="mt-5 flex flex-col gap-3 md:flex-row">
        <input
          value={q}
          onChange={(event) => update({ q: event.target.value })}
          placeholder="Tìm OTP, công an, MoMo, shipper…"
          className="h-11 flex-1 rounded-full border border-line bg-card px-4 text-sm outline-none focus:border-ink"
        />
        <select
          value={category}
          onChange={(event) => update({ category: event.target.value })}
          className="h-11 rounded-full border border-line bg-card px-3 text-sm"
        >
          <option value="">Mọi loại</option>
          {meta?.categories.map((item) => (
            <option key={item.id} value={item.id}>
              {item.label}
            </option>
          ))}
        </select>
        <select
          value={channel}
          onChange={(event) => update({ channel: event.target.value })}
          className="h-11 rounded-full border border-line bg-card px-3 text-sm"
        >
          <option value="">Mọi kênh</option>
          {meta?.channels.map((item) => (
            <option key={item.id} value={item.id}>
              {item.label}
            </option>
          ))}
        </select>
      </div>
      <label className="mt-3 flex items-center gap-2 text-sm text-ink-soft">
        <input type="checkbox" checked={roots} onChange={(event) => update({ roots: event.target.checked ? '' : '0' })} />
        Chỉ hiện kịch bản gốc
      </label>
      {error && (
        <div className="mt-4">
          <Banner tone="danger">{error}</Banner>
        </div>
      )}
      {items === null && !error && <p className="mt-6 text-sm text-ink-soft">Đang xếp tủ…</p>}
      {items && items.length === 0 && <p className="mt-6 text-sm text-ink-soft">Không có kịch bản khớp bộ lọc này.</p>}
      <div className="mt-5 grid gap-3 md:grid-cols-2">
        {items?.map((script) => (
          <Link key={script.id} to={`/canh-bao/kich-ban/${script.id}`} className="dossier rounded-3xl p-5 hover:border-ink">
            <p className="text-[11px] uppercase tracking-[0.14em] text-gold">
              {script.category_label}
              {script.brand ? ` · ${script.brand}` : ''} · {script.channel_label}
            </p>
            <h2 className="mt-2 font-display text-2xl leading-tight">{script.title}</h2>
            <p className="mt-2 line-clamp-3 text-sm leading-6 text-ink-soft">{script.summary}</p>
            <p className="mt-3 text-xs text-ink-soft">
              {script.occurrence_count} lượt · {formatDay(script.first_seen)} → {formatDay(script.last_seen)}
              {script.variant_count ? ` · ${script.variant_count} nhánh` : ''}
              {script.parent_id ? ' · biến thể' : ''}
            </p>
          </Link>
        ))}
      </div>
    </div>
  )
}
