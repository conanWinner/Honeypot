import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Banner, Button } from '../components/ui'
import { api, type Dossier } from '../lib/api'

const RELATION: Record<string, string> = {
  new_root: 'Chiêu mới',
  variant: 'Nhánh mới của chiêu đã biết',
  duplicate: 'Trùng chiêu đã biết',
}

function when(iso: string) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('vi-VN', { dateStyle: 'short', timeStyle: 'medium' })
}

function download(dossier: Dossier) {
  const blob = new Blob([JSON.stringify(dossier, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `ho-so-${dossier.case_id}.json`
  link.click()
  URL.revokeObjectURL(url)
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="dossier-print break-inside-avoid rounded-3xl border border-line bg-card p-5 print:rounded-none print:border-0 print:border-t print:p-0 print:pt-4">
      <h2 className="font-display text-xl">{title}</h2>
      <div className="mt-3">{children}</div>
    </section>
  )
}

export function DossierPage() {
  const { id = '' } = useParams()
  const [dossier, setDossier] = useState<Dossier | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api<Dossier>(`/api/conversations/${id}/dossier`)
      .then(setDossier)
      .catch((reason: Error) => setError(reason.message))
  }, [id])

  if (error) return <Banner tone="danger">{error}</Banner>
  if (!dossier) return <p className="text-ink-soft">Đang lập hồ sơ…</p>

  const { classification: cls, contacts } = dossier
  const confirmed = dossier.destinations.filter((row) => row.confirmed).length
  const contactRows: [string, string[]][] = [
    ['Số điện thoại', contacts.phones],
    ['Zalo', contacts.zalo],
    ['Telegram', contacts.telegram],
    ['File cài đặt', contacts.apk],
    ['ID điều khiển từ xa', contacts.remote_ids],
    ['Ứng dụng được nhắc', contacts.apps],
  ]

  return (
    <article className="mx-auto max-w-4xl space-y-4 print:max-w-none print:space-y-3 print:text-[12px]">
      <div className="flex flex-wrap items-center justify-between gap-3 print:hidden">
        <Link to={`/phan-tich/hoi-thoai/${dossier.conversation_id}`} className="text-sm underline">
          ← Về cuộc hội thoại
        </Link>
        <div className="flex gap-2">
          <Button variant="ghost" size="sm" onClick={() => download(dossier)}>
            Tải JSON
          </Button>
          <Button variant="seal" size="sm" onClick={() => window.print()}>
            In / Lưu PDF
          </Button>
        </div>
      </div>

      <header className="rounded-3xl bg-ink p-6 text-paper print:rounded-none print:bg-transparent print:p-0 print:text-ink">
        <p className="text-[11px] uppercase tracking-[0.18em] opacity-75">Hồ sơ tố giác · Honeypot</p>
        <h1 className="mt-1 font-display text-3xl">{dossier.case_id}</h1>
        <p className="mt-2 text-sm opacity-85">
          {cls.extracted ? cls.extracted.title : cls.live_match && !cls.unmatched ? cls.live_match.title : 'Chưa khớp kịch bản nào'}
          {dossier.is_demo ? ' · dữ liệu demo' : ''}
        </p>
        <dl className="mt-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
          {[
            ['Bắt đầu', when(dossier.started_at)],
            ['Kết thúc', when(dossier.ended_at)],
            ['Số lượt đối tượng', String(dossier.turns)],
            ['Nơi nhận tiền', `${dossier.destinations.length} (${confirmed} đã xác nhận)`],
          ].map(([label, value]) => (
            <div key={label}>
              <dt className="text-[11px] uppercase tracking-[0.12em] opacity-70">{label}</dt>
              <dd className="font-semibold">{value}</dd>
            </div>
          ))}
        </dl>
      </header>

      <Section title="1. Nơi nhận tiền">
        {dossier.destinations.length === 0 ? (
          <p className="text-sm text-ink-soft">Đối tượng chưa đưa tài khoản hay ví nào.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] text-left text-sm">
              <thead className="text-[11px] uppercase tracking-[0.1em] text-ink-soft">
                <tr>
                  <th className="py-2 pr-3">Loại</th>
                  <th className="py-2 pr-3">Số</th>
                  <th className="py-2 pr-3">Ngân hàng / chủ</th>
                  <th className="py-2 pr-3">Xác nhận</th>
                  <th className="py-2">Đề nghị</th>
                </tr>
              </thead>
              <tbody>
                {dossier.destinations.map((row) => (
                  <tr key={`${row.kind}-${row.value}`} className="border-t border-line align-top">
                    <td className="py-2 pr-3">{row.kind_label}</td>
                    <td className="py-2 pr-3 font-mono font-semibold">{row.value}</td>
                    <td className="py-2 pr-3">
                      {row.bank || '—'}
                      {row.holder && <span className="block text-ink-soft">{row.holder}</span>}
                    </td>
                    <td className="py-2 pr-3">
                      {row.confirmed ? (
                        <span className="text-pine">
                          <b>Đã xác nhận</b>
                          {row.confirmed_how && <span className="block text-xs">{row.confirmed_how}</span>}
                        </span>
                      ) : (
                        <span className="text-ink-soft">Chưa</span>
                      )}
                      {row.seen_elsewhere.length > 0 && (
                        <span className="mt-1 block text-xs font-semibold text-seal">Gặp ở {row.seen_elsewhere.length} nguồn khác</span>
                      )}
                    </td>
                    <td className="py-2 text-xs leading-5">{row.action}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="mt-3 text-xs leading-5 text-ink-soft">{dossier.caveat}</p>
      </Section>

      <Section title="2. Đường dẫn và kênh liên lạc">
        {contacts.urls.length > 0 && (
          <ul className="mb-3 space-y-1 text-sm">
            {contacts.urls.map((url) => (
              <li key={url.value}>
                <span className="font-mono font-semibold">{url.value}</span>
                {url.note && <span className="text-ink-soft"> — {url.note}</span>}
              </li>
            ))}
          </ul>
        )}
        <dl className="grid gap-2 text-sm sm:grid-cols-2">
          {contactRows
            .filter(([, values]) => values.length)
            .map(([label, values]) => (
              <div key={label}>
                <dt className="text-[11px] uppercase tracking-[0.12em] text-ink-soft">{label}</dt>
                <dd className="font-mono">{values.join(', ')}</dd>
              </div>
            ))}
        </dl>
        {contacts.urls.length === 0 && contactRows.every(([, values]) => !values.length) && (
          <p className="text-sm text-ink-soft">Chưa có.</p>
        )}
      </Section>

      <Section title="3. Đối tượng tự xưng và thủ đoạn">
        <dl className="grid gap-3 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-[11px] uppercase tracking-[0.12em] text-ink-soft">Tự xưng</dt>
            <dd>{dossier.claims.posed_as || '—'}</dd>
          </div>
          <div>
            <dt className="text-[11px] uppercase tracking-[0.12em] text-ink-soft">Thương hiệu bị mạo danh / nhắc tới</dt>
            <dd>{dossier.claims.brands.join(', ') || '—'}</dd>
          </div>
          <div>
            <dt className="text-[11px] uppercase tracking-[0.12em] text-ink-soft">Gây sức ép</dt>
            <dd>{dossier.claims.pressure.join(', ') || '—'}</dd>
          </div>
          <div>
            <dt className="text-[11px] uppercase tracking-[0.12em] text-ink-soft">Dấu hiệu</dt>
            <dd>{dossier.claims.red_flags.join(' · ') || '—'}</dd>
          </div>
        </dl>
      </Section>

      <Section title="4. Phân loại">
        <ul className="space-y-1 text-sm">
          <li>
            Trong lúc chat:{' '}
            {cls.unmatched || !cls.live_match ? (
              <b>chưa khớp kịch bản nào trong thư viện</b>
            ) : (
              <>
                khớp <b>{cls.live_match.title}</b> (độ tin {Math.round(cls.live_match.confidence * 100)}%)
              </>
            )}
          </li>
          {cls.extracted ? (
            <li>
              Lúc trích xuất: <b>{RELATION[cls.extracted.relation] ?? cls.extracted.relation}</b> —{' '}
              <Link className="underline" to={`/canh-bao/kich-ban/${cls.extracted.merge_target?.id ?? cls.extracted.script_id}`}>
                {cls.extracted.merge_target?.title ?? cls.extracted.title}
              </Link>{' '}
              ({cls.extracted.status === 'published' ? 'đã công bố' : cls.extracted.status === 'merged' ? 'đã gộp' : 'chờ duyệt'})
              {cls.extracted.summary && <p className="mt-1 text-ink-soft">{cls.extracted.summary}</p>}
            </li>
          ) : (
            <li className="text-ink-soft">Chưa trích xuất. Bấm «Trích xuất» trong cuộc hội thoại để phân loại cả bản thoại.</li>
          )}
        </ul>
      </Section>

      {dossier.cross_links.length > 0 && (
        <Section title="5. Liên kết với vụ khác">
          <ul className="space-y-2 text-sm">
            {dossier.cross_links.map((hit) => (
              <li key={`${hit.kind}-${hit.value}`}>
                <b>
                  {hit.kind_label} {hit.value}
                </b>{' '}
                xuất hiện ở {hit.count} nguồn khác:{' '}
                {hit.seen_in.map((src, index) => (
                  <span key={src.ref}>
                    {index > 0 && ', '}
                    <Link className="underline" to={src.type === 'script' ? `/canh-bao/kich-ban/${src.ref}` : `/phan-tich/ho-so/${src.ref}`}>
                      {src.label}
                    </Link>
                  </span>
                ))}
              </li>
            ))}
          </ul>
        </Section>
      )}

      <Section title={`${dossier.cross_links.length ? 6 : 5}. Dòng thời gian`}>
        <p className="mb-3 text-xs text-ink-soft">{dossier.decoy.note}</p>
        <ol className="space-y-2 text-sm">
          {dossier.timeline.map((row, index) => (
            <li key={index} className="grid grid-cols-[72px_1fr] gap-3 break-inside-avoid">
              <span className="font-mono text-xs text-ink-soft">
                {new Date(row.at).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
              </span>
              <span>
                <b className={row.role === 'scammer' ? 'text-seal-deep' : 'text-ink-soft'}>{row.who}:</b> {row.text}
                {row.new_iocs.length > 0 && <span className="block text-xs text-pine">+ {row.new_iocs.join(' · ')}</span>}
              </span>
            </li>
          ))}
        </ol>
      </Section>

      <Section title="Nơi tiếp nhận và tính toàn vẹn">
        <ul className="space-y-1 text-sm">
          {dossier.report_channels.map((item) => (
            <li key={item.label}>
              <b>{item.label}:</b> {item.detail}
            </li>
          ))}
        </ul>
        <p className="mt-3 break-all font-mono text-xs">
          {dossier.integrity.algorithm.toUpperCase()} {dossier.integrity.transcript_digest}
        </p>
        <p className="text-xs text-ink-soft">{dossier.integrity.note}</p>
        <p className="mt-2 text-xs text-ink-soft">Lập lúc {when(dossier.generated_at)}.</p>
      </Section>
    </article>
  )
}
