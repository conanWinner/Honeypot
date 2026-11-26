import { Link } from 'react-router-dom'
import type { Indicators, IocLink, Playbook, RiskInfo, TimelineEntry, WarningRef } from '../lib/api'

const LEVEL_TONE: Record<string, string> = {
  thap: 'bg-pine',
  trung_binh: 'bg-gold',
  cao: 'bg-seal',
  rat_cao: 'bg-danger',
}

export function RiskGauge({ risk, compact = false }: { risk?: RiskInfo | null; compact?: boolean }) {
  if (!risk) return null
  const tone = LEVEL_TONE[risk.level] ?? 'bg-seal'
  return (
    <div>
      <div className="flex items-baseline justify-between gap-3">
        <p className="text-sm text-ink-soft">Điểm rủi ro</p>
        <p className="font-display text-3xl text-ink">
          {risk.score}
          <span className="text-base text-ink-soft">/100 · {risk.label}</span>
        </p>
      </div>
      <div className="mt-2 h-2 overflow-hidden rounded-full bg-paper-deep">
        <span className={`block h-full rounded-full ${tone}`} style={{ width: `${risk.score}%` }} />
      </div>
      {risk.factors.length > 0 && (
        <ul className="mt-3 space-y-1.5">
          {risk.factors.slice(0, compact ? 4 : 8).map((factor) => (
            <li key={factor.code} className="flex items-start gap-2 text-sm">
              <span className="mt-0.5 shrink-0 rounded-full bg-[#fde7ef] px-1.5 text-[11px] font-semibold text-seal-deep">+{factor.weight}</span>
              <span>
                <span className="text-ink">{factor.label}</span>
                {factor.evidence && <span className="block break-all text-xs text-ink-soft">{factor.evidence}</span>}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export function StageTimeline({ timeline }: { timeline?: TimelineEntry[] }) {
  if (!timeline || timeline.length === 0) return null
  return (
    <ol className="relative mt-3 space-y-3 border-l border-line pl-4">
      {timeline.map((entry) => (
        <li key={entry.turn} className="relative text-sm">
          <span className={`absolute -left-[21px] top-1 h-2.5 w-2.5 rounded-full ${entry.new_iocs.length ? 'bg-seal' : 'bg-ink-soft/40'}`} />
          <div className="flex flex-wrap items-baseline gap-x-2">
            <span className="text-xs text-ink-soft">Lượt {entry.turn}</span>
            <span className="font-medium">{entry.stage_label}</span>
            {entry.risk_delta > 0 && <span className="text-xs text-seal">rủi ro +{entry.risk_delta} → {entry.risk}</span>}
          </div>
          <p className="text-xs text-ink-soft">Agent: {entry.goal_label}</p>
          {entry.new_iocs.length > 0 && (
            <div className="mt-1 flex flex-wrap gap-1">
              {entry.new_iocs.map((item) => (
                <span key={item} className="rounded-full bg-[#fde7ef] px-2 py-0.5 text-[11px] text-seal-deep">
                  {item}
                </span>
              ))}
            </div>
          )}
        </li>
      ))}
    </ol>
  )
}

export function PlaybookCard({ playbook }: { playbook?: Playbook }) {
  if (!playbook || playbook.targets.length === 0) return null
  const done = playbook.targets.filter((row) => row.done).length
  return (
    <div>
      <div className="flex items-baseline justify-between">
        <p className="font-medium">{playbook.label}</p>
        <p className="text-xs text-ink-soft">
          {done}/{playbook.targets.length} chỉ dấu
        </p>
      </div>
      <ul className="mt-2 space-y-1.5">
        {playbook.targets.map((row) => (
          <li key={row.key} className="flex items-start gap-2 text-sm">
            <span
              className={`mt-0.5 grid h-4 w-4 shrink-0 place-items-center rounded-full text-[10px] ${
                row.done ? 'bg-pine text-white' : playbook.next?.key === row.key ? 'bg-seal text-white' : 'bg-paper-deep text-ink-soft'
              }`}
            >
              {row.done ? '✓' : playbook.next?.key === row.key ? '→' : ''}
            </span>
            <span>
              <span className={row.done ? 'text-ink' : 'text-ink-soft'}>{row.label}</span>
              {row.detail && <span className="block break-all text-xs text-ink-soft">{row.detail}</span>}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}

export function IocChips({ indicators }: { indicators?: Indicators | null }) {
  const ind = indicators
  if (!ind) return <p className="text-sm text-ink-soft">Chưa có số, link, ví hay tên ứng dụng.</p>
  const chips = [
    ...(ind.crypto_wallets ?? []).map((item) => `Ví ${item}`),
    ...(ind.apk ?? []).map((item) => `APK ${item}`),
    ...(ind.remote_ids ?? []).map((item) => `ID ${item}`),
    ...(ind.bank_accounts ?? []).map((item) => `TK ${item}`),
    ...(ind.lookalikes ?? []),
    ...(ind.telegram ?? []).map((item) => `Telegram ${item}`),
    ...(ind.zalo ?? []).map((item) => `Zalo ${item}`),
    ...(ind.phones ?? []).map((item) => `ĐT ${item}`),
    ...(ind.urls ?? []),
    ...(ind.apps ?? []),
    ...(ind.techniques ?? []),
    ...(ind.brands ?? []),
    ...(ind.pressure ?? []),
  ]
  if (chips.length === 0) return <p className="text-sm text-ink-soft">Chưa có số, link, ví hay tên ứng dụng.</p>
  return (
    <div className="flex flex-wrap gap-2">
      {chips.map((chip) => (
        <span key={chip} className="break-all rounded-full bg-[#fde7ef] px-2.5 py-1 text-xs text-seal-deep">
          {chip}
        </span>
      ))}
    </div>
  )
}

export function IocLinks({ links }: { links?: IocLink[] }) {
  if (!links || links.length === 0) return null
  return (
    <div className="rounded-2xl border border-seal/40 bg-[#fff1f5] p-3">
      <p className="text-[11px] uppercase tracking-[0.16em] text-seal">Đã gặp ở nơi khác</p>
      <ul className="mt-2 space-y-2 text-sm">
        {links.map((link) => (
          <li key={`${link.kind}-${link.value}`}>
            <span className="font-semibold">
              {link.kind_label} {link.value}
            </span>{' '}
            <span className="text-ink-soft">xuất hiện ở {link.count} nguồn</span>
          </li>
        ))}
      </ul>
      <Link to="/mang-luoi" className="mt-2 inline-block text-xs font-semibold text-seal underline">
        Xem mạng lưới chỉ dấu
      </Link>
    </div>
  )
}

export function WarningRefs({ refs }: { refs?: WarningRef[] }) {
  if (!refs || refs.length === 0) return null
  return (
    <div className="flex flex-wrap gap-2">
      {refs.map((ref) => (
        <Link key={ref.id} to={`/canh-bao#${ref.id}`} className="rounded-full border border-gold/50 bg-[#f8e7c8] px-2.5 py-1 text-xs text-[#6d4708]">
          {ref.rising ? '▲ ' : ''}
          {ref.title}
        </Link>
      ))}
    </div>
  )
}
