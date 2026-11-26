import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Banner } from '../components/ui'
import { api } from '../lib/api'

type Brief = {
  id: string
  title: string
  category_label: string
  brand: string
  occurrence_count: number
  first_seen: string
  last_seen: string
}

type Trends = {
  total: number
  variants: number
  categories: { id: string; label: string; count: number }[]
  brands: { name: string; count: number }[]
  by_month: { month: string; count: number }[]
  newest: Brief[]
  rising: Brief[]
  emerging?: { id: string; label: string; new_scripts: number; total: number; new_branches_30d: number; score: number }[]
  watch?: { id: string; title: string; rising: boolean; first_reported: string; scripts: number; source: { title: string; url: string } | null }[]
  stats?: { label: string; value: string; url: string }[]
}

export function TrendsPage() {
  const [data, setData] = useState<Trends | null>(null)
  const [error, setError] = useState('')
  useEffect(() => {
    api<Trends>('/api/trends').then(setData).catch((reason: Error) => setError(reason.message))
  }, [])
  if (error) return <Banner tone="danger">{error}</Banner>
  if (!data) return <p className="text-ink-soft">Đang gom số liệu…</p>
  const maxCategory = Math.max(...data.categories.map((item) => item.count), 1)
  const maxMonth = Math.max(...data.by_month.map((item) => item.count), 1)

  return (
    <div className="space-y-6">
      <div>
        <p className="text-[11px] uppercase tracking-[0.16em] text-seal">Xu hướng</p>
        <h1 className="mt-2 font-display text-4xl">Kịch bản nào đang được ghi nhận</h1>
        <p className="mt-2 text-sm text-ink-soft">
          {data.total} hồ sơ công khai, trong đó {data.variants} nhánh. Mốc thời gian lấy từ lần đầu thấy và lần thấy gần nhất của từng kịch bản.
        </p>
      </div>
      {data.emerging && data.emerging.length > 0 && (
        <section className="dossier rounded-3xl p-5">
          <h2 className="font-display text-2xl">Đang nổi lên</h2>
          <ul className="mt-3 space-y-2 text-sm">
            {data.emerging.map((item) => (
              <li key={item.id}>
                {item.label}: {item.new_scripts}/{item.total} kịch bản mới
              </li>
            ))}
          </ul>
        </section>
      )}
      {data.watch && data.watch.length > 0 && (
        <section className="dossier rounded-3xl p-5">
          <h2 className="font-display text-2xl">Theo dõi phương thức</h2>
          <ul className="mt-3 space-y-2 text-sm">
            {data.watch.map((item) => (
              <li key={item.id}>
                <Link className="underline" to={`/canh-bao#${item.id}`}>
                  {item.rising ? '▲ ' : ''}
                  {item.title}
                </Link>
                <span className="text-ink-soft"> · {item.scripts} kịch bản</span>
              </li>
            ))}
          </ul>
        </section>
      )}
      <section className="grid gap-4 lg:grid-cols-2">
        <div className="dossier rounded-3xl p-5">
          <h2 className="font-display text-2xl">Theo loại</h2>
          <svg viewBox={`0 0 ${Math.max(data.categories.length, 1) * 36} 160`} className="mt-4 h-40 w-full">
            {data.categories.map((item, index) => {
              const height = (item.count / maxCategory) * 130
              return (
                <g key={item.id}>
                  <rect x={index * 36 + 8} y={140 - height} width={18} height={height} rx={4} fill="#d6336c" />
                  <text x={index * 36 + 17} y={156} textAnchor="middle" fontSize="8" fill="#5e564c">
                    {item.count}
                  </text>
                </g>
              )
            })}
          </svg>
          <ul className="mt-2 space-y-1 text-xs text-ink-soft">
            {data.categories.map((item) => (
              <li key={item.id}>
                {item.label} · {item.count}
              </li>
            ))}
          </ul>
        </div>
        <div className="dossier rounded-3xl p-5">
          <h2 className="font-display text-2xl">Lần đầu thấy, theo tháng</h2>
          <div className="mt-4 flex h-40 items-end gap-2">
            {data.by_month.map((item) => (
              <div key={item.month} className="flex flex-1 flex-col items-center gap-1">
                <div className="w-full rounded-t-md bg-ink" style={{ height: `${(item.count / maxMonth) * 100}%` }} />
                <span className="text-[10px] text-ink-soft">{item.month.slice(2)}</span>
              </div>
            ))}
          </div>
          <h2 className="mt-6 font-display text-2xl">Thương hiệu bị mạo danh</h2>
          <ul className="mt-3 flex flex-wrap gap-2">
            {data.brands.map((brand) => (
              <li key={brand.name} className="rounded-full bg-paper-deep px-3 py-1 text-sm">
                {brand.name} · {brand.count}
              </li>
            ))}
          </ul>
        </div>
      </section>
      <section className="grid gap-4 lg:grid-cols-2">
        <List title="Đang nóng" items={data.rising} empty="Chưa có kịch bản được ghi nhận trong 45 ngày gần đây." />
        <List title="Mới vào tủ" items={data.newest} empty="Thư viện đang trống." />
      </section>
    </div>
  )
}

function List({ title, items, empty }: { title: string; items: Brief[]; empty: string }) {
  return (
    <div className="dossier rounded-3xl p-5">
      <h2 className="font-display text-2xl">{title}</h2>
      <ul className="mt-3 space-y-3">
        {items.length === 0 && <li className="text-sm text-ink-soft">{empty}</li>}
        {items.map((item) => (
          <li key={item.id}>
            <Link to={`/kich-ban/${item.id}`} className="font-medium underline">
              {item.title}
            </Link>
            <p className="text-xs text-ink-soft">
              {item.category_label}
              {item.brand ? ` · ${item.brand}` : ''} · {item.occurrence_count} lượt · {item.last_seen}
            </p>
          </li>
        ))}
      </ul>
    </div>
  )
}
