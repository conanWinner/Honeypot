import { useEffect, useState } from 'react'
import { ChatRoom } from '../components/ChatRoom'
import { Banner, Button } from '../components/ui'
import { api, type Conversation } from '../lib/api'

export function DemoPage() {
  const [conversation, setConversation] = useState<Conversation | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [demos, setDemos] = useState<{ id: string; title: string; blurb: string }[]>([])

  useEffect(() => {
    api<{ all?: { id: string; title: string; blurb: string }[] }>('/api/demo')
      .then((meta) => setDemos(meta.all ?? []))
      .catch(() => setDemos([]))
  }, [])

  async function start(id = '') {
    setBusy(true)
    setError('')
    try {
      setConversation(await api<Conversation>(`/api/demo/start${id ? `?id=${encodeURIComponent(id)}` : ''}`, { method: 'POST' }))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Không mở được demo.')
    } finally {
      setBusy(false)
    }
  }

  if (!conversation) {
    return (
      <section className="mx-auto max-w-2xl">
        <p className="text-[11px] uppercase tracking-[0.16em] text-seal">Cho giám khảo</p>
        <h1 className="mt-2 font-display text-4xl">Ba phút, một kịch bản đầy đủ</h1>
        <p className="mt-3 text-base leading-7 text-ink-soft">
          Dành cho video chấm. Bạn là người gọi. Agent là bà Nguyễn Thị Năm. Bấm «Tự đi nốt các câu gợi ý», nhìn buồng
          lái đổi giai đoạn, rồi trích xuất. Khoảng hai phút rưỡi nếu không dừng giữa chừng.
        </p>
        <ol className="mt-4 list-decimal space-y-1 pl-5 text-sm leading-6">
          <li>Đối phương tự xưng công an và cô lập nạn nhân.</li>
          <li>Đòi chuyển vào tài khoản giám định, rồi đòi cài phần mềm.</li>
          <li>Khai thác chuyện con ở Đức — nhánh thư viện đã có.</li>
          <li>Khai thác việc bà sống một mình — nhánh mới, agent không khép.</li>
        </ol>
        {error && (
          <div className="mt-4">
            <Banner tone="danger">{error}</Banner>
          </div>
        )}
        <Button className="mt-5" variant="seal" disabled={busy} onClick={() => void start()}>
          Bắt đầu demo
        </Button>
        {demos.length > 1 && (
          <div className="mt-8 space-y-3">
            {demos.slice(1).map((demo) => (
              <div key={demo.id} className="dossier rounded-3xl p-5">
                <h2 className="font-display text-2xl">{demo.title}</h2>
                <p className="mt-2 text-sm leading-6 text-ink-soft">{demo.blurb}</p>
                <Button className="mt-3" variant="ink" disabled={busy} onClick={() => void start(demo.id)}>
                  Chạy demo này
                </Button>
              </div>
            ))}
          </div>
        )}
      </section>
    )
  }

  return (
    <div className="space-y-4">
      <p className="text-sm leading-6 text-ink-soft">{conversation.demo?.blurb}</p>
      <ChatRoom id={conversation.id} />
    </div>
  )
}
