import { Icon } from './Icons'

interface EmptyResultsProps {
  canRun: boolean
  onRun: () => void
}

const checks = [
  { icon: 'wallet' as const, label: 'Billing traps', copy: 'Paid plans, disks, previews, and metered services.' },
  { icon: 'shield' as const, label: 'Secret exposure', copy: 'Token-shaped values and credentials embedded in config.' },
  { icon: 'server' as const, label: 'Deployment limits', copy: 'Spin-down, expiry, health checks, and host bindings.' },
  { icon: 'broom' as const, label: 'Cleanup debt', copy: 'What to pause, delete, rotate, and verify after judging.' },
]

export function EmptyResults({ canRun, onRun }: EmptyResultsProps) {
  return (
    <div className="panel empty-results">
      <div className="radar-visual" aria-hidden="true">
        <span className="radar-ring radar-ring-1" />
        <span className="radar-ring radar-ring-2" />
        <span className="radar-ring radar-ring-3" />
        <span className="radar-sweep" />
        <span className="radar-blip radar-blip-1" />
        <span className="radar-blip radar-blip-2" />
        <Icon name="radar" size={34} />
      </div>

      <p className="panel-kicker">
        <span className="step-number">02</span> Pre-flight results
      </p>
      <h2>Awaiting a scan</h2>
      <p className="empty-lede">
        Load a synthetic demo or paste your own supported config. CredPilot checks the text
        against deterministic rules — no cloud account, no deployment, no live prices.
      </p>

      <ul className="empty-checks">
        {checks.map((check) => (
          <li key={check.label}>
            <span className="empty-check-icon">
              <Icon name={check.icon} size={16} />
            </span>
            <span>
              <strong>{check.label}</strong>
              <em>{check.copy}</em>
            </span>
          </li>
        ))}
      </ul>

      <button
        type="button"
        className="btn btn-primary"
        onClick={onRun}
        disabled={!canRun}
      >
        <Icon name="radar" size={17} /> Run the first pre-flight
      </button>

      <p className="empty-note">
        The risk score is an exposure heuristic, <strong>not a bill estimate</strong>. Findings
        cite exact <code>file:line</code> evidence so you can verify each one.
      </p>
    </div>
  )
}
