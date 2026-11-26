import { toPng } from 'html-to-image'
import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Banner, Button } from '../components/ui'
import { WarningCard } from '../components/WarningCard'
import { api, type Script } from '../lib/api'
import { formatDay } from '../lib/utils'

export function ScriptPage() {
  const { id } = useParams()
  const [script, setScript] = useState<Script | null>(null)
  const [error, setError] = useState('')
  const [copied, setCopied] = useState(false)
  const cardRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!id) return
    setScript(null)
    api<Script>(`/api/scripts/${id}`)
      .then(setScript)
      .catch((reason: Error) => setError(reason.message))
  }, [id])

  async function download() {
    if (!cardRef.current || !script) return
    const url = await toPng(cardRef.current, { pixelRatio: 2, backgroundColor: '#1c1915' })
    const link = document.createElement('a')
    link.href = url
    link.download = `${script.id}.png`
    link.click()
  }

  async function share() {
    await navigator.clipboard.writeText(window.location.href)
    setCopied(true)
  }

  if (error) return <Banner tone="danger">{error}</Banner>
  if (!script) return <p className="text-ink-soft">Đang mở hồ sơ…</p>

  return (
    <div className="grid gap-6 lg:grid-cols-[1.15fr_0.85fr]">
      <article>
        <p className="text-[11px] uppercase tracking-[0.16em] text-gold">
          {script.category_label} · {script.channel_label}
          {script.brand ? ` · ${script.brand}` : ''} · {script.status === 'published' ? 'công khai' : script.status}
        </p>
        <h1 className="mt-2 font-display text-4xl leading-tight">{script.title}</h1>
        {script.parent && (
          <p className="mt-2 text-sm">
            Nhánh của{' '}
            <Link className="underline" to={`/kich-ban/${script.parent.id}`}>
              {script.parent.title}
            </Link>
          </p>
        )}
        <p className="mt-4 text-base leading-7">{script.summary}</p>
        <p className="mt-3 text-sm text-ink-soft">
          {script.occurrence_count} lượt ghi nhận · thấy từ {formatDay(script.first_seen)} · gần nhất {formatDay(script.last_seen)}
          {script.has_embedding ? ' · đã có embedding' : ' · chưa có embedding'}
        </p>
        {script.indicators && Object.values(script.indicators).some((items) => (items ?? []).length > 0) && (
          <div className="mt-4 flex flex-wrap gap-2">
            {Object.entries(script.indicators).flatMap(([key, items]) =>
              (items ?? []).map((item) => (
                <span key={`${key}-${item}`} className="rounded-full bg-[#fde7ef] px-2.5 py-1 text-xs text-seal-deep">
                  {item}
                </span>
              )),
            )}
          </div>
        )}
        <h2 className="mt-8 font-display text-2xl">Các bước</h2>
        <ol className="mt-3 space-y-3">
          {script.steps?.map((step, index) => (
            <li key={`${step.intent}-${index}`} className="dossier rounded-3xl p-4">
              <p className="text-[11px] uppercase tracking-[0.14em] text-ink-soft">
                {index + 1}. {step.actor === 'scammer' ? 'Đối phương' : 'Nạn nhân'}
              </p>
              <p className="mt-1 font-semibold">{step.intent}</p>
              <ul className="mt-2 list-disc pl-4 text-sm leading-6 text-ink-soft">
                {(step.phrases ?? []).map((phrase) => (
                  <li key={phrase}>{phrase}</li>
                ))}
              </ul>
            </li>
          ))}
        </ol>
        {!!script.variants?.length && (
          <>
            <h2 className="mt-8 font-display text-2xl">Nhánh</h2>
            <ul className="mt-3 space-y-2">
              {script.variants.map((variant) => (
                <li key={variant.id}>
                  <Link className="underline" to={`/kich-ban/${variant.id}`}>
                    {variant.title}
                  </Link>
                </li>
              ))}
            </ul>
          </>
        )}
      </article>
      <aside className="space-y-4">
        <section className="dossier rounded-3xl p-5">
          <h2 className="font-display text-2xl">Cờ đỏ</h2>
          <ul className="mt-2 list-disc space-y-1 pl-4 text-sm leading-6">
            {script.red_flags.map((flag) => (
              <li key={flag}>{flag}</li>
            ))}
          </ul>
          <h2 className="mt-5 font-display text-2xl">Nên làm gì</h2>
          <p className="mt-2 text-sm leading-6">{script.advice}</p>
          {!!script.hooks.length && (
            <>
              <h2 className="mt-5 font-display text-2xl">Hoàn cảnh bị khai thác</h2>
              <ul className="mt-2 list-disc pl-4 text-sm leading-6">
                {script.hooks.map((hook) => (
                  <li key={hook}>{hook}</li>
                ))}
              </ul>
            </>
          )}
        </section>
        <section className="space-y-3">
          <WarningCard script={script} cardRef={cardRef} />
          <div className="flex flex-wrap gap-2">
            <Button variant="seal" type="button" onClick={() => void download()}>
              Tải thẻ cảnh báo
            </Button>
            <Button variant="ghost" type="button" onClick={() => void share()}>
              {copied ? 'Đã chép liên kết' : 'Chép liên kết'}
            </Button>
          </div>
        </section>
        <section className="dossier rounded-3xl p-5 text-sm">
          <h2 className="font-display text-2xl">Nguồn</h2>
          <ul className="mt-2 space-y-1 text-ink-soft">
            {script.sources.map((source, index) => (
              <li key={`${source.ref}-${index}`}>
                {source.url ? (
                  <a className="underline" href={source.url} target="_blank" rel="noreferrer">
                    {source.ref}
                  </a>
                ) : (
                  <>
                    {source.type}: {source.ref}
                  </>
                )}
              </li>
            ))}
          </ul>
          {script.novelty_note && <p className="mt-3">{script.novelty_note}</p>}
        </section>
      </aside>
    </div>
  )
}
