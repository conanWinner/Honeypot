import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { RichText } from '../components/training/RichText'
import { practiceWarning } from '../lib/mask'
import { Banner, Button } from '../components/ui'
import { api, ApiError, type TrainingSession } from '../lib/api'

const safeActions = [
  { id: 'hang_up', label: 'Gác máy / chặn' },
  { id: 'verify_official', label: 'Gọi lại số chính thức' },
  { id: 'report', label: 'Báo cáo lừa đảo' },
] as const

const fallActions = [
  { id: 'transfer', label: 'Chuyển tiền (giả)' },
  { id: 'share_otp', label: 'Đọc OTP (giả)' },
] as const

const difficultyLabel = { de: 'Dễ', vua: 'Vừa', kho: 'Khó' }

export function SimulationPage() {
  const { sessionId } = useParams()
  const navigate = useNavigate()
  const [session, setSession] = useState<TrainingSession | null>(null)
  const [draft, setDraft] = useState('')
  const [hint, setHint] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [pending, setPending] = useState<(typeof fallActions)[number] | null>(null)
  const thread = useRef<HTMLDivElement>(null)
  const sending = useRef(false)

  useEffect(() => {
    if (!sessionId) return
    api<TrainingSession>(`/api/training/sessions/${sessionId}`)
      .then((data) => {
        if (data.status !== 'active') {
          navigate(`/luyen-tap/${sessionId}/ket-qua`, { replace: true })
          return
        }
        setSession(data)
      })
      .catch((reason: Error) => setError(reason.message))
  }, [sessionId, navigate])

  useEffect(() => {
    thread.current?.scrollTo({ top: thread.current.scrollHeight })
  }, [session?.messages.length, busy])

  function leave(next: TrainingSession) {
    setSession(next)
    if (next.status !== 'active' && sessionId) {
      navigate(`/luyen-tap/${sessionId}/ket-qua`)
    }
  }

  async function send() {
    if (!sessionId || !draft.trim() || sending.current) return
    sending.current = true
    const original = draft.trim()
    setBusy(true)
    setError('')
    try {
      const payload = await api<{ session: TrainingSession }>('/api/training/sessions/' + sessionId + '/messages', {
        method: 'POST',
        body: JSON.stringify({ text: original }),
      })
      setDraft('')
      leave(payload.session)
    } catch (reason) {
      if (reason instanceof ApiError && reason.status === 409) {
        navigate(`/luyen-tap/${sessionId}/ket-qua`)
        return
      }
      setError(reason instanceof Error ? reason.message : 'Không gửi được.')
    } finally {
      sending.current = false
      setBusy(false)
    }
  }

  async function act(action: string) {
    if (!sessionId) return
    setPending(null)
    setBusy(true)
    setError('')
    try {
      const next = await api<TrainingSession>(`/api/training/sessions/${sessionId}/action`, {
        method: 'POST',
        body: JSON.stringify({ action }),
      })
      leave(next)
    } catch (reason) {
      if (reason instanceof ApiError && reason.status === 409 && sessionId) {
        navigate(`/luyen-tap/${sessionId}/ket-qua`)
        return
      }
      setError(reason instanceof Error ? reason.message : 'Không thực hiện được.')
      setBusy(false)
    }
  }

  async function askHint() {
    if (!sessionId) return
    setBusy(true)
    try {
      const payload = await api<{ hint: string }>(`/api/training/sessions/${sessionId}/hint`, { method: 'POST' })
      setHint(payload.hint)
      setSession((current) => (current ? { ...current, hints_used: current.hints_used + 1 } : current))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Chưa có gợi ý.')
    } finally {
      setBusy(false)
    }
  }

  if (error && !session) return <Banner tone="danger">{error}</Banner>
  if (!session) return <p className="text-ink-soft">Đang mở bài luyện…</p>

  const flags = session.visible_flags

  return (
    <div className="space-y-3">
      <div className="sticky top-16 z-20 rounded-2xl border border-gold/40 bg-[#f8e7c8] px-4 py-2 text-sm leading-6 text-[#6d4708]">
        Đây là mô phỏng. Mọi số điện thoại, tài khoản, đường link đều là giả. Không nhập mã OTP hay mật khẩu thật.
      </div>
      <section className="dossier rounded-3xl p-4">
        <p className="text-[11px] uppercase tracking-[0.14em] text-seal">Tình huống này</p>
        <div className="mt-2 grid gap-3 text-sm sm:grid-cols-2">
          <p>
            <span className="text-ink-soft">Ai đang liên hệ: </span>
            {session.scenario.context?.who || session.scenario.scammer_name}
          </p>
          <p>
            <span className="text-ink-soft">Kênh: </span>
            {session.scenario.context?.channel || session.scenario.channel_label}
          </p>
          <p>
            <span className="text-ink-soft">Bạn đang đóng vai: </span>
            {session.scenario.context?.role}
          </p>
          <p>
            <span className="text-ink-soft">Mục tiêu: </span>
            {session.scenario.context?.goal}
          </p>
        </div>
      </section>
      <div className="grid gap-4 lg:grid-cols-[1.3fr_0.7fr]">
        <section className="dossier flex h-[calc(100dvh-12rem)] min-h-[22rem] flex-col overflow-hidden rounded-3xl md:h-auto md:min-h-[70vh]">
          <header className="border-b border-line px-4 py-3">
            <p className="font-semibold">{session.scenario.scammer_name}</p>
            <p className="text-xs text-ink-soft">
              {session.scenario.channel_label} · {session.scenario.category_label} · {difficultyLabel[session.difficulty]} · Lượt{' '}
              {session.turn_index}/{session.max_turns}
            </p>
          </header>
          <div ref={thread} className="thread flex-1 space-y-3 overflow-y-auto px-4 py-4">
            {session.messages.map((message) => (
              <div key={message.id} className={message.role === 'user' ? 'flex justify-end' : 'flex justify-start'}>
                <div
                  className={
                    message.role === 'user'
                      ? 'bubble max-w-[85%] rounded-3xl bg-ink px-4 py-3 text-sm leading-6 text-paper'
                      : 'bubble max-w-[85%] rounded-3xl border border-ink/15 bg-card px-4 py-3 text-sm leading-6 shadow-sm'
                  }
                >
                  <RichText text={message.text} onDark={message.role === 'user'} />
                </div>
              </div>
            ))}
            {busy && (
              <div className="flex justify-start">
                <div className="typing rounded-3xl bg-card px-4 py-3 text-ink-soft" aria-label="Đang nhập">
                  <span />
                  <span />
                  <span />
                </div>
              </div>
            )}
          </div>
          <div className="space-y-3 border-t border-line px-4 py-3">
            {practiceWarning(draft) && (
              <p className="text-xs text-seal">Đừng bao giờ gửi mã OTP thật. Số này sẽ được che trước khi lưu.</p>
            )}
            {error && <p className="text-sm text-danger">{error}</p>}
            <div className="flex gap-2">
              <input
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') void send()
                }}
                maxLength={500}
                placeholder="Nhắn lại…"
                className="h-11 flex-1 rounded-full border border-line bg-card px-4 text-sm outline-none focus:border-ink"
              />
              <Button variant="seal" disabled={busy || draft.trim().length < 1} onClick={() => void send()}>
                Gửi
              </Button>
            </div>
            <div className="flex flex-wrap gap-2">
              {safeActions.map((action) => (
                <button
                  key={action.id}
                  type="button"
                  disabled={busy}
                  onClick={() => void act(action.id)}
                  className="rounded-full border border-line bg-card px-3 py-1.5 text-xs font-semibold"
                >
                  {action.label}
                </button>
              ))}
              {fallActions.map((action) => (
                <button
                  key={action.id}
                  type="button"
                  disabled={busy}
                  onClick={() => setPending(action)}
                  className="rounded-full border border-danger/30 bg-[#fde7ef] px-3 py-1.5 text-xs font-semibold text-danger"
                >
                  {action.label}
                </button>
              ))}
            </div>
          </div>
        </section>
        <aside className="space-y-3">
          <section className="dossier rounded-3xl p-4">
            <h2 className="font-semibold">Mục tiêu</h2>
            <p className="mt-1 text-sm leading-6 text-ink-soft">
              Nhận ra chiêu trước khi chuyển tiền, đọc mã, hoặc cài ứng dụng. Chặn hoặc gọi lại số bạn tự tra.
            </p>
          </section>
          <section className="dossier rounded-3xl p-4">
            <h2 className="font-semibold">Tiến trình kịch bản</h2>
            <ol className="mt-2 space-y-1 text-sm">
              {session.stages.map((stage) => {
                const current = stage.index === session.stage_index
                return (
                  <li key={stage.index} className={stage.reached ? 'text-ink' : 'text-ink-soft/50'}>
                    {current ? '▶' : stage.reached ? '✔' : '·'} {stage.intent || '…'}
                  </li>
                )
              })}
            </ol>
          </section>
          <section className="dossier rounded-3xl p-4">
            <h2 className="font-semibold">Cờ đỏ</h2>
            {flags.mode === 'hoc' ? (
              <ul className="mt-2 space-y-2 text-sm leading-6">
                {flags.items.length === 0 && <li className="text-ink-soft">Cờ đỏ sẽ hiện khi bước đó xuất hiện.</li>}
                {flags.items.map((item) => (
                  <li key={`${item.stage_index}-${item.id}`}>{item.text}</li>
                ))}
              </ul>
            ) : (
              <p className="mt-2 text-sm text-ink-soft">{'🚩 ? '.repeat(Math.max(flags.count, 1)).trim()} · đang che {flags.count} cờ</p>
            )}
            <Button className="mt-3" variant="ghost" disabled={busy} onClick={() => void askHint()}>
              Gợi ý (−5 điểm)
            </Button>
            {hint && <p className="mt-2 text-sm leading-6">{hint}</p>}
          </section>
        </aside>
      </div>
      {pending && (
        <div className="fixed inset-0 z-40 flex items-end justify-center bg-ink/40 p-4 sm:items-center">
          <div className="w-full max-w-sm rounded-3xl bg-card p-5">
            <p className="text-sm leading-6">Trong đời thật bạn sẽ mất tiền. Vẫn chọn?</p>
            <div className="mt-4 flex gap-2">
              <Button variant="seal" onClick={() => void act(pending.id)}>
                Vẫn chọn
              </Button>
              <Button variant="ghost" onClick={() => setPending(null)}>
                Quay lại
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
