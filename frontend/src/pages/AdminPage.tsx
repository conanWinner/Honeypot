import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Banner, Button } from '../components/ui'
import { api, ApiError, type Script } from '../lib/api'

const RELATION_LABELS: Record<string, string> = {
  new_root: 'Chiêu mới',
  variant: 'Nhánh của kịch bản có sẵn',
  duplicate: 'Đề xuất gộp',
}

export function AdminPage() {
  const [items, setItems] = useState<Script[] | null>(null)
  const [error, setError] = useState('')
  const [token, setToken] = useState(() => sessionStorage.getItem('gianan-admin') ?? '')
  const [notice, setNotice] = useState<{ id: string; title: string; merged?: boolean } | null>(null)
  const [needsToken, setNeedsToken] = useState(false)

  function headers(): HeadersInit | undefined {
    return token ? { 'X-Admin-Token': token } : undefined
  }

  async function load(next = token) {
    setError('')
    try {
      const rows = await api<Script[]>('/api/moderation', {
        headers: next ? { 'X-Admin-Token': next } : undefined,
      })
      setItems(rows)
      setNeedsToken(false)
    } catch (reason) {
      if (reason instanceof ApiError && reason.status === 401) {
        setNeedsToken(true)
        setItems([])
      } else {
        setError(reason instanceof Error ? reason.message : 'Không tải được hàng chờ.')
      }
    }
  }

  useEffect(() => {
    void load()
    // token is read from the initial state; reload is explicit
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function act(id: string, action: 'approve' | 'reject', mode = '') {
    const query = mode ? `?mode=${mode}` : ''
    const result = await api<Script>(`/api/moderation/${id}/${action}${query}`, { method: 'POST', headers: headers() })
    if (action === 'approve' && result.id === id && result.status === 'published') {
      setNotice({ id: result.id, title: result.title })
    } else if (action === 'approve') {
      setNotice({ id: result.id, title: result.title, merged: true })
    } else {
      setNotice(null)
    }
    await load()
  }

  return (
    <div>
      <p className="text-[11px] uppercase tracking-[0.16em] text-seal">Kiểm duyệt</p>
      <h1 className="mt-2 font-display text-4xl">Hàng chờ trước khi công bố</h1>
      <p className="mt-2 max-w-2xl text-sm leading-6 text-ink-soft">
        Kịch bản trích từ hội thoại không hiện ở thư viện công khai cho đến khi có người duyệt. Nếu chưa gắn ADMIN_TOKEN,
        cửa này mở cho bản demo và cần khóa lại trước khi đưa lên mạng.
      </p>
      {notice && (
        <div className="mt-4">
          <Banner tone="ok">
            {notice.merged ? (
              <>
                Đã gộp vào{' '}
                <Link className="font-semibold underline" to={`/canh-bao/kich-ban/${notice.id}`}>
                  {notice.title}
                </Link>
                . Số lần ghi nhận và chỉ dấu của kịch bản đó đã được cập nhật.
              </>
            ) : (
              <>
                Đã công bố{' '}
                <Link className="font-semibold underline" to={`/canh-bao/kich-ban/${notice.id}`}>
                  {notice.title}
                </Link>
                . Người dùng thấy ngay ở mục <b>Chiêu mới ghi nhận</b> trên{' '}
                <Link className="font-semibold underline" to="/">
                  Trang chủ
                </Link>
                .
              </>
            )}
          </Banner>
        </div>
      )}
      {needsToken && (
        <form
          className="mt-4 flex flex-wrap gap-2"
          onSubmit={(event) => {
            event.preventDefault()
            sessionStorage.setItem('gianan-admin', token)
            void load(token)
          }}
        >
          <input
            value={token}
            onChange={(event) => setToken(event.target.value)}
            type="password"
            placeholder="Mã quản trị"
            className="h-10 rounded-full border border-line bg-card px-4 text-sm"
          />
          <Button type="submit" variant="ink">
            Mở hàng chờ
          </Button>
        </form>
      )}
      {error && (
        <div className="mt-4">
          <Banner tone="danger">{error}</Banner>
        </div>
      )}
      {items === null && !error && <p className="mt-6 text-sm text-ink-soft">Đang mở hàng chờ…</p>}
      {items && items.length === 0 && !needsToken && (
        <p className="mt-6 text-sm text-ink-soft">Hàng chờ trống. Kết thúc một hội thoại có nhánh mới để thấy bản chờ ở đây.</p>
      )}
      <ul className="mt-5 space-y-3">
        {items?.map((script) => (
          <li key={script.id} className="dossier rounded-3xl p-5">
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-[11px] uppercase tracking-[0.14em] text-gold">{script.category_label}</p>
              {script.relation && (
                <span className="rounded-full border border-line px-2 py-0.5 text-[11px] text-ink-soft">
                  {RELATION_LABELS[script.relation] ?? script.relation}
                </span>
              )}
            </div>
            <h2 className="mt-1 font-display text-2xl">
              <Link to={`/canh-bao/kich-ban/${script.id}`} className="underline">
                {script.title}
              </Link>
            </h2>
            <p className="mt-2 text-sm leading-6 text-ink-soft">{script.summary}</p>
            {script.novelty_note && <p className="mt-2 text-sm">{script.novelty_note}</p>}
            {script.merge_target && (
              <p className="mt-2 text-sm">
                Đề xuất gộp vào{' '}
                <Link to={`/canh-bao/kich-ban/${script.merge_target}`} className="font-semibold underline">
                  {script.merge_target_title || script.merge_target}
                </Link>
                . Gộp sẽ thêm câu chữ và chỉ dấu vào kịch bản đó, không tạo kịch bản mới.
              </p>
            )}
            <div className="mt-3 flex flex-wrap gap-2">
              {script.merge_target ? (
                <>
                  <Button size="sm" variant="seal" type="button" onClick={() => void act(script.id, 'approve', 'merge')}>
                    Gộp vào kịch bản có sẵn
                  </Button>
                  <Button size="sm" variant="ink" type="button" onClick={() => void act(script.id, 'approve', 'publish')}>
                    Không trùng, công bố riêng
                  </Button>
                </>
              ) : (
                <Button size="sm" variant="seal" type="button" onClick={() => void act(script.id, 'approve')}>
                  Duyệt
                </Button>
              )}
              <Button size="sm" variant="ghost" type="button" onClick={() => void act(script.id, 'reject')}>
                Từ chối
              </Button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}
