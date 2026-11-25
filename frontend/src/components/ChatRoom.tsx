import * as Dialog from '@radix-ui/react-dialog'
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, panelFromMessage, type Conversation, type Message, type Panel, type Script } from '../lib/api'
import { sleep } from '../lib/utils'
import { CasePanel } from './CasePanel'
import { Button, Banner } from './ui'

function DemoCoach({ sent }: { sent: number }) {
  const beats = [
    [0, '0:00 — Họ vừa gọi. Bà Năm sẽ hỏi họ là ai. Bạn chỉ cần gửi câu gợi ý.'],
    [2, '0:40 — Họ đang cô lập nạn nhân. Đừng bấm trích xuất.'],
    [4, '1:20 — Số tài khoản và phần mềm xuất hiện ở buồng lái.'],
    [6, '2:00 — Nhánh con ở Đức, rồi chuyện sống một mình. Agent không khép.'],
    [8, '2:30 — Bấm Trích xuất. Hồ sơ vào hàng chờ, duyệt để thấy trên thư viện.'],
  ]
  const line = [...beats].reverse().find(([at]) => sent >= Number(at))?.[1] ?? beats[0][1]
  return <p className="border-b border-line bg-[#fde7ef] px-4 py-2 text-sm text-seal-deep">{line}</p>
}

type ExtractResult = { action: string; relation: string; script: Script }

export function ChatRoom({ id }: { id: string }) {
  const [conversation, setConversation] = useState<Conversation | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [panel, setPanel] = useState<Panel | null>(null)
  const [reasoning, setReasoning] = useState<unknown>(null)
  const [text, setText] = useState('')
  const [error, setError] = useState('')
  const [typing, setTyping] = useState(false)
  const [busy, setBusy] = useState(false)
  const [showReason, setShowReason] = useState(() => localStorage.getItem('gianan-reason') === '1')
  const [sheet, setSheet] = useState(false)
  const [extracted, setExtracted] = useState<ExtractResult | null>(null)
  const [playing, setPlaying] = useState(false)
  const scroller = useRef<HTMLDivElement>(null)
  const alive = useRef(true)

  useEffect(() => {
    alive.current = true
    api<Conversation>(`/api/conversations/${id}`)
      .then((data) => {
        setConversation(data)
        setMessages(data.messages)
        const last = [...data.messages].reverse().find((message) => message.role === 'victim')
        setPanel(panelFromMessage(last))
        setReasoning(last?.reasoning ?? null)
      })
      .catch((reason: Error) => setError(reason.message))
    return () => {
      alive.current = false
    }
  }, [id])

  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight })
  }, [messages, typing])

  function toggleReason() {
    const next = !showReason
    setShowReason(next)
    localStorage.setItem('gianan-reason', next ? '1' : '0')
  }

  async function send(raw: string) {
    const content = raw.trim()
    if (!content || busy || conversation?.status === 'ended') return
    setText('')
    setError('')
    setBusy(true)
    setTyping(true)
    const localId = `local-${Date.now()}`
    setMessages((current) => [
      ...current,
      { id: localId, role: 'scammer', content, reasoning: null, created_at: new Date().toISOString() },
    ])
    try {
      const started = Date.now()
      const result = await api<{
        typing_ms: number
        scammer_message: Message
        victim_message: Message
        panel: Panel
      }>(`/api/conversations/${id}/messages`, { method: 'POST', body: JSON.stringify({ text: content }) })
      if (!alive.current) return
      setMessages((current) => current.map((message) => (message.id === localId ? result.scammer_message : message)))
      const wait = Math.max(700, Math.min(result.typing_ms, 2200) - (Date.now() - started))
      await sleep(wait)
      if (!alive.current) return
      setMessages((current) => [...current, result.victim_message])
      setPanel(result.panel)
      setReasoning(result.victim_message.reasoning)
      setConversation((current) => (current ? { ...current, turn_index: current.turn_index + 1, status: 'active' } : current))
    } catch (reason) {
      setMessages((current) => current.filter((message) => message.id !== localId))
      setText(content)
      setError(reason instanceof Error ? reason.message : 'Không gửi được.')
    } finally {
      if (alive.current) {
        setTyping(false)
        setBusy(false)
      }
    }
  }

  async function playRest() {
    if (!conversation) return
    setPlaying(true)
    const sent = messages.filter((message) => message.role === 'scammer').length
    for (const line of conversation.demo_lines.slice(sent)) {
      if (!alive.current) return
      await send(line)
      await sleep(400)
    }
    setPlaying(false)
  }

  async function extract() {
    setBusy(true)
    setError('')
    try {
      const result = await api<ExtractResult>(`/api/conversations/${id}/extract`, { method: 'POST' })
      setExtracted(result)
      setConversation((current) => (current ? { ...current, status: 'ended', extracted_script_id: result.script.id } : current))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Không trích được.')
    } finally {
      setBusy(false)
    }
  }

  async function approve() {
    if (!extracted) return
    const script = await api<Script>(`/api/moderation/${extracted.script.id}/approve`, { method: 'POST' })
    setExtracted({ ...extracted, script })
  }

  if (!conversation && !error) return <p className="text-ink-soft">Đang mở hồ sơ…</p>
  if (!conversation) return <Banner tone="danger">{error}</Banner>

  const sentCount = messages.filter((message) => message.role === 'scammer').length
  const nextLine = conversation.demo_lines[sentCount]
  const profile = conversation.persona.fake_profile

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1.35fr)_minmax(280px,0.8fr)]">
      <section className="dossier flex min-h-[70vh] flex-col overflow-hidden rounded-3xl">
        <header className="flex flex-wrap items-start justify-between gap-3 border-b border-line px-4 py-4">
          <div>
            <p className="text-[11px] uppercase tracking-[0.16em] text-ink-soft">
              {conversation.channel_label}
              {conversation.channel !== 'web' ? ' · cùng agent, chưa nối vận chuyển pha 2' : ''}
              {conversation.is_demo ? ' · demo giám khảo' : ''}
            </p>
            <h1 className="font-display text-2xl">
              {conversation.persona.display_name}, {conversation.persona.age}
            </h1>
            <p className="text-sm text-ink-soft">
              {conversation.persona.label} · {conversation.persona.city}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="ghost" size="sm" onClick={toggleReason} type="button">
              {showReason ? 'Ẩn luận giải' : 'Luận giải của agent'}
            </Button>
            <Button variant="ghost" size="sm" className="lg:hidden" type="button" onClick={() => setSheet(true)}>
              Hồ sơ vụ
            </Button>
          </div>
        </header>
        {conversation.is_demo && <DemoCoach sent={sentCount} />}
        <div ref={scroller} className="thread flex-1 space-y-3 overflow-y-auto px-4 py-4">
          {messages.length === 0 && (
            <p className="rounded-2xl bg-paper-deep px-4 py-3 text-sm leading-6 text-ink-soft">
              Bạn đóng vai người đang lừa. Gõ câu đầu, hoặc dán tin nhắn họ đã gửi. {conversation.persona.display_name} sẽ
              trả lời trong vai và không chuyển tiền.
            </p>
          )}
          {messages.map((message) => (
            <div key={message.id} className={`bubble flex ${message.role === 'victim' ? 'justify-end' : 'justify-start'}`}>
              <div
                className={`max-w-[85%] px-3.5 py-2 text-sm leading-6 shadow-sm ${
                  message.role === 'victim'
                    ? 'rounded-2xl rounded-br-md bg-seal text-white'
                    : 'rounded-2xl rounded-bl-md bg-white text-ink'
                }`}
              >
                <p className={`mb-0.5 text-[10px] uppercase tracking-[0.14em] ${message.role === 'victim' ? 'text-white/75' : 'text-ink-soft'}`}>
                  {message.role === 'victim' ? conversation.persona.display_name : 'Đối phương'}
                </p>
                {message.content}
                <p className={`mt-1 text-right text-[10px] ${message.role === 'victim' ? 'text-white/70' : 'text-ink-soft'}`}>
                  {new Date(message.created_at).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })}
                </p>
              </div>
            </div>
          ))}
          {typing && (
            <div className="flex justify-end">
              <div className="typing rounded-3xl bg-ink px-4 py-3 text-paper">
                <span />
                <span />
                <span />
              </div>
            </div>
          )}
        </div>
        <div className="space-y-3 border-t border-line px-4 py-4">
          {error && <Banner tone="danger">{error}</Banner>}
          {extracted && (
            <div className="rounded-2xl bg-[#e7f3ec] px-4 py-3 text-sm leading-6">
              {extracted.action === 'merged' ? (
                <p>
                  Trùng kịch bản đã có. Đã cộng một lượt ghi nhận vào{' '}
                  <Link className="font-semibold underline" to={`/kich-ban/${extracted.script.id}`}>
                    {extracted.script.title}
                  </Link>
                  .
                </p>
              ) : (
                <p>
                  Đã đưa vào hàng chờ duyệt:{' '}
                  <Link className="font-semibold underline" to={`/kich-ban/${extracted.script.id}`}>
                    {extracted.script.title}
                  </Link>
                  . {extracted.script.status === 'published' ? 'Đã công bố.' : 'Chưa hiện ở thư viện công khai.'}
                </p>
              )}
              {extracted.script.status === 'pending' && (
                <Button className="mt-2" size="sm" variant="seal" type="button" onClick={() => void approve()}>
                  Duyệt ngay
                </Button>
              )}
            </div>
          )}
          {nextLine && conversation.status === 'active' && (
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                className="rounded-full border border-line bg-paper px-3 py-1.5 text-left text-sm hover:bg-paper-deep"
                onClick={() => void send(nextLine)}
                disabled={busy}
              >
                Gợi ý: {nextLine}
              </button>
              {conversation.demo_lines.length > 1 && (
                <Button size="sm" variant="ghost" type="button" disabled={busy || playing} onClick={() => void playRest()}>
                  Tự đi nốt các câu gợi ý
                </Button>
              )}
            </div>
          )}
          <form
            className="flex gap-2"
            onSubmit={(event) => {
              event.preventDefault()
              void send(text)
            }}
          >
            <textarea
              value={text}
              onChange={(event) => setText(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                  event.preventDefault()
                  void send(text)
                }
              }}
              rows={2}
              disabled={conversation.status !== 'active' || busy}
              placeholder={conversation.status === 'active' ? 'Nhập lời của kẻ lừa…' : 'Hội thoại đã kết thúc.'}
              className="min-h-12 flex-1 resize-none rounded-2xl border border-line bg-white px-3 py-2 text-sm outline-none focus:border-ink"
            />
            <div className="flex flex-col gap-2">
              <Button type="submit" variant="seal" disabled={busy || conversation.status !== 'active'}>
                Gửi
              </Button>
              <Button type="button" variant="ghost" size="sm" disabled={busy || messages.length === 0 || conversation.status !== 'active'} onClick={() => void extract()}>
                Trích xuất
              </Button>
            </div>
          </form>
          <details className="text-sm text-ink-soft">
            <summary className="cursor-pointer">Hồ sơ giả — chỉ để đóng vai, không phải dữ liệu của ai</summary>
            <dl className="mt-2 grid grid-cols-2 gap-2">
              {Object.entries({
                'Họ tên': profile.full_name,
                'Điện thoại': profile.phone,
                'Ngân hàng': `${profile.bank_name} ${profile.bank_account}`,
                MoMo: profile.momo,
                'Căn cước giả': profile.cccd,
                OTP: conversation.fake_otp,
              }).map(([key, value]) => (
                <div key={key}>
                  <dt className="text-[11px] uppercase tracking-[0.12em]">{key}</dt>
                  <dd className="text-ink">{value}</dd>
                </div>
              ))}
            </dl>
          </details>
        </div>
      </section>
      <div className="hidden lg:sticky lg:top-24 lg:block lg:max-h-[calc(100vh-7rem)] lg:self-start lg:overflow-y-auto">
        <CasePanel panel={panel} reasoning={showReason ? reasoning : undefined} />
      </div>
      <Dialog.Root open={sheet} onOpenChange={setSheet}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-40 bg-black/40" />
          <Dialog.Content className="fixed inset-x-0 bottom-0 z-50 max-h-[85vh] overflow-y-auto rounded-t-3xl bg-paper p-4">
            <Dialog.Title className="mb-3 font-display text-xl">Hồ sơ vụ</Dialog.Title>
            <CasePanel panel={panel} reasoning={showReason ? reasoning : undefined} />
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  )
}
