import type { HealthResponse } from '../types'
import { BrandMark, Icon } from './Icons'

interface HeaderProps {
  healthStatus: 'checking' | 'online' | 'offline'
  health: HealthResponse | null
  onRetry: () => void
}

export function Header({ healthStatus, health, onRetry }: HeaderProps) {
  const apiOnline = healthStatus === 'online'
  const aiReady = apiOnline && health?.ai_configured === true

  return (
    <header className="site-header">
      <div className="header-inner">
        <a className="brand" href="#top" aria-label="CredPilot home">
          <BrandMark />
          <span className="brand-copy">
            <span className="brand-name">CredPilot</span>
            <span className="brand-sub">deployment pre-flight</span>
          </span>
        </a>

        <nav className="header-nav" aria-label="Primary">
          <a href="#analyzer">Analyzer</a>
          <a href="#scope">Scope</a>
          <a href="#how-it-works">How it works</a>
        </nav>

        <div className="header-status" aria-live="polite">
          <span
            className={`status-pill status-${healthStatus}`}
            title={
              healthStatus === 'offline'
                ? 'The API is unreachable. Click to retry.'
                : healthStatus === 'online'
                  ? `Rules v${health?.rules_version ?? ''} online`
                  : 'Checking the API'
            }
          >
            <span className="status-dot" aria-hidden="true" />
            {healthStatus === 'checking'
              ? 'Checking API'
              : healthStatus === 'offline'
                ? 'API offline'
                : 'Rules online'}
          </span>
          <span
            className={`status-pill ${aiReady ? 'status-ai' : 'status-muted'}`}
            title={
              aiReady
                ? `Gemma explanations enabled (${health?.gemma_model})`
                : 'Gemma is optional. Deterministic checks work without it.'
            }
          >
            <Icon name="sparkles" size={13} />
            {aiReady ? 'Gemma ready' : 'Gemma optional'}
          </span>
          {healthStatus === 'offline' && (
            <button
              type="button"
              className="icon-button"
              onClick={onRetry}
              title="Retry API connection"
              aria-label="Retry API connection"
            >
              <Icon name="refresh" size={16} />
            </button>
          )}
        </div>
      </div>
    </header>
  )
}
