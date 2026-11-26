import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { RichText } from '../components/training/RichText'
import { Banner, Button } from '../components/ui'
import { api, type QuizQuestion } from '../lib/api'

const channelLabel = (channel: string) =>
  ({
    phone: 'Điện thoại',
    zalo: 'Zalo',
    sms: 'SMS',
    facebook: 'Facebook',
    web: 'Web',
    telegram: 'Telegram',
  })[channel] ?? channel

export function QuizPage() {
  const [questions, setQuestions] = useState<QuizQuestion[]>([])
  const [index, setIndex] = useState(0)
  const [picked, setPicked] = useState<'scam' | 'safe' | null>(null)
  const [correct, setCorrect] = useState(0)
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
    return (
      <section className="mx-auto max-w-md space-y-4 text-center">
        <p className="text-[11px] uppercase tracking-[0.16em] text-seal">Kết quả</p>
        <h1 className="font-display text-5xl">
          {correct}/{questions.length}
        </h1>
        <p className="text-sm leading-6 text-ink-soft">
          {correct >= 6 ? 'Bạn đọc tin khá chắc.' : 'Nên luyện thêm một kịch bản hội thoại.'}
        </p>
        <Button asChild variant="seal">
          <Link to="/luyen-tap">Sang mô phỏng hội thoại</Link>
        </Button>
      </section>
    )
  }

  const question = questions[index]
  const right = picked !== null && picked === question.answer

  function choose(answer: 'scam' | 'safe') {
    if (picked) return
    setPicked(answer)
    if (answer === question.answer) setCorrect((value) => value + 1)
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
    <div className="mx-auto max-w-sm space-y-4">
      <p className="text-center text-sm text-ink-soft">
        {index + 1}/{questions.length}
      </p>
      <div className="rounded-[2rem] border border-ink bg-[#1c1915] p-3 shadow-lg">
        <div className="rounded-[1.4rem] bg-[#efe6da] p-4">
          <p className="text-[11px] uppercase tracking-[0.14em] text-ink-soft">{channelLabel(question.channel)}</p>
          <p className="mt-3 text-sm leading-6">
            <RichText text={question.text} />
          </p>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <Button variant="seal" disabled={picked !== null} onClick={() => choose('scam')}>
          Lừa đảo
        </Button>
        <Button variant="ink" disabled={picked !== null} onClick={() => choose('safe')}>
          An toàn
        </Button>
      </div>
      {picked && (
        <div className={`rounded-3xl px-4 py-3 text-sm leading-6 ${right ? 'bg-[#e7f3ec] text-pine' : 'bg-[#fde7ef] text-danger'}`}>
          <p className="font-semibold">{right ? 'Đúng.' : 'Chưa đúng.'}</p>
          <p className="mt-1">{question.explain}</p>
          <Button className="mt-3" variant="ghost" onClick={next}>
            {index + 1 >= questions.length ? 'Xem điểm' : 'Câu tiếp'}
          </Button>
        </div>
      )}
    </div>
  )
}
