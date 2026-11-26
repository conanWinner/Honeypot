import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Banner, Button } from '../components/ui'
import { api, type QuizQuestion } from '../lib/api'

const channelLabel = (channel: string) =>
  ({
    phone: 'Cuộc gọi đến',
    zalo: 'Zalo',
    sms: 'SMS',
    facebook: 'Facebook',
    email: 'Thư',
    web: 'Web',
    telegram: 'Telegram',
  })[channel] ?? channel

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function Highlighted({ text, phrases, on }: { text: string; phrases: string[]; on: boolean }) {
  if (!on || phrases.length === 0) return <>{text}</>
  const pattern = new RegExp(`(${phrases.map(escapeRegExp).join('|')})`, 'g')
  const parts = text.split(pattern)
  return (
    <>
      {parts.map((part, index) =>
        phrases.includes(part) ? (
          <mark key={`${part}-${index}`} className="rounded bg-[#f6d7a2] px-0.5 text-ink">
            {part}
          </mark>
        ) : (
          <span key={`${index}-t`}>{part}</span>
        ),
      )}
    </>
  )
}

function Artifact({ question, revealed }: { question: QuizQuestion; revealed: boolean }) {
  const lines = question.lines?.length ? question.lines : [question.text]
  const phrases = question.highlights ?? []
  const frame =
    question.channel === 'zalo'
      ? 'bg-[#e7f3ec]'
      : question.channel === 'email'
        ? 'bg-card'
        : question.channel === 'facebook'
          ? 'bg-[#eef3fb]'
          : 'bg-[#efe6da]'
  return (
    <article className="rounded-[1.6rem] border border-ink bg-[#1c1915] p-3 shadow-lg">
      <div className={`rounded-[1.2rem] p-4 ${frame}`}>
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-[11px] uppercase tracking-[0.14em] text-ink-soft">{channelLabel(question.channel)}</p>
            <p className="mt-1 font-semibold">{question.sender}</p>
            <p className="text-xs text-ink-soft">{question.sender_detail}</p>
          </div>
          <p className="text-xs text-ink-soft">{question.time}</p>
        </div>
        <div className="mt-4 space-y-2 text-sm leading-6">
          {lines.map((line) => (
            <p key={line}>
              <Highlighted text={line} phrases={phrases} on={revealed} />
            </p>
          ))}
        </div>
      </div>
    </article>
  )
}

export function QuizPage() {
  const [questions, setQuestions] = useState<QuizQuestion[]>([])
  const [index, setIndex] = useState(0)
  const [picked, setPicked] = useState<'scam' | 'safe' | null>(null)
  const [correct, setCorrect] = useState(0)
  const [missed, setMissed] = useState<QuizQuestion[]>([])
  const [done, setDone] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    api<{ questions: QuizQuestion[] }>('/api/training/quiz?n=8')
      .then((data) => setQuestions(data.questions))
      .catch((reason: Error) => setError(reason.message))
  }, [])

  if (error) return <Banner tone="danger">{error}</Banner>
  if (questions.length === 0) return <p className="text-ink-soft">Đang soạn câu hỏi…</p>

  if (done) {
    const practice = missed.filter((item) => item.script_id)
    return (
      <div className="space-y-5">
        <div>
          <p className="text-[11px] uppercase tracking-[0.16em] text-seal">Kết quả vòng này</p>
          <h1 className="mt-2 font-display text-5xl">
            {correct}/{questions.length}
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-ink-soft">
            {correct >= 6
              ? 'Bạn nhận ra phần lớn tin. Xem lại các câu chưa đúng trước khi luyện hội thoại.'
              : 'Một số chiêu vẫn lọt. Đọc cờ đỏ bên dưới, rồi luyện đúng kịch bản đó.'}
          </p>
        </div>
        <section className="dossier rounded-3xl p-5">
          <h2 className="font-display text-2xl">Dấu hiệu còn bỏ lỡ</h2>
          {missed.length === 0 ? (
            <p className="mt-2 text-sm leading-6">Không bỏ lỡ câu nào trong vòng này.</p>
          ) : (
            <ul className="mt-3 space-y-4">
              {missed.map((item) => (
                <li key={item.id}>
                  <p className="font-semibold">{item.sender}</p>
                  <ol className="mt-1 list-decimal space-y-1 pl-5 text-sm leading-6">
                    {(item.flags ?? []).map((flag) => (
                      <li key={flag}>{flag}</li>
                    ))}
                  </ol>
                </li>
              ))}
            </ul>
          )}
        </section>
        {practice.length > 0 && (
          <section className="dossier rounded-3xl p-5">
            <h2 className="font-display text-2xl">Nên luyện tiếp</h2>
            <ul className="mt-3 space-y-2 text-sm">
              {practice.map((item) => (
                <li key={item.id}>
                  <Link className="font-semibold underline" to={`/luyen-tap?script=${item.script_id}`}>
                    Luyện tình huống: {item.sender}
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        )}
        <Button asChild variant="seal">
          <Link to="/luyen-tap">Sang mô phỏng hội thoại</Link>
        </Button>
      </div>
    )
  }

  const question = questions[index]
  const right = picked !== null && picked === question.answer
  const progress = ((index + (picked ? 1 : 0)) / questions.length) * 100

  function choose(answer: 'scam' | 'safe') {
    if (picked) return
    setPicked(answer)
    if (answer === question.answer) setCorrect((value) => value + 1)
    else setMissed((items) => [...items, question])
  }

  function next() {
    if (index + 1 >= questions.length) {
      setDone(true)
      return
    }
    setIndex((value) => value + 1)
    setPicked(null)
  }

  return (
    <div className="space-y-4">
      <div>
        <div className="flex items-baseline justify-between gap-3">
          <h1 className="font-display text-3xl">Trắc nghiệm tình huống</h1>
          <p className="text-sm text-ink-soft">
            {index + 1}/{questions.length} · đúng {correct}
          </p>
        </div>
        <div className="meter mt-3">
          <span className="block h-full rounded-full bg-seal" style={{ width: `${progress}%` }} />
        </div>
        <p className="mt-3 text-sm leading-6 text-ink-soft">{question.context}</p>
      </div>
      <div className="grid items-start gap-4 lg:grid-cols-2">
        <Artifact question={question} revealed={picked !== null} />
        <aside className="space-y-3">
          <div className="grid grid-cols-2 gap-2">
            <Button variant="seal" disabled={picked !== null} onClick={() => choose('scam')}>
              Lừa đảo
            </Button>
            <Button variant="ink" disabled={picked !== null} onClick={() => choose('safe')}>
              An toàn
            </Button>
          </div>
          {picked && (
            <section className={`rounded-3xl px-4 py-4 text-sm leading-6 ${right ? 'bg-[#e7f3ec] text-pine' : 'bg-[#fde7ef] text-danger'}`}>
              <p className="font-semibold">{right ? 'Đúng.' : 'Chưa đúng.'}</p>
              <ol className="mt-3 list-decimal space-y-1 pl-5 text-ink">
                {(question.flags ?? []).map((flag) => (
                  <li key={flag}>{flag}</li>
                ))}
              </ol>
              <p className="mt-3 text-ink">{question.explain}</p>
              {question.action && (
                <p className="mt-3 rounded-2xl bg-card px-3 py-2 text-ink">
                  <span className="font-semibold">Nên làm gì: </span>
                  {question.action}
                </p>
              )}
              <div className="mt-3 flex flex-wrap gap-3">
                {question.warning_id && (
                  <Link className="font-semibold underline" to={`/canh-bao#${question.warning_id}`}>
                    Xem thẻ cảnh báo
                  </Link>
                )}
                {question.script_id && (
                  <Link className="font-semibold underline" to={`/luyen-tap?script=${question.script_id}`}>
                    Luyện tình huống này
                  </Link>
                )}
              </div>
              <Button className="mt-4" variant="ghost" onClick={next}>
                {index + 1 >= questions.length ? 'Xem điểm' : 'Câu tiếp'}
              </Button>
            </section>
          )}
        </aside>
      </div>
    </div>
  )
}
