import { BrandMark, Icon } from './Icons'

const limits = [
  'Not a cost estimator. It never reads balances, usage, or current prices.',
  'Not an account scanner. It only sees the files you paste.',
  'Not an auto-cleanup tool. It cannot pause, delete, or rotate anything.',
  'Not a security audit. Findings are deterministic heuristics, not proof.',
]

const formats = ['render.yaml', 'docker-compose.yml / compose.yaml', '.env / dotenv']

export function Footer() {
  return (
    <footer className="site-footer">
      <div className="footer-grid">
        <div className="footer-brand">
          <a className="brand" href="#top" aria-label="Back to top">
            <BrandMark size={34} />
            <span className="brand-copy">
              <span className="brand-name">CredPilot</span>
              <span className="brand-sub">deployment pre-flight</span>
            </span>
          </a>
          <p>
            A small, honest safety check for student teams shipping under deadline. Built to
            be read, edited, and argued with.
          </p>
          <span className="footer-version">v0.1.0 · rules 2026.10.1</span>
        </div>

        <div className="footer-column">
          <h3>Supported inputs</h3>
          <ul>
            {formats.map((format) => (
              <li key={format}>
                <code>{format}</code>
              </li>
            ))}
          </ul>
          <p className="footer-small">More formats are deliberately out of scope for v1.</p>
        </div>

        <div className="footer-column">
          <h3>Hard limits</h3>
          <ul className="footer-limits">
            {limits.map((limit) => (
              <li key={limit}>
                <Icon name="x" size={12} /> {limit}
              </li>
            ))}
          </ul>
        </div>

        <div className="footer-column">
          <h3>References</h3>
          <ul className="footer-links">
            <li>
              <a href="https://render.com/docs/free" target="_blank" rel="noreferrer">
                Render free tier <Icon name="external" size={11} />
              </a>
            </li>
            <li>
              <a
                href="https://render.com/docs/blueprint-spec"
                target="_blank"
                rel="noreferrer"
              >
                Blueprint spec <Icon name="external" size={11} />
              </a>
            </li>
            <li>
              <a
                href="https://docs.docker.com/reference/compose-file/"
                target="_blank"
                rel="noreferrer"
              >
                Compose file reference <Icon name="external" size={11} />
              </a>
            </li>
            <li>
              <a
                href="https://huggingface.co/docs/inference-providers"
                target="_blank"
                rel="noreferrer"
              >
                HF Inference Providers <Icon name="external" size={11} />
              </a>
            </li>
          </ul>
        </div>
      </div>

      <div className="footer-bottom">
        <p>
          <Icon name="shield" size={13} /> Findings are not guarantees. Verify billing and
          cleanup in each provider dashboard.
        </p>
        <p className="footer-scope">
          Configuration text is analyzed in memory. The optional AI receives finding metadata
          only.
        </p>
      </div>
    </footer>
  )
}
