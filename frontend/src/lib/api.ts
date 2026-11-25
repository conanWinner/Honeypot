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
  sources: { type: string; ref: string }[]
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
  indicators?: {
    phones: string[]
    bank_accounts: string[]
    urls: string[]
    apps: string[]
    brands: string[]
    pressure: string[]
  }
  aggressiveness?: string
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
    aggressiveness: reasoning.aggressiveness,
  }
}
