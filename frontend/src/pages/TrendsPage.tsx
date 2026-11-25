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
      <section className="grid gap-4 lg:grid-cols-2">
        <div className="dossier rounded-3xl p-5">
          <h2 className="font-display text-2xl">Theo loại</h2>
          <ul className="mt-4 space-y-3">
            {data.categories.map((item) => (
              <li key={item.id}>
                <div className="flex justify-between text-sm">
                  <span>{item.label}</span>
                  <span>{item.count}</span>
                </div>
                <div className="mt-1 h-2 rounded-full bg-paper-deep">
                  <div className="h-full rounded-full bg-seal" style={{ width: `${(item.count / maxCategory) * 100}%` }} />
                </div>
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
