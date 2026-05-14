export interface ClarificationNeeded {
  kind: 'clarification'
  needs_clarification: boolean
  questions: string[]
}

export interface AssessmentSummary {
  requirement: string
  change_type: string
  risk_level: string
  overall_confidence: string
  needs_human_review: boolean
  conclusion: string
  stop_reason?: string | null
  source_snapshot: Record<string, unknown>
  assessment_id?: string | null
  created_at?: string | null
}

export interface MatchItem {
  evidence_id?: string
  file_path?: string
  relative_path?: string
  line_no?: number
  reason?: string
  confidence?: string
  code?: string
  clue_category?: string
  status?: string
  [key: string]: unknown
}

export interface TraceItem {
  node?: string
  action?: string
  reasoning?: string | null
  next_keywords?: string[]
  [key: string]: unknown
}

export interface AssessmentReport {
  kind?: 'report'
  summary: AssessmentSummary
  confirmed_affected: MatchItem[]
  uncertain_matches: MatchItem[]
  excluded_matches: MatchItem[]
  coverage: Record<string, unknown>
  evidence_chain: {
    items: MatchItem[]
    count: number
  }
  knowledge_used: Record<string, unknown>
  next_action?: string | null
  trace: TraceItem[]
}

export interface AssessmentHistoryItem {
  assessment_id: string
  created_at: string
  requirement: string
  change_type: string
  risk_level: string
  overall_confidence: string
  needs_human_review: boolean
  conclusion: string
  project_root?: string | null
  repo_path?: string | null
  module?: string | null
}

export interface AssessmentRecord {
  assessment_id: string
  created_at: string
  request: Record<string, unknown>
  history_item: AssessmentHistoryItem
  report: AssessmentReport
}

export interface AssessmentSubmitInput {
  requirement: string
}

export type AssessmentSubmitResult = ClarificationNeeded | AssessmentReport
