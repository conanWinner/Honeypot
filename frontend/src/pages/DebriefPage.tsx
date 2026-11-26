import { toPng } from 'html-to-image'
import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { RichText } from '../components/training/RichText'
import { Banner, Button } from '../components/ui'
import { api, type TrainingDebrief, type TrainingSession } from '../lib/api'

const leakLabel: Record<string, string> = {
  otp: 'mã OTP',
  account: 'số tài khoản',
  cccd: 'số căn cước',
  password: 'mật khẩu',
  name: 'họ tên',
  address: 'địa chỉ',
}

function sentence(report: TrainingDebrief): string {
  const before = report.stopped_before ? `, trước bước «${report.stopped_before}»` : ''
  if (report.status === 'safe' && report.end_reason === 'hang_up') {
    return `Bạn đã gác máy ở lượt ${report.turns}${before}.`
  }
  if (report.status === 'safe' && report.end_reason === 'verify_official') {
    return `Bạn đã gọi lại số chính thức ở lượt ${report.turns}${before}.`
  }
  if (report.status === 'safe' && report.end_reason === 'report') {
    return `Bạn đã báo lừa đảo ở lượt ${report.turns}${before}.`
  }
  if (report.status === 'safe') {
    return `Bạn đã dừng an toàn ở lượt ${report.turns}${before}.`
  }
  if (report.end_reason === 'otp') return `Bạn đã đọc mã OTP ở lượt ${report.turns}.`
  if (report.end_reason === 'transfer') return `Bạn đã chuyển tiền ở lượt ${report.turns}.`
  if (report.end_reason === 'install') return `Bạn đã cài ứng dụng ở lượt ${report.turns}.`
  if (report.end_reason === 'credentials') return `Bạn đã đưa mật khẩu ở lượt ${report.turns}.`
  if (report.status === 'timeout') return 'Hết lượt trước khi bạn chặn cuộc gọi.'
  return `Phiên kết thúc ở lượt ${report.turns}.`
}

const tone: Record<string, string> = {
  caught: 'border-[#b7d7c4] bg-[#e7f3ec]',
  missed: 'border-[#f0c2c2] bg-[#fde7ef]',
  fell: 'border-[#f0c2c2] bg-[#fde7ef]',
  not_reached: 'border-line bg-card text-ink-soft',
}

export function DebriefPage() {
  const { sessionId } = useParams()
  const navigate = useNavigate()
  const cardRef = useRef<HTMLDivElement>(null)
  const [report, setReport] = useState<TrainingDebrief | null>(null)
  const [session, setSession] = useState<TrainingSession | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!sessionId) return
    Promise.all([
      api<TrainingDebrief>(`/api/training/sessions/${sessionId}/debrief`),
      api<TrainingSession>(`/api/training/sessions/${sessionId}`),
    ])
      .then(([debrief, current]) => {
        setReport(debrief)
        setSession(current)
      })
      .catch((reason: Error) => setError(reason.message))
  }, [sessionId])

  async function share() {
    if (!cardRef.current) return
    const url = await toPng(cardRef.current, { pixelRatio: 2, backgroundColor: '#1c1915' })
    const link = document.createElement('a')
    link.href = url
    link.download = 'honeypot-luyen-tap.png'
    link.click()
  }

  async function replay(harder: boolean) {
    if (!session) return
    const ladder = ['de', 'vua', 'kho'] as const
    const index = ladder.indexOf(session.difficulty)
    const difficulty = harder ? ladder[Math.min(index + 1, ladder.length - 1)] : session.difficulty
    setBusy(true)
    try {
      const created = await api<{ id: string }>('/api/training/sessions', {
        method: 'POST',
        body: JSON.stringify({ script_id: session.scenario.script_id, difficulty, mode: session.mode }),
      })
      navigate(`/luyen-tap/${created.id}`)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Không chơi lại được.')
      setBusy(false)
    }
  }

  if (error && !report) return <Banner tone="danger">{error}</Banner>
  if (!report || !session) return <p className="text-ink-soft">Đang tổng kết…</p>

  const caught = report.flags.filter((flag) => flag.caught).length
  const minutes = Math.max(1, Math.round(report.duration_s / 60))

  return (
    <div className="space-y-5">
      <section className="dossier rounded-3xl p-6 text-center">
        <p className="font-display text-7xl">{report.score}</p>
        <p className="mt-1 text-lg font-semibold">{report.label}</p>
        <p className="mt-2 text-sm leading-6 text-ink-soft">{sentence(report)}</p>
        <dl className="mt-4 grid grid-cols-2 gap-3 text-sm md:grid-cols-4">
          <div>
            <dt className="text-ink-soft">Cờ đỏ nhận ra</dt>
            <dd className="font-display text-2xl">
              {caught}/{report.flags.length}
            </dd>
          </div>
          <div>
            <dt className="text-ink-soft">Thông tin bị lộ</dt>
            <dd className="font-display text-2xl">{report.leaked.length}</dd>
          </div>
          <div>
            <dt className="text-ink-soft">Thời gian</dt>
            <dd className="font-display text-2xl">{minutes} phút</dd>
          </div>
          <div>
            <dt className="text-ink-soft">Gợi ý</dt>
            <dd className="font-display text-2xl">{report.hints_used}</dd>
          </div>
        </dl>
        {report.leaked.length > 0 && (
          <p className="mt-3 text-sm text-danger">Đã lộ: {report.leaked.map((kind) => leakLabel[kind] || kind).join(', ')}.</p>
        )}
      </section>

      <section>
        <h2 className="font-display text-2xl">Các bước</h2>
        <div className="mt-3 grid gap-3 md:grid-cols-2">
          {report.stages.map((stage) => (
            <article key={stage.index} className={`rounded-3xl border p-4 ${tone[stage.outcome] || tone.not_reached}`}>
              <p className="text-[11px] uppercase tracking-[0.14em]">
                {stage.outcome === 'caught' ? 'Nhận ra' : stage.outcome === 'fell' ? 'Sập bẫy' : stage.outcome === 'missed' ? 'Bỏ qua' : 'Chưa tới'}
              </p>
              <p className="mt-1 font-semibold">{stage.intent}</p>
              {stage.user_quote && <p className="mt-2 text-sm leading-6">«{stage.user_quote}»</p>}
            </article>
          ))}
        </div>
      </section>

      <section className="dossier rounded-3xl p-5">
        <h2 className="font-display text-2xl">Cờ đỏ trong cuộc trò chuyện</h2>
        <ul className="mt-3 space-y-3">
          {report.flags.map((flag, index) => {
            const previous = report.flags[index - 1]
            const showQuote = Boolean(flag.quote) && (!previous || previous.quote !== flag.quote || previous.stage_index !== flag.stage_index)
            return (
              <li key={`${flag.stage_index}-${flag.text}`} className="text-sm leading-6">
                {showQuote && (
                  <p className="text-ink-soft">
                    “<RichText text={flag.quote} />”
                  </p>
                )}
                <p>
                  {flag.text} · <b>{flag.caught ? 'đã nhận ra' : 'chưa nhận ra'}</b>
                </p>
              </li>
            )
          })}
          {report.flags.length === 0 && <li className="text-sm text-ink-soft">Chưa kịp chạm bước có cờ đỏ.</li>}
        </ul>
      </section>

      <section className="dossier rounded-3xl p-5">
        <h2 className="font-display text-2xl">3 điều cần nhớ</h2>
        <ol className="mt-3 list-decimal space-y-2 pl-5 text-sm leading-6">
          {report.tips.map((tip) => (
            <li key={tip}>{tip}</li>
          ))}
        </ol>
      </section>

      <section className="dossier rounded-3xl p-5">
        <h2 className="font-display text-2xl">Kịch bản này có thật</h2>
        <p className="mt-2 text-sm leading-6">
          {report.script.title} đã được ghi nhận {report.script.occurrence_count} lần
          {report.script.last_seen ? `, gần nhất ${report.script.last_seen.slice(0, 10)}` : ''}.
        </p>
        <div className="mt-3 flex flex-wrap gap-2 text-sm">
          <Link className="underline" to={`/canh-bao/kich-ban/${report.script.id}`}>
            Mở hồ sơ kịch bản
          </Link>
          {report.warning_card_ids.map((id) => (
            <Link key={id} className="underline" to={`/canh-bao#${id}`}>
              Thẻ cảnh báo
            </Link>
          ))}
        </div>
      </section>

      <div ref={cardRef} className="rounded-3xl bg-ink p-6 text-paper">
        <p className="text-xs uppercase tracking-[0.16em] text-paper/70">Honeypot · Luyện tập</p>
        <p className="mt-2 font-display text-6xl">{report.score}</p>
        <p className="text-lg">{report.label}</p>
        <p className="mt-2 text-sm text-paper/80">{report.script.title}</p>
      </div>

      <div className="flex flex-wrap gap-2">
        <Button asChild variant="ghost">
          <Link to="/luyen-tap">Thử kịch bản khác</Link>
        </Button>
        <Button variant="ink" disabled={busy} onClick={() => void replay(true)}>
          Chơi lại khó hơn
        </Button>
        <Button variant="seal" onClick={() => void share()}>
          Chia sẻ thẻ kết quả
        </Button>
      </div>
      {error && <p className="text-sm text-danger">{error}</p>}
    </div>
  )
}
