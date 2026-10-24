import { Icon } from './Icons'

const steps = [
  {
    number: '01',
    icon: 'terminal' as const,
    title: 'Parse the text',
    copy: 'Line-aware parsers read Render Blueprints, Compose files, and dotenv syntax. Unsupported or broken files are reported instead of silently skipped.',
  },
  {
    number: '02',
    icon: 'shield' as const,
    title: 'Match deterministic rules',
    copy: 'Versioned rules flag paid plans, public database ports, secret-shaped values, free-tier expiry, host bindings, and cleanup hazards. The same input gives the same result.',
  },
  {
    number: '03',
    icon: 'broom' as const,
    title: 'Clear the checklist',
    copy: 'Every finding cites file and line evidence. Fix what matters, edit the cleanup list, and export a Markdown report before the demo.',
  },
]

export function HowItWorks() {
  return (
    <section className="how-section" id="how-it-works">
      <div className="section-heading">
        <p className="eyebrow">
          <Icon name="radar" size={14} /> Method
        </p>
        <h2>Rules first. AI last. Always evidence.</h2>
        <p>
          CredPilot is a static analyzer, not a cloud scanner. The optional Gemma layer only
          narrates findings the rules already produced.
        </p>
      </div>

      <div className="how-grid">
        {steps.map((step) => (
          <article key={step.number} className="how-card">
            <div className="how-card-top">
              <span className="how-icon">
                <Icon name={step.icon} size={20} />
              </span>
              <span className="how-number">{step.number}</span>
            </div>
            <h3>{step.title}</h3>
            <p>{step.copy}</p>
          </article>
        ))}
      </div>

      <div className="how-strip">
        <span>
          <Icon name="lock" size={14} /> No account connection
        </span>
        <span>
          <Icon name="wallet" size={14} /> No invented prices
        </span>
        <span>
          <Icon name="server" size={14} /> No resource changes
        </span>
        <span>
          <Icon name="code" size={14} /> No database or auth
        </span>
      </div>
    </section>
  )
}
