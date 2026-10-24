import type { AiState, AnalysisResponse } from '../types'
import { Icon } from './Icons'

interface AiExplainerProps {
  analysis: AnalysisResponse
  ai: AiState
  aiConfigured: boolean | null
  onExplain: () => void
}

export function AiExplainer({
  analysis,
  ai,
  aiConfigured,
  onExplain,
}: AiExplainerProps) {
  const loading = ai.status === 'loading'
  const disabled = aiConfigured === false || loading

  return (
    <div className="ai-panel">
      <div className="ai-head">
        <span className="ai-mark">
          <Icon name="sparkles" size={18} />
        </span>
        <div>
          <h3>Optional Gemma explanation</h3>
          <p>
            A plain-language read of the findings above. Generated only from redacted finding
            metadata — never your file contents, env values, or evidence snippets.
          </p>
        </div>
        <span className="ai-badge">AI · optional</span>
      </div>

      <div className="ai-guardrails">
        <span>
          <Icon name="lock" size={13} /> No raw config sent
        </span>
        <span>
          <Icon name="gauge" size={13} /> Cannot add checks or prices
        </span>
        <span>
          <Icon name="shield" size={13} /> Deterministic results stay authoritative
        </span>
      </div>

      {aiConfigured === false && (
        <p className="ai-notice">
          <Icon name="alert" size={14} />
          Gemma is not configured on this server. Add <code>HF_TOKEN</code> to enable
          explanations; every deterministic check works without it.
        </p>
      )}

      <div className="ai-actions">
        <button
          type="button"
          className="btn btn-ai"
          onClick={onExplain}
          disabled={disabled}
        >
          {loading ? (
            <>
              <span className="spinner" aria-hidden="true" /> Asking Gemma…
            </>
          ) : (
            <>
              <Icon name="sparkles" size={16} />
              {ai.status === 'done' ? 'Regenerate explanation' : 'Explain these findings'}
            </>
          )}
        </button>
        <span className="ai-model">
          {ai.model ?? 'google/gemma via Hugging Face'} · {analysis.findings.length}{' '}
          {analysis.findings.length === 1 ? 'finding' : 'findings'} in context
        </span>
      </div>

      {loading && (
        <div className="ai-loading" aria-live="polite">
          <span />
          <span />
          <span />
          <span />
        </div>
      )}

      {!loading && ai.status === 'done' && ai.available && ai.explanation && (
        <div className="ai-result" aria-live="polite">
          <div className="ai-result-head">
            <span className="ai-result-tag">
              <Icon name="sparkles" size={12} /> AI-generated
            </span>
            <span>May be imperfect. Not a verified fact.</span>
          </div>
          <div className="ai-text">{ai.explanation}</div>
          {ai.guardrail && <p className="ai-guardrail-note">{ai.guardrail}</p>}
        </div>
      )}

      {!loading && ai.status === 'done' && !ai.available && (
        <div className="ai-unavailable" aria-live="polite">
          <Icon name="alert" size={16} />
          <div>
            <strong>Explanation unavailable</strong>
            <p>{ai.reason ?? 'The optional AI explanation could not be generated.'}</p>
            <p className="ai-unavailable-foot">
              The deterministic findings and checklist are unaffected.
            </p>
          </div>
        </div>
      )}

      <p className="ai-footnote">
        AI output is never parsed back into findings and price or savings claims are withheld.
        If the model is unavailable, this tab degrades gracefully.
      </p>
    </div>
  )
}
