import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { Button } from '../components/ui'
import { api, type TrainingGroup, type TrainingScenario } from '../lib/api'
import { cn } from '../lib/utils'

const channels: Record<string, string> = {
  phone: 'Điện thoại',
  zalo: 'Zalo',
  sms: 'SMS',
  facebook: 'Facebook',
  web: 'Web',
  telegram: 'Telegram',
  multi: 'Nhiều kênh',
}

const difficulties = [
  { id: 'de', label: 'Dễ' },
  { id: 'vua', label: 'Vừa' },
  { id: 'kho', label: 'Khó' },
] as const

export function TrainingHubPage() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const preset = params.get('script') ?? ''
  const [groups, setGroups] = useState<TrainingGroup[]>([])
  const [scenarios, setScenarios] = useState<TrainingScenario[]>([])
  const [group, setGroup] = useState('')
  const [picked, setPicked] = useState<string | null>(null)
  const selected = picked ?? preset
  const [difficulty, setDifficulty] = useState<(typeof difficulties)[number]['id']>('vua')
  const [mode, setMode] = useState<'hoc' | 'thu_thach'>('thu_thach')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    const query = group ? `?group=${encodeURIComponent(group)}` : ''
    api<{ groups: TrainingGroup[]; scenarios: TrainingScenario[] }>(`/api/training/scenarios${query}`)
      .then((data) => {
        setGroups(data.groups)
        setScenarios(data.scenarios)
      })
      .catch((reason: Error) => setError(reason.message))
  }, [group])

  async function start(scriptId?: string) {
    setBusy(true)
    setError('')
    try {
      const created = await api<{ id: string }>('/api/training/sessions', {
        method: 'POST',
        body: JSON.stringify({
          script_id: scriptId || undefined,
          group: !scriptId && group ? group : undefined,
          difficulty,
          mode,
        }),
      })
      navigate(`/luyen-tap/${created.id}`)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Không mở được bài luyện.')
      setBusy(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <p className="text-[11px] uppercase tracking-[0.16em] text-seal">Phản xạ</p>
        <h1 className="mt-2 font-display text-4xl">Luyện tập nhận diện lừa đảo</h1>
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        <article className="dossier rounded-3xl p-5">
          <h2 className="font-display text-2xl">Mô phỏng hội thoại (5 phút)</h2>
          <p className="mt-2 text-sm leading-6 text-ink-soft">
            Bạn nhắn với một người lừa đảo giả. Số, tài khoản và đường dẫn trong bài đều là giả.
          </p>
        </article>
        <article className="dossier rounded-3xl p-5">
          <h2 className="font-display text-2xl">Trắc nghiệm 2 phút</h2>
          <p className="mt-2 text-sm leading-6 text-ink-soft">Tám tin nhắn. Chọn lừa đảo hoặc an toàn, xem giải thích ngay.</p>
          <Button asChild className="mt-4" variant="ghost">
            <Link to="/luyen-tap/trac-nghiem">Làm trắc nghiệm</Link>
          </Button>
        </article>
      </div>

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => setGroup('')}
          className={cn('rounded-full px-3 py-1 text-sm', group === '' ? 'bg-ink text-paper' : 'border border-line bg-card')}
        >
          Tất cả
        </button>
        {groups.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => setGroup(item.id)}
            className={cn('rounded-full px-3 py-1 text-sm', group === item.id ? 'bg-ink text-paper' : 'border border-line bg-card')}
          >
            {item.label} ({item.count})
          </button>
        ))}
      </div>

      <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.14em] text-ink-soft">Độ khó</p>
          <div className="mt-2 flex rounded-full border border-line bg-card p-1">
            {difficulties.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setDifficulty(item.id)}
                className={cn('rounded-full px-4 py-1.5 text-sm', difficulty === item.id ? 'bg-ink text-paper' : 'text-ink-soft')}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>
        <div>
          <p className="text-xs uppercase tracking-[0.14em] text-ink-soft">Chế độ</p>
          <div className="mt-2 flex gap-2">
            <button
              type="button"
              onClick={() => setMode('hoc')}
              className={cn('rounded-full px-4 py-1.5 text-sm', mode === 'hoc' ? 'bg-ink text-paper' : 'border border-line bg-card')}
            >
              Học
            </button>
            <button
              type="button"
              onClick={() => setMode('thu_thach')}
              className={cn('rounded-full px-4 py-1.5 text-sm', mode === 'thu_thach' ? 'bg-ink text-paper' : 'border border-line bg-card')}
            >
              Thử thách
            </button>
          </div>
          <p className="mt-2 max-w-sm text-xs leading-5 text-ink-soft">
            {mode === 'hoc' ? 'Cờ đỏ hiện ngay khi xuất hiện. Phù hợp khi mới tập.' : 'Cờ đỏ bị che. Bạn tự nhận ra trước khi bấm chặn.'}
          </p>
        </div>
        <Button variant="seal" disabled={busy} onClick={() => void start(selected || undefined)}>
          {selected ? 'Bắt đầu kịch bản đã chọn' : 'Ngẫu nhiên'}
        </Button>
      </div>
      {error && <p className="text-sm text-danger">{error}</p>}

      <div className="grid gap-3 md:grid-cols-2">
        {scenarios.map((item) => (
          <button
            key={item.script_id}
            type="button"
            onClick={() => setPicked(item.script_id)}
            className={cn(
              'dossier rounded-3xl p-4 text-left hover:border-ink',
              selected === item.script_id && 'border-ink ring-1 ring-ink',
            )}
          >
            <p className="text-[11px] uppercase tracking-[0.14em] text-gold">
              {item.category_label} · {channels[item.channel] || item.channel}
            </p>
            <h2 className="mt-1 font-display text-xl leading-tight">{item.title}</h2>
            <p className="mt-2 text-xs text-ink-soft">
              Đã ghi nhận {item.occurrence_count} lần · {item.stages} bước
              {item.rising ? ' · Đang nổi' : ''}
            </p>
          </button>
        ))}
      </div>
    </div>
  )
}
