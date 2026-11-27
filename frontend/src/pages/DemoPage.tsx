import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ChatRoom } from '../components/ChatRoom'
import { Banner, Button } from '../components/ui'
import { api, type Conversation, type DemoMeta } from '../lib/api'

const LOOP = [
  ['Chat', 'Chọn một chiêu mới bên dưới. Bạn đóng vai kẻ lừa, bấm «Tự đi nốt các câu gợi ý». Buồng lái báo «Chưa khớp kịch bản nào» — agent không biết trước chiêu này.'],
  ['Trích xuất', 'Bấm «Trích xuất». Hệ thống so cả bản thoại với thư viện, thấy không khớp chắc, tạo kịch bản gốc mới và đưa vào hàng chờ.'],
  ['Duyệt', 'Bấm «Duyệt ngay» ngay trong cuộc chat, hoặc vào tab Kiểm duyệt. Không gì lên thư viện công khai khi chưa có người duyệt.'],
  ['Người dùng thấy', 'Mở Trang chủ: mục «Chiêu mới ghi nhận» hiện chiêu vừa duyệt, kèm dấu hiệu và lời khuyên. Ô kiểm tra tin nhắn cũng nhận ra nó.'],
  ['Chạy lại', 'Chạy lại đúng chiêu đó: lần này hệ thống nhận ra chiêu đã biết và chỉ đề xuất gộp, không tạo bản trùng.'],
]

function DemoCard({ demo, busy, onStart }: { demo: DemoMeta; busy: boolean; onStart: (id: string) => void }) {
  return (
    <article className="dossier flex flex-col rounded-3xl p-5">
      <p className={`text-[11px] font-semibold uppercase tracking-[0.14em] ${demo.kind === 'new' ? 'text-seal' : 'text-pine'}`}>
        {demo.kind === 'new' ? 'Chưa có trong thư viện' : 'Đã có trong thư viện'} · {demo.lines.length} câu
      </p>
      <h3 className="mt-1 font-display text-xl leading-snug">{demo.title}</h3>
      <p className="mt-2 text-sm leading-6 text-ink-soft">{demo.blurb}</p>
      <p className="mt-2 rounded-2xl bg-paper-deep px-3 py-2 text-xs leading-5">
        <b>Kỳ vọng:</b> {demo.expect}
      </p>
      <Button className="mt-3 self-start" variant={demo.kind === 'new' ? 'seal' : 'ink'} size="sm" disabled={busy} onClick={() => onStart(demo.id)}>
        Chạy kịch bản này
      </Button>
    </article>
  )
}

export function DemoPage() {
  const [conversation, setConversation] = useState<Conversation | null>(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const [demos, setDemos] = useState<DemoMeta[]>([])

  useEffect(() => {
    api<{ all?: DemoMeta[] }>('/api/demo')
      .then((meta) => setDemos(meta.all ?? []))
      .catch(() => setDemos([]))
  }, [])

  async function start(id = '') {
    setBusy(true)
    setError('')
    try {
      setConversation(await api<Conversation>(`/api/demo/start${id ? `?id=${encodeURIComponent(id)}` : ''}`, { method: 'POST' }))
      window.scrollTo({ top: 0 })
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Không mở được demo.')
    } finally {
      setBusy(false)
    }
  }

  async function reset() {
    if (!window.confirm('Xóa mọi hội thoại demo và các kịch bản trích từ chúng? Thư viện gốc giữ nguyên.')) return
    setBusy(true)
    setError('')
    try {
      const token = sessionStorage.getItem('gianan-admin') ?? ''
      const result = await api<{ conversations: number; scripts: number }>('/api/demo/reset', {
        method: 'POST',
        headers: token ? { 'X-Admin-Token': token } : undefined,
      })
      setNotice(`Đã dọn ${result.conversations} hội thoại demo và ${result.scripts} kịch bản trích từ chúng.`)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Không dọn được. Nếu đã đặt ADMIN_TOKEN, nhập ở tab Kiểm duyệt trước.')
    } finally {
      setBusy(false)
    }
  }

  if (conversation) {
    return (
      <div className="space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="max-w-3xl">
            <p className="text-[11px] uppercase tracking-[0.14em] text-seal">{conversation.demo?.kind === 'new' ? 'Chiêu mới' : 'Chiêu đã biết'}</p>
            <h2 className="font-display text-2xl">{conversation.demo?.title}</h2>
            <p className="mt-1 text-sm leading-6 text-ink-soft">{conversation.demo?.expect}</p>
          </div>
          <Button variant="ghost" size="sm" onClick={() => setConversation(null)}>
            ← Chọn kịch bản khác
          </Button>
        </div>
        <ChatRoom id={conversation.id} />
      </div>
    )
  }

  const fresh = demos.filter((demo) => demo.kind === 'new')
  const known = demos.filter((demo) => demo.kind === 'known')

  return (
    <div className="space-y-8">
      <section className="max-w-3xl">
        <p className="text-[11px] uppercase tracking-[0.16em] text-seal">Cho giám khảo</p>
        <h2 className="mt-2 font-display text-4xl">Từ một chiêu chưa ai biết tới cảnh báo cho người dùng</h2>
        <p className="mt-3 text-base leading-7 text-ink-soft">
          Bạn đóng vai kẻ lừa, agent đóng vai nạn nhân. Mỗi kịch bản mất khoảng hai phút. Mọi số tài khoản, ví và đường dẫn ở
          đây đều bịa ra cho demo.
        </p>
      </section>

      <section className="rounded-3xl bg-ink p-5 text-paper">
        <h3 className="font-display text-2xl">Vòng chiêu mới, năm bước</h3>
        <ol className="mt-4 grid gap-3 md:grid-cols-5">
          {LOOP.map(([title, body], index) => (
            <li key={title} className="rounded-2xl bg-white/10 p-3">
              <p className="font-display text-3xl text-[#ff9ec0]">{index + 1}</p>
              <p className="mt-1 font-semibold">{title}</p>
              <p className="mt-1 text-xs leading-5 text-paper/80">{body}</p>
            </li>
          ))}
        </ol>
        <p className="mt-4 text-sm text-paper/80">
          Sau đó mở{' '}
          <Link className="underline" to="/phan-tich/noi-nhan-tien">
            Nơi nhận tiền
          </Link>{' '}
          để thấy danh sách tài khoản, ví cần khóa, hoặc bấm «Xuất hồ sơ» trong cuộc chat để in hồ sơ tố giác.
        </p>
      </section>

      {error && <Banner tone="danger">{error}</Banner>}
      {notice && <Banner tone="ok">{notice}</Banner>}

      <section>
        <h3 className="font-display text-2xl">Chiêu hoàn toàn mới ({fresh.length})</h3>
        <p className="mt-1 text-sm text-ink-soft">
          Không có trong 48 kịch bản gốc. Gợi ý: chạy «Phạt nguội» rồi «Đổi bằng lái» — hai chiêu dùng chung một tài khoản nhận
          tiền, tab Nơi nhận tiền sẽ chỉ ra cùng một đường dây.
        </p>
        <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {fresh.map((demo) => (
            <DemoCard key={demo.id} demo={demo} busy={busy} onStart={(id) => void start(id)} />
          ))}
        </div>
      </section>

      <section>
        <h3 className="font-display text-2xl">Chiêu đã có trong thư viện ({known.length})</h3>
        <p className="mt-1 text-sm text-ink-soft">Agent bám kịch bản khớp, moi chỉ dấu, và lúc trích xuất chỉ đề xuất gộp.</p>
        <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {known.map((demo) => (
            <DemoCard key={demo.id} demo={demo} busy={busy} onStart={(id) => void start(id)} />
          ))}
        </div>
      </section>

      <section className="flex flex-wrap items-center justify-between gap-3 rounded-3xl border border-dashed border-line p-4">
        <p className="text-sm text-ink-soft">Tập dượt xong? Dọn dữ liệu demo để chiêu mới lại là «mới» trong lần trình bày.</p>
        <Button variant="ghost" size="sm" disabled={busy} onClick={() => void reset()}>
          Đặt lại dữ liệu demo
        </Button>
      </section>
    </div>
  )
}
