import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { CheckResult } from '../components/CheckResult'
import { Banner, Button } from '../components/ui'
import { api, type CheckResult as CheckResultData, type Persona } from '../lib/api'

const samples = [
  'Ví MoMo của bạn bị tạm khóa do đăng nhập lạ. Bấm link để xác thực và nhập mã OTP trong 15 phút.',
  'Tôi là thiếu tá cơ quan cảnh sát điều tra. Anh chuyển toàn bộ số dư sang tài khoản giám định, không được kể cho ai.',
  'Đơn hàng của bạn không phát được do sai địa chỉ. Bấm link thanh toán phí ship 25 nghìn.',
  'Cán bộ phường báo hồ sơ cư trú sai. Bác tải DichVuCong.apk ở dichvucong-gov.top/app rồi bật quyền Hỗ trợ truy cập.',
  'Vietcombank: ma OTP 482193 cua quy khach. Khong chia se ma nay voi bat ky ai.',
]

export function CheckPage() {
  const navigate = useNavigate()
  const [text, setText] = useState('')
  const [result, setResult] = useState<CheckResultData | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function run(value = text) {
    setBusy(true)
    setError('')
    setResult(null)
    try {
      setResult(await api<CheckResultData>('/api/check', { method: 'POST', body: JSON.stringify({ text: value }) }))
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
      navigate(`/phan-tich/hoi-thoai/${created.conversation.id}`)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Không giao được cho Honeypot.')
      setBusy(false)
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_0.9fr]">
      <section>
        <p className="text-[11px] uppercase tracking-[0.16em] text-seal">Báo cáo</p>
        <h1 className="mt-2 font-display text-4xl">Báo cáo lừa đảo</h1>
        <p className="mt-2 text-sm leading-6 text-ink-soft">
          Dán tin nhắn, số, hoặc đường dẫn. Honeypot đối chiếu kho kịch bản. Nếu muốn, giao cuộc thoại cho Honeypot đóng vai nạn nhân.
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
          {busy ? 'Đang đọc…' : 'Kiểm tra'}
        </Button>
        {error && (
          <div className="mt-4">
            <Banner tone="danger">{error}</Banner>
          </div>
        )}
      </section>
      <aside>
        {!result && <div className="dossier rounded-3xl p-5 text-sm text-ink-soft">Kết quả hiện ở đây: mức rủi ro, kịch bản khớp, cờ đỏ, và việc nên làm.</div>}
        {result && <CheckResult result={result} busy={busy} onHandoff={() => void handoff()} />}
      </aside>
    </div>
  )
}
