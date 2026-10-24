import { useMemo, useState } from 'react'
import type { AnalysisResponse, ChecklistItem } from '../types'
import { formatTimestamp } from '../lib/format'
import {
  buildReport,
  copyText,
  downloadReport,
  reportFilename,
} from '../lib/report'
import { Icon } from './Icons'

interface ReportPanelProps {
  analysis: AnalysisResponse
  checklist: ChecklistItem[]
  aiExplanation: string | null
}

type CopyState = 'idle' | 'copied' | 'error'

export function ReportPanel({
  analysis,
  checklist,
  aiExplanation,
}: ReportPanelProps) {
  const [copyState, setCopyState] = useState<CopyState>('idle')
  const report = useMemo(
    () => buildReport({ analysis, checklist, aiExplanation }),
    [analysis, checklist, aiExplanation],
  )

  async function handleCopy() {
    try {
      await copyText(report)
      setCopyState('copied')
      window.setTimeout(() => setCopyState('idle'), 2400)
    } catch {
      setCopyState('error')
    }
  }

  return (
    <div className="report-panel">
      <div className="report-intro">
        <span className="report-icon">
          <Icon name="download" size={20} />
        </span>
        <div>
          <h3>Portable pre-flight report</h3>
          <p>
            A Markdown file you can paste into a README, PR, issue, or judging submission.
            It includes the score disclaimer, every finding with evidence, your checklist
            state, and the scope limits.
          </p>
        </div>
      </div>

      <ul className="report-includes">
        <li>
          <Icon name="check" size={13} /> Project, fingerprint, rules version
        </li>
        <li>
          <Icon name="check" size={13} /> Findings with <code>file:line</code> evidence
        </li>
        <li>
          <Icon name="check" size={13} /> Cleanup checklist with done state
        </li>
        <li>
          <Icon name="check" size={13} /> AI disclosure when an explanation is included
        </li>
      </ul>

      <div className="report-actions">
        <button type="button" className="btn btn-primary" onClick={handleCopy}>
          <Icon name={copyState === 'copied' ? 'check' : 'copy'} size={16} />
          {copyState === 'copied'
            ? 'Copied to clipboard'
            : copyState === 'error'
              ? 'Copy failed — try download'
              : 'Copy Markdown'}
        </button>
        <button
          type="button"
          className="btn btn-ghost"
          onClick={() => downloadReport(report, reportFilename(analysis))}
        >
          <Icon name="download" size={16} /> Download .md
        </button>
      </div>

      <dl className="report-meta">
        <div>
          <dt>Fingerprint</dt>
          <dd>
            <code>{analysis.fingerprint}</code>
          </dd>
        </div>
        <div>
          <dt>Generated</dt>
          <dd>{formatTimestamp(analysis.generated_at)}</dd>
        </div>
        <div>
          <dt>Rules</dt>
          <dd>
            {analysis.engine.name} / {analysis.engine.rules_version}
          </dd>
        </div>
      </dl>

      <details className="report-preview">
        <summary>
          <span>
            <Icon name="code" size={14} /> Preview Markdown
          </span>
          <Icon name="chevron-down" size={14} className="details-chevron" />
        </summary>
        <pre>
          <code>{report}</code>
        </pre>
      </details>

      <p className="report-footnote">
        <Icon name="shield" size={14} />
        Credentials are redacted before export. No report is uploaded or stored by CredPilot.
      </p>
    </div>
  )
}
