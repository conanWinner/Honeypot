import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Banner, Button } from '../components/ui'
import { api, type Persona } from '../lib/api'

type CheckResult = {
  risk: string
  risk_label: string
  is_scam?: boolean
  verdict?: 'benign' | 'scam' | 'unclear'
  confidence: number
  intent: string
  red_flags: string[]
  matched_script: { id: string; title: string; confidence: number } | null
  next_step: { intent: string; phrases: string[] } | null
  advice: string
}

const samples = [
  'Ví MoMo của bạn bị tạm khóa do đăng nhập lạ. Bấm link để xác thực và nhập mã OTP trong 15 phút.',
  'Tôi là thiếu tá cơ quan cảnh sát điều tra. Anh chuyển toàn bộ số dư sang tài khoản giám định, không được kể cho ai.',
  'Đơn hàng của bạn không phát được do sai địa chỉ. Bấm link thanh toán phí ship 25 nghìn.',
]

export function CheckPage() {
  const navigate = useNavigate()
  const [text, setText] = useState('')
  const [result, setResult] = useState<CheckResult | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function run(value = text) {
    setBusy(true)
    setError('')
    setResult(null)
    try {
      setResult(await api<CheckResult>('/api/check', { method: 'POST', body: JSON.stringify({ text: value }) }))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Không kiểm tra được.')
    } finally {
      setBusy(false)
    }
  }

  async function handoff() {
    setBusy(true)
    try {
      const personas = await api<Persona[]>('/api/personas')
      const persona = personas.find((item) => item.id === 'ba-nam') ?? personas[0]
      const created = await api<{ conversation: { id: string } }>('/api/check/handoff', {
        method: 'POST',
        body: JSON.stringify({ text, persona_id: persona.id, channel: 'web' }),
      })
      navigate(`/hoi-thoai/${created.conversation.id}`)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Không giao được cho agent.')
      setBusy(false)
    }
  }

  const tone = result?.risk === 'thap' ? 'ok' : result?.risk === 'trung_binh' ? 'warn' : 'danger'

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_0.9fr]">
      <section>
        <p className="text-[11px] uppercase tracking-[0.16em] text-seal">Kiểm tra tin</p>
        <h1 className="mt-2 font-display text-4xl">Dán tin đang nghi</h1>
        <p className="mt-2 text-sm leading-6 text-ink-soft">
          Một tin nhắn hoặc một đoạn hội thoại. Hệ thống chỉ mức rủi ro, kịch bản gần nhất, và bước đối phương hay làm tiếp.
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          {samples.map((sample) => (
            <button
              key={sample}
              type="button"
              className="rounded-full border border-line bg-card px-3 py-1.5 text-left text-xs hover:bg-paper-deep"
              onClick={() => {
                setText(sample)
                void run(sample)
              }}
            >
              {sample.slice(0, 72)}…
            </button>
          ))}
        </div>
        <textarea
          value={text}
          onChange={(event) => setText(event.target.value)}
          rows={8}
          className="mt-4 w-full rounded-3xl border border-line bg-card p-4 text-sm outline-none focus:border-ink"
          placeholder="Dán tin nhắn vào đây"
        />
        <Button className="mt-3" variant="seal" disabled={busy || text.trim().length < 8} onClick={() => void run()}>
          {busy ? 'Đang đọc…' : 'Đọc tin'}
        </Button>
        {error && (
          <div className="mt-4">
            <Banner tone="danger">{error}</Banner>
          </div>
        )}
      </section>
      <aside>
        {!result && <div className="dossier rounded-3xl p-5 text-sm text-ink-soft">Kết quả hiện ở đây: mức rủi ro, kịch bản khớp, bước kế, và lời khuyên.</div>}
        {result && (
          <div className="space-y-3">
            <Banner tone={tone}>
              Mức rủi ro: <b>{result.risk_label}</b>
              {result.verdict === 'benign' ? ' · không thấy dấu hiệu lừa đảo' : result.verdict === 'scam' ? ' · có dấu hiệu lừa đảo' : ''}
              {' '}· độ gần {Math.round(result.confidence * 100)}%
            </Banner>
            <section className="dossier rounded-3xl p-5">
              <p className="text-[11px] uppercase tracking-[0.14em] text-ink-soft">Ý định</p>
              <p className="mt-1 text-lg font-semibold">{result.intent}</p>
              {result.matched_script && (
                <p className="mt-3 text-sm">
                  Khớp{' '}
                  <a className="underline" href={`/kich-ban/${result.matched_script.id}`}>
                    {result.matched_script.title}
                  </a>
                </p>
              )}
              {result.next_step && (
                <p className="mt-3 text-sm leading-6">
                  <span className="font-semibold">Bước hay làm tiếp: </span>
                  {result.next_step.intent}
                </p>
              )}
              <ul className="mt-3 list-disc pl-4 text-sm leading-6">
                {result.red_flags.map((flag) => (
                  <li key={flag}>{flag}</li>
                ))}
              </ul>
              <p className="mt-3 text-sm leading-6">{result.advice}</p>
              <Button className="mt-4" variant="ink" disabled={busy} onClick={() => void handoff()}>
                Giao cho agent đóng nạn nhân
              </Button>
            </section>
          </div>
        )}
      </aside>
    </div>
  )
}
