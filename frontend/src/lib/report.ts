import type { AnalysisResponse, ChecklistItem } from '../types'
import {
  categoryLabels,
  formatTimestamp,
  priorityLabels,
  priorityOrder,
  riskLabels,
  severityLabels,
  slugify,
} from './format'

function oneLine(value: string): string {
  return value.replace(/\s+/g, ' ').trim()
}

function codeBlock(value: string): string[] {
  return ['````text', value.replace(/````/g, '` ` ` `'), '````']
}

export interface ReportOptions {
  analysis: AnalysisResponse
  checklist: ChecklistItem[]
  aiExplanation?: string | null
}

export function buildReport({
  analysis,
  checklist,
  aiExplanation,
}: ReportOptions): string {
  const { summary } = analysis
  const lines: string[] = [
    `# CredPilot pre-flight report`,
    '',
    `**Project:** ${oneLine(analysis.project_name)}  `,
    `**Generated:** ${formatTimestamp(analysis.generated_at)}  `,
    `**Risk level:** ${riskLabels[summary.risk_level]} (heuristic score ${summary.score}/100)  `,
    `**Config fingerprint:** \`${analysis.fingerprint}\`  `,
    `**Rules:** ${analysis.engine.name} v${analysis.engine.version} / ${analysis.engine.rules_version}`,
    '',
    '> The score is an exposure heuristic, not a bill, balance, or savings estimate.',
    '',
    '## Summary',
    '',
    `- Files analyzed: ${summary.files_analyzed}`,
    `- Checks run: ${summary.checks_run}`,
    `- Findings: ${summary.findings_total}`,
    `- Formats: ${summary.formats.join(', ') || 'none'}`,
    `- Severity counts: ${Object.entries(summary.counts)
      .filter(([, count]) => count > 0)
      .map(([severity, count]) => `${severityLabels[severity as keyof typeof severityLabels] ?? severity} ${count}`)
      .join(', ') || 'none'}`,
    '',
  ]

  if (analysis.parse_notes.length > 0) {
    lines.push('## Files checked', '')
    for (const note of analysis.parse_notes) {
      const status = note.ok ? 'checked' : 'not fully checked'
      lines.push(
        `- \`${note.file}\` — ${note.format_label} (${status})${note.message ? `: ${oneLine(note.message)}` : ''}`,
      )
    }
    lines.push('')
  }

  lines.push('## Findings', '')
  if (analysis.findings.length === 0) {
    lines.push(
      'No rule-based findings were reported. This is not proof that the deployment is safe or free of charges.',
      '',
    )
  } else {
    analysis.findings.forEach((finding, index) => {
      const location = `${finding.evidence.file}${finding.evidence.line ? `:${finding.evidence.line}` : ''}`
      lines.push(
        `### ${index + 1}. [${severityLabels[finding.severity]}] ${oneLine(finding.title)}`,
        '',
        `- **Category:** ${categoryLabels[finding.category]}`,
        `- **Resource:** ${finding.resource ? oneLine(finding.resource) : 'not specified'}`,
        `- **Evidence:** \`${location}\``,
        `- **Rule:** \`${finding.rule_id}\``,
        '',
        oneLine(finding.message),
        '',
        `**Why it matters:** ${oneLine(finding.why)}`,
        '',
        `**Suggested fix:** ${oneLine(finding.remediation)}`,
        '',
      )
      if (finding.evidence.snippet) {
        lines.push('Evidence excerpt:', '', ...codeBlock(finding.evidence.snippet), '')
      }
      if (finding.docs_url) {
        lines.push(`**Reference:** ${finding.docs_url}`, '')
      }
    })
  }

  lines.push('## Cleanup checklist', '')
  if (checklist.length === 0) {
    lines.push('_No checklist items._', '')
  } else {
    for (const priority of priorityOrder) {
      const items = checklist.filter((item) => item.priority === priority)
      if (items.length === 0) continue
      lines.push(`### ${priorityLabels[priority]}`, '')
      for (const item of items) {
        lines.push(`- [${item.done ? 'x' : ' '}] ${oneLine(item.title)}`)
        if (item.detail) {
          lines.push(`  - ${oneLine(item.detail)}`)
        }
        if (item.evidence_file) {
          lines.push(
            `  - Evidence: \`${item.evidence_file}${item.evidence_line ? `:${item.evidence_line}` : ''}\``,
          )
        }
      }
      lines.push('')
    }
  }

  if (aiExplanation) {
    lines.push(
      '## Optional Gemma explanation (AI-generated)',
      '',
      '> Generated only from the deterministic findings above. It cannot add checks, verify prices, or change the results.',
      '',
      aiExplanation.trim(),
      '',
    )
  }

  lines.push('## Scope and limitations', '')
  for (const disclaimer of analysis.disclaimers) {
    lines.push(`- ${oneLine(disclaimer)}`)
  }
  lines.push(
    '',
    '---',
    '',
    'No cloud resources were created, paused, or deleted by CredPilot. Verify all billing and cleanup actions in the provider dashboard.',
    '',
  )

  return lines.join('\n')
}

export function reportFilename(analysis: AnalysisResponse): string {
  const date = new Date(analysis.generated_at)
  const stamp = Number.isNaN(date.getTime())
    ? new Date().toISOString().slice(0, 10)
    : date.toISOString().slice(0, 10)
  return `credpilot-${slugify(analysis.project_name)}-${stamp}.md`
}

export function downloadReport(content: string, filename: string): void {
  const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export async function copyText(value: string): Promise<void> {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(value)
    return
  }

  const textarea = document.createElement('textarea')
  textarea.value = value
  textarea.setAttribute('readonly', '')
  textarea.style.position = 'fixed'
  textarea.style.opacity = '0'
  document.body.appendChild(textarea)
  textarea.select()
  const copied = document.execCommand('copy')
  textarea.remove()
  if (!copied) throw new Error('Clipboard copy is not available in this browser.')
}
