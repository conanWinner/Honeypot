import type { Panel } from '../lib/api'
import { GOAL_LABELS } from '../lib/utils'

export function CasePanel({ panel, reasoning }: { panel: Panel | null; reasoning?: unknown }) {
  const showReason = typeof window !== 'undefined' && localStorage.getItem('gianan-reason') === '1'
  if (!panel) {
    return (
      <aside className="dossier rounded-3xl p-5 text-sm leading-6 text-ink-soft">
        Hồ sơ vụ hiện khi đối phương gửi câu đầu tiên. Bên này là bước đang khớp, cờ đỏ, nhánh mới và mục tiêu của agent.
      </aside>
    )
  }
  return (
    <aside className="space-y-3">
      <section className="dossier rounded-3xl p-5">
        <p className="text-[11px] uppercase tracking-[0.16em] text-gold">Mục tiêu lượt này</p>
        <h2 className="mt-1 font-display text-2xl text-ink">{panel.goal.label || GOAL_LABELS[panel.goal.goal] || panel.goal.goal}</h2>
        <p className="mt-2 text-sm leading-6 text-ink-soft">{panel.goal.rationale}</p>
      </section>

      {panel.branch.kind === 'new' && (
        <section className="rounded-3xl border border-seal/40 bg-[#f8e4dc] p-5">
          <p className="text-[11px] uppercase tracking-[0.16em] text-seal">Nhánh mới</p>
          <p className="mt-1 font-semibold">{panel.branch.hook}</p>
          <p className="mt-1 text-sm leading-6">{panel.branch.description}</p>
        </section>
      )}
      {panel.branch.kind === 'known_variant' && (
        <section className="rounded-3xl border border-pine/30 bg-[#e7f3ec] p-5 text-sm leading-6">
          <p className="text-[11px] uppercase tracking-[0.16em] text-pine">Khớp nhánh đã có</p>
          <p className="mt-1">{panel.branch.description}</p>
        </section>
      )}

      <section className="dossier rounded-3xl p-5">
        <p className="text-[11px] uppercase tracking-[0.16em] text-ink-soft">Bước trong kịch bản</p>
        <p className="mt-1 font-medium">{panel.current_step.script_title || 'Chưa khớp kịch bản'}</p>
        <ol className="mt-3 space-y-2">
          {panel.script_steps.map((step, index) => {
            if (step.actor !== 'scammer') return null
            const current = index === panel.current_step.index
            const done = index < panel.current_step.index
            return (
              <li key={`${step.intent}-${index}`} className="flex gap-3 text-sm">
                <span
                  className={`mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full text-[11px] ${
                    current ? 'bg-seal text-white' : done ? 'bg-ink text-paper' : 'bg-paper-deep text-ink-soft'
                  }`}
                >
                  {index + 1}
                </span>
                <span className={current ? 'font-semibold' : 'text-ink-soft'}>{step.intent}</span>
              </li>
            )
          })}
        </ol>
        {panel.wrap_recommended ? (
          <p className="mt-3 rounded-2xl bg-[#e7f3ec] px-3 py-2 text-sm text-pine">Có thể khép: {panel.wrap_reason}</p>
        ) : (
          <p className="mt-3 text-sm text-ink-soft">{panel.wrap_reason || 'Chưa khép. Vẫn đang kéo kịch bản.'}</p>
        )}
      </section>

      <section className="dossier rounded-3xl p-5">
        <p className="text-[11px] uppercase tracking-[0.16em] text-ink-soft">Kịch bản khớp</p>
        <ul className="mt-3 space-y-3">
          {panel.matches.length === 0 && <li className="text-sm text-ink-soft">Chưa có ứng viên đủ gần.</li>}
          {panel.matches.map((match) => (
            <li key={match.script_id}>
              <div className="flex items-baseline justify-between gap-3 text-sm">
                <span className="font-medium">{match.title}</span>
                <span className="text-ink-soft">{Math.round(match.confidence * 100)}%</span>
              </div>
              <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-paper-deep">
                <div className="h-full bg-seal" style={{ width: `${Math.round(match.confidence * 100)}%` }} />
              </div>
              <p className="mt-1 text-xs text-ink-soft">{match.reason}</p>
            </li>
          ))}
        </ul>
      </section>

      <section className="dossier rounded-3xl p-5">
        <p className="text-[11px] uppercase tracking-[0.16em] text-danger">Cờ đỏ</p>
        <ul className="mt-2 list-disc space-y-1 pl-4 text-sm leading-6">
          {(panel.red_flags.length ? panel.red_flags : ['Chưa thấy cờ đỏ rõ ở lượt này.']).map((flag) => (
            <li key={flag}>{flag}</li>
          ))}
        </ul>
        {panel.suspicion >= 0.6 && (
          <p className="mt-3 text-sm text-seal">Đối phương đang nghi đây không phải người. Agent sẽ lùi lại, không nhận mình là máy.</p>
        )}
        {panel.safety_action !== 'allow' && (
          <p className="mt-2 text-sm text-pine">Lớp an toàn đã chặn câu gốc ({panel.safety_action}).</p>
        )}
      </section>

      {showReason && reasoning != null && (
        <section className="dossier rounded-3xl p-5">
          <p className="text-[11px] uppercase tracking-[0.16em] text-ink-soft">Luận giải của agent</p>
          <pre className="mt-2 max-h-80 overflow-auto whitespace-pre-wrap text-xs leading-5 text-ink-soft">
            {JSON.stringify(reasoning, null, 2)}
          </pre>
        </section>
      )}
    </aside>
  )
}
