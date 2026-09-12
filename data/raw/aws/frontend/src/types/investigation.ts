export interface Hypothesis {
  service: string
  description: string
  search_terms: string[]
  rationale: string
  time_window_start?: string
  time_window_end?: string
}

export type Hypotheses = Record<string, Hypothesis>

export interface Scenario {
  name: string
  display_name?: string
  description: string
  has_hitl: boolean
}

export interface ScenarioDocs {
  incident: string | null
  context: Record<string, string>
  evidence: Record<string, string>
  readme: string | null
  ground_truth: GroundTruth | null
}

export interface GroundTruthIncident {
  date?: string
  day?: string
  time_range?: string
  severity?: string
  symptom?: string
  root_cause?: { issue?: string; details?: string }
  evidence_keywords?: string[]
  resolution?: string
}

export interface GroundTruth {
  scenario_id?: string
  scenario_name?: string
  display_name?: string
  domain?: string
  difficulty?: string
  description?: string

  // HITL fields
  hitl_scenario?: boolean
  hitl_clarification_type?: string
  hitl_flow?: Record<string, unknown>
  incidents?: Record<string, GroundTruthIncident>
  alternate_scenarios?: Record<string, { user_says?: string; correct_root_cause?: string }>
  current_incident?: { description?: string; most_likely_date?: string; correct_root_cause?: string }
  why_clarification_matters?: string
  why_change_correlation_matters?: string
  why_scope_matters?: string
  without_clarification?: string

  // Plain English fields for ScenarioDetail
  plain_english_summary?: string
  causation_chain?: Array<{ step: string; service: string }>

  // Root cause (object shape for most scenarios)
  root_cause?: { service?: string; issue?: string; details?: string } | string
  evidence_keywords?: string[]

  // Non-HITL extras
  trap?: { obvious_answer?: string; why_wrong?: string; misleading_evidence?: string[]; actual_evidence?: string[] }
  red_herrings?: Array<string | { name?: string; symptom?: string; event?: string; evidence?: string; service?: string; description?: string; why_misleading?: string }>
  chain_of_events?: string[]
  timeline?: Record<string, string>
  victim_service?: string
  victim_symptoms?: string[]

  // Some scenarios nest data under a `ground_truth` key
  ground_truth?: {
    root_cause?: string
    root_cause_service?: string
    chain_of_events?: string[]
    trap?: { obvious_answer?: string; why_wrong?: string; misleading_evidence?: string[]; actual_evidence?: string[] }
    [key: string]: unknown
  }

  [key: string]: unknown
}

export type ViewMode =
  | { kind: 'browse' }
  | { kind: 'preview'; scenarioName: string }
  | { kind: 'investigating'; scenarioName: string }

export type InterruptType = 'clarification' | 'hypothesis_review' | 'followup'

export type Phase =
  | 'idle'
  | 'clarification'
  | 'context_enrichment'
  | 'hypothesis_generation'
  | 'hypothesis_review'
  | 'investigation'
  | 'synthesis'
  | 'followup'
  | 'stopped'
  | 'complete'

export interface StreamMessage {
  id: string
  node: string
  content: string
  role: 'ai' | 'human' | 'system'
  timestamp: number
  isStreaming?: boolean
  toolCall?: {
    name: string
    args: Record<string, unknown>
    result?: string
  }
}

export interface InterruptInfo {
  type: InterruptType
  next_node: string
  prompt: string
}

export interface ContextDetails {
  kb_chunks?: string[]
  change_signals?: string[]
  error_signals?: string[]
}

export interface InvestigationState {
  id: string | null
  scenarioName: string | null
  phase: Phase
  messages: StreamMessage[]
  hypotheses: Hypotheses | null
  contextDetails: ContextDetails | null
  interrupt: InterruptInfo | null
  report: string | null
  winnerHypothesis: number | null
  error: string | null
  toolCalls: ToolCallInfo[]
  workerConclusions: Record<string, string>
}

export interface ToolCallInfo {
  name: string
  args: Record<string, unknown>
  node: string
  timestamp: number
  result?: string
}

export type InvestigationAction =
  | { type: 'START'; id: string; scenarioName: string | null }
  | { type: 'PHASE'; phase: Phase }
  | { type: 'MESSAGE'; node: string; content: string; role: 'ai' | 'human' }
  | { type: 'HYPOTHESIS'; hypotheses: Hypotheses }
  | { type: 'CONTEXT_DETAILS'; details: ContextDetails }
  | { type: 'WORKER_UPDATE'; worker_id: string; content: string; conclusion?: string }
  | { type: 'INTERRUPT'; interrupt: InterruptInfo }
  | { type: 'TOKEN'; content: string; node: string }
  | { type: 'TOOL_CALL'; name: string; args: Record<string, unknown>; node: string }
  | { type: 'TOOL_RESULT'; name: string; content: string; node: string }
  | { type: 'RESPOND' }
  | { type: 'COMPLETE'; report: string; winnerHypothesis?: number }
  | { type: 'STOP' }
  | { type: 'ERROR'; message: string }
  | { type: 'RESET' }
