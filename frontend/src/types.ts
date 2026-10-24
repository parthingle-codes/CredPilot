export type Severity = 'critical' | 'high' | 'medium' | 'low' | 'info'
export type Category = 'billing' | 'deployment' | 'security' | 'cleanup'
export type Priority = 'now' | 'before-demo' | 'after-demo'
export type RiskLevel = 'clear' | 'low' | 'elevated' | 'high' | 'critical'

export interface Evidence {
  file: string
  line: number | null
  snippet: string
}

export interface Finding {
  id: string
  rule_id: string
  title: string
  severity: Severity
  category: Category
  message: string
  why: string
  remediation: string
  evidence: Evidence
  docs_url: string | null
  resource: string | null
}

export interface CleanupTask {
  id: string
  title: string
  detail: string
  priority: Priority
  category: Category
  source_finding_id: string | null
  evidence_file: string | null
  evidence_line: number | null
}

export interface ParseNote {
  file: string
  format: string
  format_label: string
  ok: boolean
  message: string
}

export interface EngineInfo {
  name: string
  version: string
  rules_version: string
}

export interface Summary {
  score: number
  risk_level: RiskLevel
  counts: Record<Severity, number>
  findings_total: number
  checks_run: number
  files_analyzed: number
  formats: string[]
}

export interface AnalysisResponse {
  project_name: string
  generated_at: string
  fingerprint: string
  engine: EngineInfo
  summary: Summary
  findings: Finding[]
  cleanup_tasks: CleanupTask[]
  parse_notes: ParseNote[]
  disclaimers: string[]
}

export interface HealthResponse {
  status: 'ok'
  version: string
  rules_version: string
  ai_configured: boolean
  gemma_model: string
}

export interface ExplainResponse {
  available: boolean
  model: string
  explanation: string | null
  reason: string | null
  generated_at: string
  guardrail: string
}

export interface FilePayload {
  path: string
  content: string
}

export interface ConfigFileState extends FilePayload {
  id: string
}

export interface DemoFile {
  path: string
  content: string
}

export interface Demo {
  id: string
  name: string
  tagline: string
  projectName: string
  files: DemoFile[]
}

export interface ChecklistItem extends CleanupTask {
  done: boolean
}

export interface AiState {
  status: 'idle' | 'loading' | 'done'
  available: boolean
  explanation: string | null
  reason: string | null
  model: string | null
  guardrail: string | null
}
