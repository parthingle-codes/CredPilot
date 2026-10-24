import { Icon } from './Icons'

export function Hero() {
  return (
    <section className="hero" id="top">
      <div className="hero-copy">
        <p className="eyebrow">
          <Icon name="radar" size={14} />
          Deployment safety · pre-flight 01
        </p>
        <h1>
          Clear the <span className="hero-highlight">runway</span>
          <br />
          before your demo.
        </h1>
        <p className="hero-sub">
          CredPilot reads your Render, Docker Compose, and <code>.env</code>{' '}
          configuration for billing traps, deployment limits, and cleanup you will
          forget — without touching your cloud account.
        </p>
        <div className="trust-row">
          <span className="trust-chip">
            <Icon name="lock" size={14} /> No account access
          </span>
          <span className="trust-chip">
            <Icon name="gauge" size={14} /> Rules first, always
          </span>
          <span className="trust-chip">
            <Icon name="sparkles" size={14} /> Gemma only explains
          </span>
        </div>
      </div>

      <aside className="scope-card" id="scope" aria-label="Scan boundary">
        <div className="scope-head">
          <span className="scope-kicker">
            <Icon name="shield" size={14} /> Scan boundary
          </span>
          <span className="scope-tag">read-only</span>
        </div>
        <div className="scope-grid">
          <div className="scope-item scope-inspects">
            <span className="scope-label">Inspects</span>
            <p>
              Config text, plan IDs, ports, env key patterns, secret-shaped values,
              and cleanup hazards.
            </p>
          </div>
          <div className="scope-item scope-cannot">
            <span className="scope-label">Cannot see</span>
            <p>
              Balances, live usage, quotas, current prices, or resources outside the
              submitted files.
            </p>
          </div>
        </div>
        <p className="scope-note">
          <Icon name="terminal" size={14} /> Findings cite <code>file:line</code>{' '}
          evidence. Nothing is deployed, changed, or deleted.
        </p>
      </aside>
    </section>
  )
}
