import type { CSSProperties } from 'react'
import type { AnalysisResponse, ParseNote } from '../types'
import { riskCopy, riskLabels } from '../lib/format'
import { Icon } from './Icons'

interface ParseNotesProps {
  notes: ParseNote[]
}

export function ParseNotes({ notes }: ParseNotesProps) {
  const issues = notes.filter((note) => !note.ok).length

  return (
    <details className="parse-notes" open={issues > 0}>
      <summary>
        <span className="parse-summary-left">
          <Icon name="file" size={14} />
          Files checked
          <span className="parse-count">{notes.length}</span>
        </span>
        <span className={issues > 0 ? 'parse-issue' : 'parse-ok'}>
          {issues > 0 ? `${issues} not fully checked` : 'all parsed'}
          <Icon name="chevron-down" size={14} className="details-chevron" />
        </span>
      </summary>
      <ul className="parse-list">
        {notes.map((note) => (
          <li key={note.file}>
            <span className={`parse-status ${note.ok ? 'is-ok' : 'is-warn'}`}>
              <Icon name={note.ok ? 'check' : 'alert'} size={12} />
            </span>
            <span className="parse-file">{note.file}</span>
            <span className="parse-format">{note.format_label}</span>
            {note.message && <span className="parse-message">{note.message}</span>}
          </li>
        ))}
      </ul>
    </details>
  )
}

interface SummaryPanelProps {
  analysis: AnalysisResponse
}

const riskColors: Record<string, string> = {
  clear: '#4ade80',
  low: '#5eead4',
  elevated: '#f5b642',
  high: '#ff9f43',
  critical: '#ff5d6c',
}

export function SummaryPanel({ analysis }: SummaryPanelProps) {
  const { summary } = analysis
  const copy = riskCopy[summary.risk_level]
  const color = riskColors[summary.risk_level] ?? '#f5b642'

  return (
    <section className="panel summary-panel" aria-labelledby="summary-heading">
      <div className="summary-top">
        <div
          className="score-ring"
          style={
            {
              '--score': summary.score,
              '--score-color': color,
            } as CSSProperties
          }
          role="img"
          aria-label={`Exposure score ${summary.score} out of 100, ${riskLabels[summary.risk_level]}`}
        >
          <div className="score-inner">
            <span className="score-value">{summary.score}</span>
            <span className="score-denom">/ 100</span>
          </div>
        </div>

        <div className="summary-copy">
          <div className="summary-heading-row">
            <h2 id="summary-heading">
              <span className={`risk-dot risk-${summary.risk_level}`} aria-hidden="true" />
              {riskLabels[summary.risk_level]} exposure
            </h2>
            <span className={`risk-badge risk-${summary.risk_level}`}>
              {summary.findings_total}{' '}
              {summary.findings_total === 1 ? 'finding' : 'findings'}
            </span>
          </div>
          <p className="summary-headline">{copy.headline}</p>
          <p className="summary-subline">{copy.subline}</p>

          <div className="severity-chips" aria-label="Findings by severity">
            {(['critical', 'high', 'medium', 'low', 'info'] as const).map((severity) =>
              summary.counts[severity] > 0 ? (
                <span key={severity} className={`severity-chip sev-${severity}`}>
                  {severity} <b>{summary.counts[severity]}</b>
                </span>
              ) : null,
            )}
            {summary.findings_total === 0 && (
              <span className="severity-chip sev-clear">no findings</span>
            )}
          </div>
        </div>
      </div>

      <dl className="summary-stats">
        <div>
          <dt>Files</dt>
          <dd>{summary.files_analyzed}</dd>
        </div>
        <div>
          <dt>Checks run</dt>
          <dd>{summary.checks_run}</dd>
        </div>
        <div>
          <dt>Formats</dt>
          <dd className="stat-formats">{summary.formats.join(' · ') || 'none'}</dd>
        </div>
        <div>
          <dt>Rules</dt>
          <dd>{analysis.engine.rules_version}</dd>
        </div>
      </dl>

      <ParseNotes notes={analysis.parse_notes} />

      <p className="score-disclaimer">
        <Icon name="gauge" size={14} />
        Exposure heuristic only — not a bill, balance, usage reading, or savings estimate.
      </p>
    </section>
  )
}
