import type { Panel } from '../lib/api'
import { GOAL_LABELS } from '../lib/utils'
import { IocChips, IocLinks, PlaybookCard, RiskGauge, StageTimeline, WarningRefs } from './Intel'

const STAGES = ['mo_dau', 'danh_tinh', 'ly_do', 'co_lap', 'tien', 'kenh_nhan', 'ep', 'nhanh', 'phuc_hoi', 'kep']
const STAGE_SHORT: Record<string, string> = {
  mo_dau: 'Mở',
  danh_tinh: 'Danh',
  ly_do: 'Lý do',
  co_lap: 'Cô lập',
  tien: 'Tiền',
  kenh_nhan: 'Kênh',
  ep: 'Ép',
  nhanh: 'Nhánh',
  phuc_hoi: 'Nghi',
  kep: 'Khép',
}

export function CasePanel({ panel, reasoning, explain = false }: { panel: Panel | null; reasoning?: unknown; explain?: boolean }) {
  const showReason = typeof window !== 'undefined' && localStorage.getItem('gianan-reason') === '1'
  if (!panel) {
    return (
      <aside className="dossier rounded-3xl p-5 text-sm leading-6 text-ink-soft">
        Buồng lái hiện khi đối phương gửi câu đầu. Bên này là giai đoạn kịch bản, mục còn thiếu, và chỉ dấu vừa lộ.
      </aside>
    )
  }
  const confidence = panel.matches[0]?.confidence ?? 0
  const risk = Math.round(Math.max(confidence, panel.suspicion) * 100)
  const stageIndex = Math.max(0, STAGES.indexOf(panel.stage || 'mo_dau'))
  return (
    <aside className="space-y-3">
      <section className="dossier rounded-3xl p-5">
        <div className="flex items-center justify-between gap-3">
          <p className="text-[11px] uppercase tracking-[0.16em] text-seal">Buồng lái</p>
          <p className="text-xs text-ink-soft">{panel.stage_label || 'Mở đầu'}</p>
        </div>
        <ol className="mt-3 flex gap-1">
          {STAGES.map((stage, index) => (
            <li
              key={stage}
              title={STAGE_SHORT[stage]}
              className={`h-1.5 flex-1 rounded-full ${index <= stageIndex ? 'bg-seal' : 'bg-paper-deep'}`}
            />
          ))}
        </ol>
        {panel.risk ? (
          <div className="mt-4">
            <RiskGauge risk={panel.risk} compact />
          </div>
        ) : (
          <>
            <p className="mt-3 text-sm text-ink-soft">Mức khớp / nghi ngờ</p>
            <div className="meter mt-1">
              <span style={{ width: `${risk}%` }} />
            </div>
            <p className="mt-1 text-xs text-ink-soft">{risk}%</p>
          </>
        )}
        {panel.warnings && panel.warnings.length > 0 && (
          <div className="mt-3">
            <WarningRefs refs={panel.warnings} />
          </div>
        )}
      </section>

      <section className="dossier rounded-3xl p-5">
        <p className="text-[11px] uppercase tracking-[0.16em] text-gold">Mục tiêu lượt này</p>
        <h2 className="mt-1 font-display text-2xl text-ink">{panel.goal.label || GOAL_LABELS[panel.goal.goal] || panel.goal.goal}</h2>
        <p className="mt-2 text-sm leading-6 text-ink-soft">{panel.goal.rationale}</p>
        {panel.degraded && <p className="mt-2 text-sm text-seal">Mô hình vừa chậm. Câu này là câu giữ chỗ trong vai.</p>}
      </section>

      {panel.playbook && panel.playbook.targets.length > 0 && (
        <section className="dossier rounded-3xl p-5">
          <p className="text-[11px] uppercase tracking-[0.16em] text-gold">Playbook theo loại lừa</p>
          <div className="mt-2">
            <PlaybookCard playbook={panel.playbook} />
          </div>
        </section>
      )}

      <section className="dossier rounded-3xl p-5">
        <p className="text-[11px] uppercase tracking-[0.16em] text-ink-soft">Bảng khai thác</p>
        <ul className="mt-3 space-y-2">
          {(panel.checklist ?? []).map((item) => (
            <li key={item.key} className="flex items-start gap-2 text-sm">
              <span className={`mt-0.5 grid h-4 w-4 shrink-0 place-items-center rounded-full text-[10px] ${item.done ? 'bg-seal text-white' : 'bg-paper-deep text-ink-soft'}`}>
                {item.done ? '✓' : ''}
              </span>
              <span>
                <span className={item.done ? 'text-ink' : 'text-ink-soft'}>{item.label}</span>
                {item.detail && <span className="mt-0.5 block text-xs text-ink-soft">{item.detail}</span>}
              </span>
            </li>
          ))}
          {(panel.checklist ?? []).length === 0 && <li className="text-sm text-ink-soft">Chưa có mục nào.</li>}
        </ul>
      </section>

      {panel.branch.kind === 'new' && (
        <section className="rounded-3xl border border-seal/40 bg-[#fde7ef] p-5">
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
        <p className="text-[11px] uppercase tracking-[0.16em] text-ink-soft">Chỉ dấu vừa lộ</p>
        <div className="mt-3">
          <IocChips indicators={panel.indicators} />
        </div>
        {panel.ioc_links && panel.ioc_links.length > 0 && (
          <div className="mt-3">
            <IocLinks links={panel.ioc_links} />
          </div>
        )}
      </section>

      {panel.accounts && panel.accounts.length > 0 && (
        <section className="dossier rounded-3xl p-5">
          <p className="text-[11px] uppercase tracking-[0.16em] text-ink-soft">Nơi nhận tiền</p>
          <ul className="mt-2 space-y-2 text-sm">
            {panel.accounts.map((item) => (
              <li key={item.value} className="flex flex-wrap items-baseline justify-between gap-2">
                <span className="font-mono">{item.value.replace(':', ' ')}</span>
                <span className={item.confirmed ? 'text-xs text-[#2f6b45]' : 'text-xs text-ink-soft'}>
                  {item.confirmed ? 'Đã xác nhận' : 'Chờ xác nhận'}
                </span>
                {(item.holder || item.bank) && (
                  <span className="w-full text-xs text-ink-soft">{[item.holder, item.bank].filter(Boolean).join(' · ')}</span>
                )}
              </li>
            ))}
          </ul>
          <p className="mt-2 text-xs leading-5 text-ink-soft">
            Một số chỉ được tính khi họ nhắc lại, hoặc đồng ý sau khi agent đọc lại.
          </p>
        </section>
      )}

      {panel.timeline && panel.timeline.length > 0 && (
        <section className="dossier rounded-3xl p-5">
          <p className="text-[11px] uppercase tracking-[0.16em] text-ink-soft">Dòng thời gian kịch bản</p>
          <StageTimeline timeline={panel.timeline} />
        </section>
      )}

      <section className="dossier rounded-3xl p-5">
        <p className="text-[11px] uppercase tracking-[0.16em] text-ink-soft">Bước trong kịch bản</p>
        {panel.unmatched ? (
          <>
            <p className="mt-1 font-medium">Chưa khớp kịch bản nào trong thư viện</p>
            <p className="mt-1 text-sm leading-6 text-ink-soft">
              Có thể là chiêu mới. Agent đang hỏi theo playbook chung, và sẽ phân loại cả cuộc thoại lúc trích xuất.
              {panel.current_step.script_title && <> Gần nhất hiện tại: {panel.current_step.script_title}.</>}
            </p>
          </>
        ) : (
          <p className="mt-1 font-medium">{panel.current_step.script_title || 'Chưa khớp kịch bản'}</p>
        )}
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

      {explain && panel.rejected_draft && (
        <section className="rounded-3xl border border-seal/30 bg-[#fff7fa] p-5">
          <p className="text-[11px] uppercase tracking-[0.16em] text-seal">Vì sao Agent nói vậy</p>
          <ul className="mt-2 list-disc space-y-1 pl-4 text-sm leading-6">
            {panel.rejected_draft.labels.map((label) => (
              <li key={label}>{label}</li>
            ))}
          </ul>
          <p className="mt-3 text-xs uppercase tracking-[0.12em] text-ink-soft">Câu nháp bị giữ lại</p>
          <p className="mt-1 text-sm leading-6 text-ink-soft">{panel.rejected_draft.text}</p>
        </section>
      )}

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
