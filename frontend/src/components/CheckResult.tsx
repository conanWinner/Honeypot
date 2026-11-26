import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, type CheckResult as CheckResultData, type IntelHit } from '../lib/api'
import { RiskGauge } from './Intel'
import { Button } from './ui'

export function CheckResult({
  result,
  hits = [],
  busy = false,
  onHandoff,
}: {
  result: CheckResultData
  hits?: IntelHit[]
  busy?: boolean
  onHandoff?: () => void
}) {
  const navigate = useNavigate()
  const [training, setTraining] = useState(false)
  const [error, setError] = useState('')
  const score = result.risk_score ?? Math.round((result.confidence || 0) * 100)
  const seen = hits.reduce((sum, hit) => sum + hit.count, 0)
  const factors = result.risk_factors ?? []

  async function train() {
    if (!result.matched_script) return
    setTraining(true)
    setError('')
    try {
      const created = await api<{ id: string }>('/api/training/sessions', {
        method: 'POST',
        body: JSON.stringify({ script_id: result.matched_script.id, difficulty: 'vua', mode: 'hoc' }),
      })
      navigate(`/luyen-tap/${created.id}`)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Không mở được bài luyện.')
      setTraining(false)
    }
  }

  return (
    <div className="space-y-3">
      <section className="dossier rounded-3xl p-5">
        {factors.length > 0 ? (
          <RiskGauge risk={{ score, level: result.risk, label: result.risk_label, factors }} />
        ) : (
          <>
            <div className="flex items-baseline justify-between gap-3">
              <p className="text-sm text-ink-soft">Mức rủi ro</p>
              <p className="font-display text-4xl">
                {score}
                <span className="text-base text-ink-soft">/100 · {result.risk_label}</span>
              </p>
            </div>
            <div className="meter mt-2">
              <span className="block h-full rounded-full bg-seal" style={{ width: `${Math.max(0, Math.min(100, score))}%` }} />
            </div>
          </>
        )}
        {seen > 0 && <p className="mt-3 text-sm text-ink-soft">Đã thấy trong {seen} kịch bản.</p>}
      </section>
      <section className="dossier rounded-3xl p-5">
        <p className="text-[11px] uppercase tracking-[0.14em] text-ink-soft">Kịch bản khớp</p>
        {result.matched_script ? (
          <p className="mt-1 text-lg font-semibold">
            <Link className="underline" to={`/canh-bao/kich-ban/${result.matched_script.id}`}>
              {result.matched_script.title}
            </Link>
          </p>
        ) : (
          <p className="mt-1 text-sm text-ink-soft">Chưa khớp một kịch bản đã công bố.</p>
        )}
        <p className="mt-3 text-sm leading-6">{result.intent}</p>
        {result.red_flags.length > 0 && (
          <>
            <p className="mt-4 text-[11px] uppercase tracking-[0.14em] text-seal">Cờ đỏ</p>
            <ul className="mt-2 list-disc space-y-1 pl-4 text-sm leading-6">
              {result.red_flags.slice(0, 3).map((flag) => (
                <li key={flag}>{flag}</li>
              ))}
            </ul>
          </>
        )}
        <p className="mt-4 text-sm leading-6">{result.advice}</p>
        <div className="mt-4 flex flex-wrap gap-2">
          {result.matched_script && (
            <Button variant="seal" disabled={training || busy} onClick={() => void train()}>
              {training ? 'Đang mở…' : 'Luyện tình huống này'}
            </Button>
          )}
          {onHandoff && (
            <Button variant="ink" disabled={busy || training} onClick={onHandoff}>
              Giao cho Honeypot đóng vai nạn nhân
            </Button>
          )}
        </div>
        {error && <p className="mt-2 text-sm text-danger">{error}</p>}
      </section>
    </div>
  )
}
