import { useState } from 'react'
import type { AiState, AnalysisResponse } from '../types'
import type { ChecklistActions } from '../hooks/useChecklist'
import { EmptyResults } from './EmptyResults'
import { SummaryPanel } from './SummaryPanel'
import { FindingsPanel } from './FindingsPanel'
import { Checklist } from './Checklist'
import { AiExplainer } from './AiExplainer'
import { ReportPanel } from './ReportPanel'
import { Icon, type IconName } from './Icons'

type ResultTab = 'findings' | 'cleanup' | 'explain' | 'report'

interface ResultsPanelProps {
  analysis: AnalysisResponse | null
  analyzing: boolean
  error: string | null
  stale: boolean
  canRun: boolean
  checklist: ChecklistActions
  ai: AiState
  aiConfigured: boolean | null
  onRun: () => void
  onExplain: () => void
}

const tabs: Array<{ id: ResultTab; label: string; icon: IconName }> = [
  { id: 'findings', label: 'Findings', icon: 'alert' },
  { id: 'cleanup', label: 'Cleanup', icon: 'broom' },
  { id: 'explain', label: 'Explain', icon: 'sparkles' },
  { id: 'report', label: 'Report', icon: 'download' },
]

export function ResultsPanel({
  analysis,
  analyzing,
  error,
  stale,
  canRun,
  checklist,
  ai,
  aiConfigured,
  onRun,
  onExplain,
}: ResultsPanelProps) {
  const [tab, setTab] = useState<ResultTab>('findings')

  if (!analysis && !analyzing && !error) {
    return <EmptyResults canRun={canRun} onRun={onRun} />
  }

  if (!analysis) {
    return (
      <section className="panel results-panel" id="results" aria-busy={analyzing}>
        <div className="panel-head">
          <div>
            <p className="panel-kicker">
              <span className="step-number">02</span> Pre-flight results
            </p>
            <h2>{analyzing ? 'Running deterministic checks' : 'Scan could not run'}</h2>
          </div>
        </div>

        {analyzing ? (
          <div className="loading-panel" aria-live="polite">
            <div className="loading-radar">
              <span className="radar-sweep" />
              <Icon name="radar" size={30} />
            </div>
            <p>Parsing files and matching rules. No AI is involved in this step.</p>
            <div className="skeleton-stack" aria-hidden="true">
              <span />
              <span />
              <span />
            </div>
          </div>
        ) : (
          <div className="error-panel" role="alert">
            <span className="error-icon">
              <Icon name="alert" size={20} />
            </span>
            <div>
              <h3>The pre-flight did not complete</h3>
              <p>{error}</p>
              <button type="button" className="btn btn-primary btn-small" onClick={onRun}>
                <Icon name="refresh" size={15} /> Try again
              </button>
            </div>
          </div>
        )}
      </section>
    )
  }

  const tabCounts: Record<ResultTab, string | null> = {
    findings: String(analysis.summary.findings_total),
    cleanup: `${checklist.done}/${checklist.total}`,
    explain: ai.available ? 'on' : null,
    report: null,
  }

  return (
    <section className="panel results-panel" id="results" aria-busy={analyzing}>
      <div className="panel-head">
        <div>
          <p className="panel-kicker">
            <span className="step-number">02</span> Pre-flight results
          </p>
          <h2>What needs attention</h2>
        </div>
        <span className="panel-badge panel-badge-mono">
          {analyzing ? (
            <>
              <span className="spinner" aria-hidden="true" /> re-running
            </>
          ) : (
            <>#{analysis.fingerprint.slice(0, 8)}</>
          )}
        </span>
      </div>

      {error && (
        <div className="inline-error" role="alert">
          <Icon name="alert" size={16} />
          <span>{error}</span>
        </div>
      )}

      {stale && !analyzing && (
        <div className="stale-banner">
          <Icon name="clock" size={15} />
          <span>Configuration changed since this result.</span>
          <button type="button" className="btn btn-ghost btn-small" onClick={onRun}>
            Re-run
          </button>
        </div>
      )}

      <SummaryPanel analysis={analysis} />

      <div className="result-tabs" role="tablist" aria-label="Result sections">
        {tabs.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            id={`tab-${item.id}`}
            aria-selected={tab === item.id}
            aria-controls="results-tabpanel"
            className={`result-tab ${tab === item.id ? 'is-active' : ''}`}
            onClick={() => setTab(item.id)}
          >
            <Icon name={item.icon} size={15} />
            {item.label}
            {tabCounts[item.id] && (
              <span className="tab-count">{tabCounts[item.id]}</span>
            )}
          </button>
        ))}
      </div>

      <div
        className="tab-body"
        role="tabpanel"
        id="results-tabpanel"
        aria-labelledby={`tab-${tab}`}
      >
        {tab === 'findings' && <FindingsPanel findings={analysis.findings} />}
        {tab === 'cleanup' && (
          <Checklist checklist={checklist} fingerprint={analysis.fingerprint} />
        )}
        {tab === 'explain' && (
          <AiExplainer
            analysis={analysis}
            ai={ai}
            aiConfigured={aiConfigured}
            onExplain={onExplain}
          />
        )}
        {tab === 'report' && (
          <ReportPanel
            analysis={analysis}
            checklist={checklist.items}
            aiExplanation={ai.available ? ai.explanation : null}
          />
        )}
      </div>
    </section>
  )
}
