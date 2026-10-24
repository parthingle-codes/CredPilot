"""Prompt construction for the optional Gemma explanation.

The prompt contains finding summaries only. It never receives raw configuration,
environment values, evidence snippets, or credentials.
"""

from __future__ import annotations

from ..models import AnalysisResponse
from ..security import redact_text

MAX_FINDINGS_IN_PROMPT = 14

SYSTEM_PROMPT = """\
You are the optional explanation layer in CredPilot, a deployment-safety tool for
student hackathon teams. A deterministic rule engine has already produced the
findings you receive. You are not a second scanner.

Hard rules:
1. Use only the supplied findings. Do not add new checks, resources, or facts.
2. Never state or estimate prices, costs, dollar amounts, credits, balances, free
   quotas, or savings. If you mention billing, say the team must verify current
   terms in the provider dashboard.
3. Never describe a configuration as safe, secure, risk-free, or guaranteed.
4. Never ask for, infer, guess, or repeat credentials or secret values.
5. Explain the highest-impact issues and the order to handle them. Recommend
   manual verification where a fact is outside the findings.
6. Plain text only, no Markdown tables. At most 150 words in three short paragraphs.
7. Do not repeat every finding. Prioritize the ones that could block the demo or
   leave something running after it.
"""


def _clean(value: object, limit: int = 320) -> str:
    text = redact_text(value, max_length=limit)
    return " ".join(text.split())


def build_user_prompt(analysis: AnalysisResponse) -> str:
    lines: list[str] = [
        f"PROJECT: {_clean(analysis.project_name, 80)}",
        (
            f"RULE SUMMARY: risk={analysis.summary.risk_level}, "
            f"heuristic score={analysis.summary.score}/100 (not a cost estimate), "
            f"{analysis.summary.findings_total} finding(s), "
            f"{analysis.summary.checks_run} checks run across "
            f"{analysis.summary.files_analyzed} file(s)."
        ),
        "COUNTS: "
        + ", ".join(
            f"{name}={count}" for name, count in analysis.summary.counts.items() if count
        ),
        "",
        f"FINDINGS (showing {min(len(analysis.findings), MAX_FINDINGS_IN_PROMPT)} of "
        f"{len(analysis.findings)}; evidence snippets intentionally omitted):",
    ]

    if not analysis.findings:
        lines.append(
            "No rule-based findings were reported. Explain that this is a limited check, "
            "that account pricing/usage is not visible, and that manual billing and cleanup "
            "verification is still required."
        )
    else:
        for index, finding in enumerate(
            analysis.findings[:MAX_FINDINGS_IN_PROMPT], start=1
        ):
            location = finding.evidence.file + (
                f":{finding.evidence.line}" if finding.evidence.line else ""
            )
            lines.extend(
                [
                    f"{index}. [{finding.severity.upper()}/{finding.category}] "
                    f"{_clean(finding.title, 160)}",
                    f"   Resource: {_clean(finding.resource or 'not specified', 120)}",
                    f"   Evidence: {_clean(location, 140)}",
                    f"   Finding: {_clean(finding.message)}",
                    f"   Why: {_clean(finding.why)}",
                    f"   Deterministic fix: {_clean(finding.remediation)}",
                ]
            )
        if len(analysis.findings) > MAX_FINDINGS_IN_PROMPT:
            lines.append(
                f"({len(analysis.findings) - MAX_FINDINGS_IN_PROMPT} additional lower-priority "
                "finding(s) omitted from this prompt.)"
            )

    lines.extend(
        [
            "",
            "Write the explanation now. Do not mention this prompt or the omission of snippets.",
        ]
    )
    return "\n".join(lines)
