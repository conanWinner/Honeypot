export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers || {}),
    },
  })
  const text = await response.text()
  let body: { detail?: unknown } = {}
  try {
    body = text ? JSON.parse(text) : {}
  } catch {
    body = { detail: text || 'Máy chủ không trả lời được.' }
  }
  if (!response.ok) {
    const detail = typeof body.detail === 'string' ? body.detail : 'Máy chủ không trả lời được.'
    throw new ApiError(response.status, detail)
  }
  return body as T
}

export type Health = {
  ok: boolean
  llm: { provider: string; model: string; mock: boolean }
  embeddings: { model: string; mock: boolean; ready: number; published: number }
  database: string
  admin_open: boolean
}

export type LlmHealth = {
  ok: boolean
  mock: boolean
  latency_ms: number | null
  model: string
  error: string
  warming: boolean
}

export type Persona = {
  id: string
  label: string
  display_name: string
  age: number
  job: string
  city: string
  region: string
  texting_style: string
  bio: string
  hooks: string[]
  fake_profile: Record<string, string>
  examples: string[]
}

export type Step = { actor: string; intent: string; phrases?: string[] }

export type Script = {
  id: string
  parent_id: string | null
  title: string
  category: string
  category_label: string
  channel: string
  channel_label: string
  brand: string
  summary: string
  hooks: string[]
  red_flags: string[]
  advice: string
  sources: { type: string; ref: string; url?: string }[]
  warnings?: WarningRef[]
  first_seen: string
  last_seen: string
  occurrence_count: number
  status: string
  novelty_note: string
  has_embedding: boolean
  indicators?: {
    phones?: string[]
    bank_accounts?: string[]
    urls?: string[]
    apps?: string[]
    brands?: string[]
    pressure?: string[]
  }
  variant_count: number
  steps?: Step[]
  parent?: { id: string; title: string }
  variants?: Script[]
}

export type Message = {
  id: string
  role: 'scammer' | 'victim'
  content: string
  reasoning: Record<string, unknown> | null
  created_at: string
}

export type Panel = {
  matches: {
    script_id: string
    title: string
    confidence: number
    current_step_index: number
    current_step_intent: string
    reason: string
  }[]
  current_step: {
    index: number
    intent: string
    script_id: string
    script_title: string
    family_id: string
  }
  script_steps: { actor: string; intent: string }[]
  red_flags: string[]
  extracted_fact: string
  branch: { detected: boolean; kind: string; hook: string; description: string; variant_script_id: string }
  goal: { goal: string; label: string; rationale: string }
  wrap_recommended: boolean
  wrap_reason: string
  suspicion: number
  provider: string
  mock: boolean
  safety_action: string
  step_source: string
  stage?: string
  stage_label?: string
  checklist?: { key: string; label: string; done: boolean; detail: string }[]
  indicators?: Indicators
  aggressiveness?: string
  degraded?: boolean
  risk?: RiskInfo
  timeline?: TimelineEntry[]
  playbook?: Playbook
  ioc_links?: IocLink[]
  warnings?: WarningRef[]
  rejected_draft?: {
    text: string
    reasons: string[]
    labels: string[]
    action: string
  } | null
}

export type RiskFactor = { code: string; label: string; weight: number; evidence: string }
export type RiskInfo = { score: number; level: string; label: string; factors: RiskFactor[] }
export type TimelineEntry = {
  turn: number
  stage: string
  stage_label: string
  goal: string
  goal_label: string
  new_iocs: string[]
  risk: number
  risk_delta: number
}
export type PlaybookRow = { key: string; label: string; goal: string; hint: string; done: boolean; detail: string }
export type Playbook = { category: string; label: string; targets: PlaybookRow[]; next: PlaybookRow | null }
export type IocLink = { kind: string; kind_label: string; value: string; count: number; seen_in: { type: string; label: string; ref: string }[] }
export type WarningRef = { id: string; title: string; rising: boolean }
export type Source = { title: string; url: string; date: string }
export type WarningCard = {
  id: string
  title: string
  categories: string[]
  category_labels?: string[]
  channels: string[]
  targets: string
  rising: boolean
  first_reported: string
  how: string[]
  lines: string[]
  red_flags: string[]
  do: string
  sources: Source[]
  scripts?: { id: string; title: string; category: string }[]
}
export type Indicators = {
  phones?: string[]
  bank_accounts?: string[]
  urls?: string[]
  apps?: string[]
  brands?: string[]
  pressure?: string[]
  hotlines?: string[]
  apk?: string[]
  telegram?: string[]
  zalo?: string[]
  crypto_wallets?: string[]
  remote_ids?: string[]
  techniques?: string[]
  lookalikes?: string[]
}

export type Conversation = {
  id: string
  channel: string
  channel_label: string
  status: string
  is_demo: boolean
  provider: string
  persona: Persona
  messages: Message[]
  demo_lines: string[]
  turn_index: number
  wrap_recommended: boolean
  wrap_reason: string
  fake_otp: string
  extracted_script_id: string | null
  created_at: string
  demo?: { id: string; title: string; blurb: string; expected_script: string }
}

export type TrainingScenario = {
  script_id: string
  title: string
  category: string
  category_label: string
  group: string
  channel: string
  brand: string
  occurrence_count: number
  stages: number
  rising: boolean
}

export type TrainingGroup = { id: string; label: string; count: number }

export type TrainingStage = { index: number; intent: string; reached: boolean }

export type TrainingChatMessage = {
  id: string
  role: 'scammer' | 'user' | 'system'
  text: string
  stage_index: number
  flags?: number[]
  created_at: string
}

export type VisibleFlags =
  | { mode: 'hoc'; items: { id: number; text: string; stage_index: number }[] }
  | { mode: 'thu_thach'; count: number }

export type TrainingSession = {
  id: string
  status: 'active' | 'safe' | 'scammed' | 'timeout'
  end_reason: string
  score: number | null
  scenario: {
    script_id: string
    title: string
    category: string
    category_label: string
    channel: string
    channel_label: string
    scammer_name: string
    brand: string
    context?: { who: string; channel: string; role: string; goal: string }
  }
  difficulty: 'de' | 'vua' | 'kho'
  mode: 'hoc' | 'thu_thach'
  turn_index: number
  max_turns: number
  stage_index: number
  stages: TrainingStage[]
  messages: TrainingChatMessage[]
  visible_flags: VisibleFlags
  hints_used: number
}

export type TrainingDebrief = {
  score: number
  label: string
  status: string
  end_reason: string
  turns: number
  duration_s: number
  stopped_before: string
  stages: { index: number; intent: string; outcome: 'caught' | 'missed' | 'not_reached' | 'fell' | 'stopped'; user_quote?: string }[]
  flags: { text: string; stage_index: number; quote: string; caught: boolean }[]
  leaked: string[]
  tips: string[]
  warning_card_ids: string[]
  hints_used: number
  turning_point?: { turn: number; label: string; quote: string; sentence: string }
  script: { id: string; title: string; occurrence_count: number; last_seen: string; sources: Script['sources'] }
}

export type QuizQuestion = {
  id: string
  text: string
  channel: string
  answer: 'scam' | 'safe'
  explain: string
  script_id?: string | null
  sender?: string
  sender_detail?: string
  time?: string
  context?: string
  lines?: string[]
  highlights?: string[]
  flags?: string[]
  action?: string
  warning_id?: string
}

export type CheckResult = {
  risk: string
  risk_label: string
  is_scam?: boolean
  verdict?: 'benign' | 'scam' | 'unclear'
  confidence: number
  intent: string
  red_flags: string[]
  matched_script: { id: string; title: string; confidence: number } | null
  next_step: { intent: string; phrases: string[] } | null
  advice: string
  risk_score?: number
  risk_factors?: RiskFactor[]
  indicators?: Indicators
}

export type IntelHit = {
  kind: string
  kind_label: string
  value: string
  count: number
  seen_in: { type: string; label: string; ref: string }[]
}

export function panelFromMessage(message: Message | undefined): Panel | null {
  const reasoning = message?.reasoning as Record<string, any> | null
  if (!reasoning?.analyst) return null
  const top = reasoning.analyst.matches?.[0]
  return {
    matches: reasoning.analyst.matches ?? [],
    current_step: {
      index: top?.current_step_index ?? 0,
      intent: top?.current_step_intent ?? '',
      script_id: top?.script_id ?? '',
      script_title: top?.title ?? '',
      family_id: '',
    },
    script_steps: reasoning.script_steps ?? [],
    red_flags: reasoning.analyst.red_flags ?? [],
    extracted_fact: reasoning.analyst.extracted_fact ?? '',
    branch: reasoning.branch ?? { detected: false, kind: 'none', hook: '', description: '', variant_script_id: '' },
    goal: {
      goal: reasoning.planner?.goal ?? '',
      label: reasoning.planner?.label ?? '',
      rationale: reasoning.planner?.rationale ?? '',
    },
    wrap_recommended: Boolean(reasoning.wrap?.recommended),
    wrap_reason: reasoning.wrap?.reason ?? '',
    suspicion: reasoning.inbound_safety?.suspicion_level ?? 0,
    provider: reasoning.provider ?? '',
    mock: Boolean(reasoning.mock),
    safety_action: reasoning.outbound_safety?.action ?? 'allow',
    step_source: reasoning.step_source ?? '',
    stage: reasoning.stage,
    stage_label: reasoning.stage_label,
    checklist: reasoning.checklist,
    indicators: reasoning.indicators,
    risk: reasoning.risk,
    timeline: reasoning.timeline,
    playbook: reasoning.playbook,
    ioc_links: reasoning.ioc_links,
    warnings: reasoning.warnings,
    aggressiveness: reasoning.aggressiveness,
    degraded: Boolean(reasoning.degraded),
    rejected_draft: reasoning.outbound_safety?.rejected_draft ?? null,
  }
}
