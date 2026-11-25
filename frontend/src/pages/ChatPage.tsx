import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ChatRoom } from '../components/ChatRoom'
import { Banner, Button } from '../components/ui'
import { api, type Persona } from '../lib/api'

type Recent = {
  id: string
  status: string
  channel_label: string
  is_demo: boolean
  persona_label: string
  persona_name: string
  turn_index: number
}

const channels = [
  { id: 'web', label: 'Web', note: 'Kênh đang chạy.' },
  { id: 'telegram', label: 'Telegram', note: 'Cùng agent. Telethon chưa nối.' },
  { id: 'voice', label: 'Thoại', note: 'Nhận lời thoại đã chép. Chưa nhận cuộc gọi.' },
]

export function ChatPage() {
  const { id } = useParams()
  if (id) return <ChatRoom id={id} />
  return <NewChat />
}

function NewChat() {
  const navigate = useNavigate()
  const [personas, setPersonas] = useState<Persona[]>([])
  const [personaId, setPersonaId] = useState('')
  const [channel, setChannel] = useState('web')
  const [recent, setRecent] = useState<Recent[]>([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api<Persona[]>('/api/personas')
      .then((rows) => {
        setPersonas(rows)
        setPersonaId(rows[0]?.id ?? '')
      })
      .catch((reason: Error) => setError(reason.message))
    api<Recent[]>('/api/conversations').then(setRecent).catch(() => setRecent([]))
  }, [])

  async function start() {
    setBusy(true)
    setError('')
    try {
      const created = await api<{ id: string }>('/api/conversations', {
        method: 'POST',
        body: JSON.stringify({ persona_id: personaId, channel }),
      })
      navigate(`/hoi-thoai/${created.id}`)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Không tạo được hội thoại.')
      setBusy(false)
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
      <section>
        <p className="text-[11px] uppercase tracking-[0.16em] text-seal">Tiếp quản hội thoại</p>
        <h1 className="mt-2 font-display text-4xl">Chọn người sẽ đóng nạn nhân</h1>
        <p className="mt-2 max-w-xl text-sm leading-6 text-ink-soft">
          Mỗi người có tên, tuổi, hoàn cảnh và số tài khoản giả. Agent chỉ được lộ những gì nằm trong hồ sơ này.
        </p>
        {error && (
          <div className="mt-4">
            <Banner tone="danger">{error}</Banner>
          </div>
        )}
        <div className="mt-5 grid gap-3 sm:grid-cols-2">
          {personas.map((persona) => (
            <button
              key={persona.id}
              type="button"
              onClick={() => setPersonaId(persona.id)}
              className={`dossier rounded-3xl p-4 text-left ${personaId === persona.id ? 'ring-2 ring-seal' : ''}`}
            >
              <p className="text-[11px] uppercase tracking-[0.14em] text-gold">{persona.label}</p>
              <p className="mt-1 font-semibold">
                {persona.display_name}, {persona.age}
              </p>
              <p className="text-sm text-ink-soft">
                {persona.job} · {persona.city}
              </p>
            </button>
          ))}
          {personas.length === 0 && !error && <p className="text-sm text-ink-soft">Đang tải hồ sơ…</p>}
        </div>
        <div className="mt-5 flex flex-wrap gap-2">
          {channels.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => setChannel(item.id)}
              className={`rounded-full border px-3 py-1.5 text-sm ${channel === item.id ? 'border-ink bg-ink text-paper' : 'border-line bg-card'}`}
            >
              {item.label}
            </button>
          ))}
        </div>
        <p className="mt-2 text-sm text-ink-soft">{channels.find((item) => item.id === channel)?.note}</p>
        <Button className="mt-4" variant="seal" disabled={!personaId || busy} onClick={() => void start()}>
          Bắt đầu
        </Button>
      </section>
      <aside className="dossier h-fit rounded-3xl p-5">
        <h2 className="font-display text-2xl">Hội thoại gần đây</h2>
        <ul className="mt-3 space-y-2">
          {recent.length === 0 && <li className="text-sm text-ink-soft">Chưa có. Cuộc đầu tiên sẽ hiện ở đây.</li>}
          {recent.map((item) => (
            <li key={item.id}>
              <Link to={`/hoi-thoai/${item.id}`} className="block rounded-2xl px-3 py-2 hover:bg-paper-deep">
                <span className="font-medium">{item.persona_name}</span>
                <span className="mt-0.5 block text-xs text-ink-soft">
                  {item.persona_label} · {item.channel_label} · {item.turn_index} lượt · {item.status === 'ended' ? 'đã trích' : 'đang mở'}
                  {item.is_demo ? ' · demo' : ''}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </aside>
    </div>
  )
}
