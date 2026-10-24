import { useMemo, useState } from 'react'
import type { Category, Finding, Severity } from '../types'
import {
  categoryLabels,
  categoryOrder,
  severityLabels,
  severityOrder,
} from '../lib/format'
import { Icon, type IconName } from './Icons'

interface FindingsPanelProps {
  findings: Finding[]
}

const categoryIcons: Record<Category, IconName> = {
  billing: 'wallet',
  deployment: 'server',
  security: 'shield',
  cleanup: 'broom',
}

type SeverityFilter = Severity | 'all'
type CategoryFilter = Category | 'all'

export function FindingsPanel({ findings }: FindingsPanelProps) {
  const [severity, setSeverity] = useState<SeverityFilter>('all')
  const [category, setCategory] = useState<CategoryFilter>('all')
  const [query, setQuery] = useState('')
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set())

  const counts = useMemo(() => {
    const next: Record<Severity, number> = {
      critical: 0,
      high: 0,
      medium: 0,
      low: 0,
      info: 0,
    }
    for (const finding of findings) next[finding.severity] += 1
    return next
  }, [findings])

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return findings.filter((finding) => {
      if (severity !== 'all' && finding.severity !== severity) return false
      if (category !== 'all' && finding.category !== category) return false
      if (!needle) return true
      return [
        finding.title,
        finding.message,
        finding.why,
        finding.remediation,
        finding.rule_id,
        finding.resource ?? '',
        finding.evidence.file,
      ]
        .join(' ')
        .toLowerCase()
        .includes(needle)
    })
  }, [findings, severity, category, query])

  function toggle(id: string) {
    setExpanded((current) => {
      const next = new Set(current)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  function expandAll() {
    setExpanded(new Set(visible.map((finding) => finding.id)))
  }

  if (findings.length === 0) {
    return (
      <div className="tab-empty">
        <span className="tab-empty-icon tab-empty-ok">
          <Icon name="check" size={22} />
        </span>
        <h3>No rule-based findings</h3>
        <p>
          Nothing in the submitted text matched the current rule set. This is not proof that
          the deployment is safe, free, or correctly configured — confirm provider limits and
          billing manually.
        </p>
      </div>
    )
  }

  return (
    <div className="findings-panel">
      <div className="filter-bar">
        <div className="filter-row" role="group" aria-label="Filter by severity">
          <button
            type="button"
            className={`filter-chip ${severity === 'all' ? 'is-active' : ''}`}
            onClick={() => setSeverity('all')}
          >
            All <b>{findings.length}</b>
          </button>
          {severityOrder.map((level) =>
            counts[level] > 0 ? (
              <button
                key={level}
                type="button"
                className={`filter-chip sev-${level} ${severity === level ? 'is-active' : ''}`}
                onClick={() => setSeverity(level)}
              >
                {severityLabels[level]} <b>{counts[level]}</b>
              </button>
            ) : null,
          )}
        </div>

        <div className="filter-row filter-row-secondary">
          <label className="search-field">
            <Icon name="radar" size={14} />
            <span className="sr-only">Search findings</span>
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search findings…"
            />
          </label>
          <select
            className="select-input"
            value={category}
            onChange={(event) => setCategory(event.target.value as CategoryFilter)}
            aria-label="Filter by category"
          >
            <option value="all">All categories</option>
            {categoryOrder.map((item) => (
              <option key={item} value={item}>
                {categoryLabels[item]}
              </option>
            ))}
          </select>
          <button type="button" className="chip-button" onClick={expandAll}>
            Expand all
          </button>
        </div>
      </div>

      <div className="findings-list">
        {visible.length === 0 && (
          <p className="filter-empty">No findings match those filters.</p>
        )}
        {visible.map((finding) => {
          const open = expanded.has(finding.id)
          const location = `${finding.evidence.file}${
            finding.evidence.line ? `:${finding.evidence.line}` : ''
          }`
          return (
            <article
              key={finding.id}
              className={`finding sev-${finding.severity} ${open ? 'is-open' : ''}`}
            >
              <button
                type="button"
                className="finding-head"
                onClick={() => toggle(finding.id)}
                aria-expanded={open}
                aria-controls={`finding-body-${finding.id}`}
              >
                <span className={`severity-badge sev-${finding.severity}`}>
                  {severityLabels[finding.severity]}
                </span>
                <span className="finding-headtext">
                  <span className="finding-title">{finding.title}</span>
                  <span className="finding-meta">
                    <span>
                      <Icon name={categoryIcons[finding.category]} size={12} />
                      {categoryLabels[finding.category]}
                    </span>
                    {finding.resource && <span>{finding.resource}</span>}
                    <code>{location}</code>
                  </span>
                </span>
                <Icon
                  name="chevron-down"
                  size={16}
                  className={`finding-chevron ${open ? 'is-open' : ''}`}
                />
              </button>

              {open && (
                <div className="finding-body" id={`finding-body-${finding.id}`}>
                  <p className="finding-message">{finding.message}</p>

                  <div className="finding-fact">
                    <span className="fact-label">Why it matters</span>
                    <p>{finding.why}</p>
                  </div>
                  <div className="finding-fact">
                    <span className="fact-label">Suggested fix</span>
                    <p>{finding.remediation}</p>
                  </div>

                  {finding.evidence.snippet && (
                    <div className="evidence-block">
                      <span className="fact-label">Redacted evidence · {location}</span>
                      <pre>
                        <code>{finding.evidence.snippet}</code>
                      </pre>
                    </div>
                  )}

                  <div className="finding-foot">
                    <span className="rule-id">rule · {finding.rule_id}</span>
                    {finding.docs_url && (
                      <a
                        className="text-link"
                        href={finding.docs_url}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Reference <Icon name="external" size={12} />
                      </a>
                    )}
                  </div>
                </div>
              )}
            </article>
          )
        })}
      </div>
    </div>
  )
}
