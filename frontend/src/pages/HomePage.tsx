import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { CheckResult } from '../components/CheckResult'
import { Button } from '../components/ui'
import { api, type CheckResult as CheckResultData, type IntelHit, type WarningCard } from '../lib/api'

type Stats = { published_scripts: number; pending_scripts: number; conversations: number }
type Kind = 'tin' | 'sdt' | 'stk' | 'link'

const samples = [
  { label: 'Giả công an', text: 'Tôi là thiếu tá cơ quan cảnh sát điều tra. Anh chuyển toàn bộ số dư sang tài khoản giám định, không được kể cho ai.' },
  { label: 'Đơn hàng COD', text: 'Đơn hàng của bạn không phát được do sai địa chỉ. Bấm link thanh toán phí ship 25 nghìn.' },
  { label: 'Việc làm online', text: 'Bạn được chọn làm nhiệm vụ bình chọn. Chuyển trước một khoản nhỏ để nhận hoa hồng ngay trong hôm nay.' },
  { label: 'Mã QR', text: 'Quét mã QR này để thanh toán. Tên tài khoản khác là của kế toán, shop đổi mã mới.' },
]

const kinds: { id: Kind; label: string }[] = [
  { id: 'tin', label: 'Tin nhắn' },
  { id: 'sdt', label: 'SĐT' },
  { id: 'stk', label: 'STK' },
  { id: 'link', label: 'Link' },
]

export function HomePage() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [warnings, setWarnings] = useState<WarningCard[]>([])
  const [kind, setKind] = useState<Kind>('tin')
  const [text, setText] = useState('')
  const [result, setResult] = useState<CheckResultData | null>(null)
  const [hits, setHits] = useState<IntelHit[]>([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api<Stats>('/api/stats').then(setStats).catch(() => setStats(null))
    api<{ cards: WarningCard[] }>('/api/warnings')
      .then((data) => setWarnings(data.cards))
      .catch(() => setWarnings([]))
  }, [])

  async function run(value = text) {
    const body = value.trim()
    if (body.length < 8) return
    setBusy(true)
    setError('')
    setResult(null)
    setHits([])
    try {
      const checked = await api<CheckResultData>('/api/check', { method: 'POST', body: JSON.stringify({ text: body }) })
      setResult(checked)
      if (kind !== 'tin') {
        const found = await api<{ hits: IntelHit[] }>(`/api/intel/lookup?value=${encodeURIComponent(body)}`)
        setHits(found.hits)
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Không kiểm tra được.')
    } finally {
      setBusy(false)
    }
  }

  const rising = warnings.filter((card) => card.rising).slice(0, 3)
  const latest = warnings.slice(0, 4)

  return (
    <div className="space-y-8">
      <section className="rounded-[2rem] border border-line bg-card/80 px-4 py-8 text-center md:px-10">
        <h1 className="font-display text-4xl leading-tight text-ink md:text-5xl">Tin nhắn này có phải lừa đảo không?</h1>
        <p className="mx-auto mt-3 max-w-2xl text-base leading-7 text-ink-soft">
          Dán tin nhắn, số điện thoại, số tài khoản, đường link hoặc ví crypto — Honeypot đối chiếu với kho kịch bản thật.
        </p>
        <div className="mx-auto mt-5 flex max-w-3xl flex-col gap-3 text-left">
          <div className="flex flex-wrap gap-2">
            {kinds.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setKind(item.id)}
                className={`rounded-full px-3 py-1 text-sm ${kind === item.id ? 'bg-ink text-paper' : 'border border-line bg-card'}`}
              >
                {item.label}
              </button>
            ))}
          </div>
          <textarea
            value={text}
            onChange={(event) => setText(event.target.value)}
            rows={4}
            className="w-full rounded-3xl border border-line bg-card p-4 text-sm outline-none focus:border-ink"
            placeholder="Tài khoản của bạn bị khóa, bấm vào link… / 09xx… / số tài khoản…"
          />
          <div className="flex flex-wrap items-center gap-3">
            <Button variant="seal" disabled={busy || text.trim().length < 8} onClick={() => void run()}>
              {busy ? 'Đang kiểm tra…' : 'Kiểm tra'}
            </Button>
            <span className="text-xs text-ink-soft">Thử nhanh:</span>
            {samples.map((sample) => (
              <button
                key={sample.label}
                type="button"
                className="rounded-full border border-line bg-card px-3 py-1 text-xs hover:bg-paper-deep"
                onClick={() => {
                  setText(sample.text)
                  setKind('tin')
                  void run(sample.text)
                }}
              >
                {sample.label}
              </button>
            ))}
          </div>
          {error && <p className="text-sm text-danger">{error}</p>}
        </div>
        {result && (
          <div className="mx-auto mt-6 max-w-3xl text-left">
            <CheckResult result={result} hits={hits} busy={busy} />
          </div>
        )}
      </section>

      <section className="grid gap-3 md:grid-cols-3">
        <article className="dossier rounded-3xl border-seal/40 p-5">
          <h2 className="font-display text-2xl">Luyện tập chống lừa</h2>
          <p className="mt-2 text-sm leading-6 text-ink-soft">
            Nhắn tin với người lừa đảo giả theo kịch bản thật. Bạn có nhận ra trước khi mất tiền?
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            <Button asChild variant="seal">
              <Link to="/luyen-tap">Bắt đầu mô phỏng</Link>
            </Button>
            <Button asChild variant="ghost">
              <Link to="/luyen-tap/trac-nghiem">Trắc nghiệm 2 phút</Link>
            </Button>
          </div>
        </article>
        <article className="dossier rounded-3xl p-5">
          <h2 className="font-display text-2xl">Chiêu đang nổi</h2>
          <ul className="mt-3 space-y-2 text-sm">
            {rising.map((card) => (
              <li key={card.id}>
                <Link className="underline" to={`/canh-bao#${card.id}`}>
                  {card.title}
                </Link>
              </li>
            ))}
            {rising.length === 0 && <li className="text-ink-soft">Đang tải các chiêu nổi…</li>}
          </ul>
          <Link to="/canh-bao" className="mt-3 inline-block text-sm font-semibold text-seal">
            Xem tất cả cảnh báo
          </Link>
        </article>
        <article className="dossier rounded-3xl p-5">
          <h2 className="font-display text-2xl">Tôi vừa bị lừa</h2>
          <ol className="mt-3 list-decimal space-y-1 pl-5 text-sm leading-6">
            <li>Gọi ngân hàng khóa tài khoản hoặc ví.</li>
            <li>Lưu bằng chứng.</li>
            <li>Trình báo công an nơi gần nhất.</li>
          </ol>
          <Link to="/bi-lua" className="mt-3 inline-block text-sm font-semibold text-seal">
            Hướng dẫn chi tiết
          </Link>
        </article>
      </section>

      <section>
        <div className="flex items-baseline justify-between gap-3">
          <h2 className="font-display text-3xl">Cảnh báo mới nhất</h2>
          <Link to="/xu-huong" className="text-sm font-semibold text-seal">
            Xem xu hướng
          </Link>
        </div>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {latest.map((card) => (
            <Link key={card.id} to={`/canh-bao#${card.id}`} className="dossier rounded-3xl p-4 hover:border-ink">
              <p className="text-[11px] uppercase tracking-[0.14em] text-gold">{card.category_labels?.[0] || card.categories[0]}</p>
              <h3 className="mt-2 font-display text-xl leading-tight">{card.title}</h3>
              {card.rising && <p className="mt-2 text-xs font-semibold text-seal">Đang nổi</p>}
            </Link>
          ))}
        </div>
      </section>

      <section className="flex flex-col gap-4 rounded-3xl bg-ink px-5 py-5 text-paper md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="font-display text-2xl">Honeypot hoạt động thế nào?</h2>
          <p className="mt-1 text-sm leading-6 text-paper/80">
            AI đóng vai nạn nhân → bóc kịch bản → thư viện cảnh báo → luyện tập cho người dân.
          </p>
          <p className="mt-2 text-xs text-paper/60">
            {stats ? `${stats.published_scripts} kịch bản` : '— kịch bản'} · {stats ? `${stats.conversations} hội thoại` : '— hội thoại'} ·{' '}
            {warnings.length ? `${warnings.length} thẻ cảnh báo` : '— thẻ cảnh báo'}
          </p>
        </div>
        <Button asChild variant="ghost" className="bg-paper text-ink hover:bg-white">
          <Link to="/phan-tich/demo">Xem demo 3 phút cho giám khảo</Link>
        </Button>
      </section>
    </div>
  )
}
