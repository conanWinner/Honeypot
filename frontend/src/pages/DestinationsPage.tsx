import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Banner, Button } from '../components/ui'
import { api, type ReceivingAccount } from '../lib/api'

type Payload = { items: ReceivingAccount[]; total: number; confirmed: number }

export function DestinationsPage() {
  const [data, setData] = useState<Payload | null>(null)
  const [error, setError] = useState('')
  const [onlyConfirmed, setOnlyConfirmed] = useState(false)

  useEffect(() => {
    api<Payload>('/api/intel/destinations')
      .then(setData)
      .catch((reason: Error) => setError(reason.message))
  }, [])

  if (error) return <Banner tone="danger">{error}</Banner>
  if (!data) return <p className="text-ink-soft">Đang gom nơi nhận tiền…</p>
  const rows = data.items.filter((row) => !onlyConfirmed || row.confirmed)
  const shared = data.items.filter((row) => row.stories.length > 1).length

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-[11px] uppercase tracking-[0.16em] text-seal">Gửi ngân hàng, ví điện tử</p>
          <h2 className="mt-1 font-display text-3xl">Nơi nhận tiền lừa đảo</h2>
          <p className="mt-1 max-w-2xl text-sm leading-6 text-ink-soft">
            Mọi tài khoản và ví kẻ gian đưa cho nạn nhân mồi, gộp theo số. Tài khoản xuất hiện ở nhiều chiêu khác nhau là dấu
            hiệu của cùng một đường dây.
          </p>
        </div>
        <Button asChild variant="seal" size="sm">
          <a href="/api/intel/destinations?format=csv">Tải CSV</a>
        </Button>
      </div>
      <section className="grid gap-3 sm:grid-cols-3">
        {[
          ['Nơi nhận tiền', data.total],
          ['Đã được kẻ gian xác nhận', data.confirmed],
          ['Dùng cho nhiều chiêu', shared],
        ].map(([label, value]) => (
          <div key={String(label)} className="dossier rounded-3xl p-4">
            <p className="font-display text-3xl text-seal">{value}</p>
            <p className="text-xs text-ink-soft">{label}</p>
          </div>
        ))}
      </section>
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={onlyConfirmed} onChange={(event) => setOnlyConfirmed(event.target.checked)} />
        Chỉ hiện nơi đã được xác nhận
      </label>
      {rows.length === 0 ? (
        <p className="text-sm text-ink-soft">Chưa có. Chạy một kịch bản ở tab Demo để thấy danh sách này đầy lên.</p>
      ) : (
        <div className="space-y-3">
          {rows.map((row) => (
            <article key={`${row.kind}-${row.value}`} className="dossier rounded-3xl p-4">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <p>
                  <span className="text-xs text-ink-soft">{row.kind_label}</span>{' '}
                  <span className="font-mono text-lg font-semibold">{row.value}</span>
                  {row.bank && <span className="text-sm"> · {row.bank}</span>}
                  {row.holders.length > 0 && <span className="text-sm text-ink-soft"> · {row.holders.join(', ')}</span>}
                </p>
                <span className="flex gap-2 text-xs">
                  {row.confirmed && <span className="rounded-full bg-[#e5f2ea] px-2 py-0.5 text-pine">Đã xác nhận</span>}
                  {row.stories.length > 1 && (
                    <span className="rounded-full bg-[#fde7ef] px-2 py-0.5 font-semibold text-seal-deep">{row.stories.length} chiêu khác nhau</span>
                  )}
                </span>
              </div>
              {row.stories.length > 0 && <p className="mt-1 text-sm">{row.stories.join(' · ')}</p>}
              <p className="mt-1 text-xs text-ink-soft">
                {row.count} cuộc hội thoại · lần cuối {row.last_seen.slice(0, 10)} · {row.action}
              </p>
              <div className="mt-2 flex flex-wrap gap-3 text-xs">
                {row.conversations.map((id) => (
                  <Link key={id} className="underline" to={`/phan-tich/ho-so/${id}`}>
                    Hồ sơ HP-{id.slice(0, 8).toUpperCase()}
                  </Link>
                ))}
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  )
}
