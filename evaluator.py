# evaluator.py
from __future__ import annotations
from pathlib import Path
from typing import List
import re
from decimal import Decimal
import os
import json
from schemas import RuleSet, DocumentReport, Finding

# ---- Try to import your rule evaluator; provide a safe fallback ----
try:
    from archive.placeholder_rules_contracts import evaluate_text_against_rules
except Exception:
    def evaluate_text_against_rules(text: str, rules: RuleSet):
        # Fallback: no findings, no guess — keeps pipeline alive
        return ([], None)

# ---- Currency-context guard (prevents "200 million shares" as money) ----
_CURRENCY_HINT = re.compile(r"(\$|usd|dollar|dollars|£|gbp|€|eur|yen|¥|cad|aud)", re.I)
_SHARE_UNIT   = re.compile(r"\b(share|shares|unit|units|warrant|warrants|option|options)\b", re.I)
_NUMBERISH    = re.compile(r"\d")

def _looks_like_money(window_text: str) -> bool:
    """Legacy helper (still used by the generic guard)."""
    if _SHARE_UNIT.search(window_text):
        return False
    return bool(_CURRENCY_HINT.search(window_text))


# --- NEW: extra helpers for rule-aware normalization ---

def _has_share_context(window: str) -> bool:
    return bool(_SHARE_UNIT.search(window))

def _looks_like_money_ctx(window: str) -> bool:
    # currency hint AND not share context
    return bool(_CURRENCY_HINT.search(window)) and not _has_share_context(window)

def _maybe_guard_monetary_false_positives(text: str, findings: List[Finding]) -> List[Finding]:
    """
    If citations look numeric but lack currency context (or mention shares/units),
    flip the finding to PASS with an explanatory note — but only for monetary-ish rules.
    """
    monetary_keywords = (
        "contract_value", "liability_cap", "damages", "penalty",
        "payment", "consideration", "fee", "cost", "price", "amount"
    )

    fixed: List[Finding] = []
    for f in findings:
        rid = (f.rule_id or "").lower()

        # Only apply to monetary-ish rules
        if not any(k in rid for k in monetary_keywords):
            fixed.append(f)
            continue

        if not f.citations:
            fixed.append(f)
            continue

        windows = []
        for c in f.citations:
            s = max(0, min(len(text), c.char_start))
            e = max(0, min(len(text), c.char_end))
            win = text[max(0, s-40): min(len(text), e+40)]
            windows.append(win)

        if not any(_NUMBERISH.search(w) for w in windows):
            fixed.append(f)
            continue

        if not any(_looks_like_money(w) for w in windows):
            fixed.append(Finding(
                rule_id=f.rule_id,
                passed=True,
                details=(f"{f.details} [auto-guard: numeric citations lacked currency "
                         "context or referenced shares/units]"),
                citations=f.citations,
                tags=getattr(f, "tags", []),
            ))
        else:
            fixed.append(f)
    return fixed


# --- NEW: rule-aware normalization for consistency across all packs ---
def _normalize_findings_with_rules(text: str, rules: RuleSet, findings: List[Finding]) -> List[Finding]:
    """
    Make results consistent using rule context (applies to every rule pack):
      - contract_value_within_limit:
          * Ignore citations that are clearly shares/units (equity issuance).
          * If every citation is shares/units, PASS with an explicit note.
          * If money context exists and a max_contract_value is configured, respect the evaluator's
            'exceeds' note in details (flip to FAIL if it says 'exceeds').
      - jurisdiction_present_and_allowed:
          * If details say 'Not in allowed list', force FAIL.
    """
    out: List[Finding] = []

    # Pull configured cap if any
    max_contract = None
    try:
        if getattr(rules, "contract", None) and getattr(rules.contract, "max_contract_value", None) is not None:
            max_contract = Decimal(str(rules.contract.max_contract_value))
    except Exception:
        max_contract = None

    for f in findings:
        rid = (f.rule_id or "").lower()
        det = (f.details or "")

        # ---- contract_value_within_limit normalization ----
        if "contract_value_within_limit" in rid:
            windows = []
            for c in (f.citations or []):
                s = max(0, min(len(text), c.char_start))
                e = max(0, min(len(text), c.char_end))
                win = text[max(0, s - 60): min(len(text), e + 60)]
                windows.append(win)

            if windows:
                # If ALL citations look like equity/share context, PASS and clarify.
                if all(_has_share_context(w) and not _looks_like_money_ctx(w) for w in windows):
                    f = Finding(
                        rule_id=f.rule_id,
                        passed=True,
                        details="Ignored numeric amounts because context indicates equity issuance (shares/units), not monetary consideration.",
                        citations=f.citations,
                        tags=getattr(f, "tags", []),
                    )
                elif max_contract is not None:
                    # If ANY window looks like money, enforce cap consistency with details text.
                    any_money = any(_looks_like_money_ctx(w) for w in windows)
                    if any_money:
                        exceeds_claim = "exceed" in det.lower()
                        passed = not exceeds_claim
                        f = Finding(
                            rule_id=f.rule_id,
                            passed=passed,
                            details=(det if det else f"Checked against max_contract_value={max_contract}"),
                            citations=f.citations,
                            tags=getattr(f, "tags", []),
                        )
                    else:
                        # No credible money near the citations; PASS with explanation.
                        f = Finding(
                            rule_id=f.rule_id,
                            passed=True,
                            details="No credible monetary context detected near citations; ignoring share/unit counts for contract value.",
                            citations=f.citations,
                            tags=getattr(f, "tags", []),
                        )
                else:
                    # No max_contract configured; keep as-is but avoid confusing 'exceeds' phrasing.
                    if "exceed" in det.lower():
                        det = det + " (note: no max_contract_value configured; not enforced)"
                        f = Finding(
                            rule_id=f.rule_id,
                            passed=f.passed,
                            details=det,
                            citations=f.citations,
                            tags=getattr(f, "tags", []),
                        )

        # ---- jurisdiction_present_and_allowed normalization ----
        elif "jurisdiction_present_and_allowed" in rid:
            if "not in allowed list" in det.lower():
                f = Finding(
                    rule_id=f.rule_id,
                    passed=False,
                    details=det,
                    citations=f.citations,
                    tags=getattr(f, "tags", []),
                )

        out.append(f)

    return out


# --- OPTIONAL: append concise LLM rationales for failing findings (off unless enabled) ---
import os
def _coerce_to_text(res) -> str:
    """
    Normalize common provider results into plain text:
    - str -> str
    - dict -> try keys ('text', 'output', OpenAI-like 'choices', 'entities'), else json.dumps
    - object -> try .text or .to_dict(), else str(obj)
    """
    if res is None:
        return ""
    if isinstance(res, str):
        return res

    if isinstance(res, dict):
        # Friendly keys first
        if isinstance(res.get("text"), str):
            return res["text"]
        if isinstance(res.get("output"), str):
            return res["output"]
        # OpenAI-style choices
        if isinstance(res.get("choices"), list):
            parts = []
            for ch in res["choices"]:
                if isinstance(ch, dict):
                    msg = ch.get("message") or {}
                    if isinstance(msg, dict) and isinstance(msg.get("content"), str):
                        parts.append(msg["content"])
                    elif isinstance(ch.get("text"), str):
                        parts.append(ch["text"])
            if parts:
                return "\n".join(parts)
        # LangExtract-style "entities"
        if isinstance(res.get("entities"), list):
            parts = []
            for ent in res["entities"]:
                if isinstance(ent, dict):
                    name = ent.get("name") or ent.get("label") or "Field"
                    val  = ent.get("value") or ent.get("text") or ""
                    if isinstance(val, (list, dict)):
                        try:
                            val = json.dumps(val, ensure_ascii=False)
                        except Exception:
                            val = str(val)
                    parts.append(f"{name}: {val}")
            if parts:
                return "\n".join(parts)
        # Fallback: pretty-print
        try:
            return json.dumps(res, ensure_ascii=False, indent=2)
        except Exception:
            return str(res)

    # Object with .text
    txt = getattr(res, "text", None)
    if isinstance(txt, str):
        return txt

    # Object with .to_dict()
    to_dict = getattr(res, "to_dict", None)
    if callable(to_dict):
        try:
            return _coerce_to_text(to_dict())
        except Exception:
            pass

    return str(res)


def _call_llm_any(provider, *, doc_text: str, prompt: str):
    """
    Try provider APIs in order and return (mode, text).
    mode ∈ {'completion','chat','extract','error'}.
    """
    # 1) Plain completion (preferred for prose)
    try:
        if hasattr(provider, "complete"):
            out = provider.complete(prompt)  # type: ignore
            return "completion", _coerce_to_text(out)
    except Exception as e:
        return "error", f"[llm error: {e}]"

    # 2) Simple chat
    try:
        if hasattr(provider, "chat"):
            out = provider.chat([{"role": "user", "content": prompt}])  # type: ignore
            return "chat", _coerce_to_text(out)
    except Exception as e:
        return "error", f"[llm error: {e}]"

    # 3) Extract with minimal examples (some providers require this)
    try:
        if hasattr(provider, "extract"):
            minimal_examples = [
                {
                    "input": "Explain why a contract compliance finding failed and suggest a fix.",
                    "entities": [
                        {"name": "Reasoning", "value": "The clause is missing or too broad."},
                        {"name": "Risk", "value": "Uncapped liability or unfavorable venue."},
                        {"name": "Suggested Fix", "value": "Add a limitation of liability and align venue with the allowlist."},
                    ],
                }
            ]
            out = provider.extract(
                text_or_documents=doc_text,
                prompt=prompt,
                examples=minimal_examples,      # required by your provider
                extraction_passes=1,
                max_workers=1,
                max_char_buffer=int(os.getenv("CE_MAX_CHAR_BUFFER", "1500")),
            )
            return "extract", _coerce_to_text(out)
    except Exception as e:
        return "error", f"[llm error: {e}]"

    return "error", "[llm error: no supported method on provider]"



def _maybe_add_llm_explanations(text: str, rules: RuleSet, findings: List[Finding], max_failures: int = 3) -> List[Finding]:
    """
    Append concise LLM rationales to failing findings when ENABLE_LLM_EXPLANATIONS is truthy.
    Always adds a status finding so it's obvious whether this step ran and which mode was used.
    """
    flag_raw = os.getenv("ENABLE_LLM_EXPLANATIONS", "")
    enabled = flag_raw.lower() in ("1", "true", "yes", "on")

    status = [f"env.ENABLE_LLM_EXPLANATIONS={flag_raw!r} -> {'enabled' if enabled else 'disabled'}"]
    if not enabled:
        findings.append(Finding(rule_id="llm_explanations_status", passed=True, details="LLM explanations disabled.", citations=[], tags=[]))
        return findings

    # Load provider
    try:
        from llm_factory import load_provider
        provider = load_provider()
        status.append(f"provider_loaded={bool(provider)}")
    except Exception as e:
        status.append(f"provider_error={e!r}")
        findings.append(Finding(rule_id="llm_explanations_status", passed=False, details="LLM provider could not be loaded: {}".format(e), citations=[], tags=[]))
        return findings

    used = 0
    updated: List[Finding] = []
    for f in findings:
        if not f.passed and used < max_failures:
            # Local context around first citation
            snippet = ""
            if f.citations:
                c = f.citations[0]
                s = max(0, min(len(text), c.char_start))
                e = max(0, min(len(text), c.char_end))
                snippet = text[max(0, s - 300): min(len(text), e + 300)]

            findings_summary = "\n".join(f"- {x.rule_id}: {'PASS' if x.passed else 'FAIL'} — {x.details}" for x in findings[:8])

            prompt = (
                "You are a meticulous contracts analyst. Explain, in 3–5 sentences, why the following finding likely failed, "
                "pointing to concrete contract language. Avoid hallucinations; if unsure, say so.\n\n"
                f"Finding ID: {f.rule_id}\n"
                f"Other findings (context):\n{findings_summary}\n\n"
                "Relevant contract excerpt:\n-----\n"
                f"{snippet}\n-----\n\n"
                "Answer format:\n"
                "Reasoning: <plain-language rationale>\n"
                "Risk: <specific risk if unaddressed>\n"
                "Suggested Fix: <practical remediation language>\n"
            )

            mode, rationale = _call_llm_any(provider, doc_text=text, prompt=prompt)
            rationale = (rationale or "").strip()
            tag = f" [mode: {mode}]"
            if rationale:
                f = Finding(
                    rule_id=f.rule_id,
                    passed=f.passed,
                    details=f"{f.details}\n\nLLM rationale:{tag}\n{rationale[:1200]}",
                    citations=f.citations,
                    tags=getattr(f, "tags", []),
                )
                used += 1
        updated.append(f)

    findings = updated
    findings.append(Finding(rule_id="llm_explanations_status", passed=True, details="; ".join(status), citations=[], tags=[]))
    return findings






# ---- Main API ----
def make_report(document_name: str, text: str, rules: RuleSet) -> DocumentReport:
    findings, _guess = evaluate_text_against_rules(text, rules) or ([], None)
    print("[debug] ENABLE_LLM_EXPLANATIONS =", os.getenv("ENABLE_LLM_EXPLANATIONS"))

    if findings:
        # Generic guard (keeps “200 million shares” out of money checks)
        findings = _maybe_guard_monetary_false_positives(text, findings)
        # Rule-aware normalization (fixes contract-value + jurisdiction contradictions)
        findings = _normalize_findings_with_rules(text, rules, findings)
        # NEW: append concise LLM rationales for failing findings (if enabled)
        findings = _maybe_add_llm_explanations(text, rules, findings)

    if not findings:
        findings = [Finding(
            rule_id="no_findings_returned",
            passed=False,
            details="No findings returned by the rule engine for this document.",
            citations=[],
        )]
    passed_all = all(f.passed for f in findings)
    return DocumentReport(document_name=document_name, passed_all=passed_all, findings=findings)

# ---- Markdown utilities (used by main.py) ----
def render_markdown(report: DocumentReport) -> str:
    lines = []
    lines.append(f"# Compliance Report — {report.document_name}")
    lines.append("")
    lines.append(f"**Overall:** {'✅ PASS' if report.passed_all else '❌ FAIL'}")
    lines.append("")
    for f in report.findings:
        title = (f.rule_id or "").replace("_", " ").title() or "Finding"
        lines.append(f"## {title}")
        lines.append(f"- **Result:** {'PASS' if f.passed else 'FAIL'}")
        lines.append(f"- **Details:** {f.details}")
        if f.citations:
            lines.append("- **Citations:**")
            for c in f.citations:
                quote = (c.quote or "").replace("\r"," ").replace("\n"," ").strip()
                if len(quote) > 420:
                    quote = quote[:420] + "…"
                lines.append(f"  - chars [{c.char_start}-{c.char_end}]: “{quote}”")
        lines.append("")
    return "\n".join(lines)

def save_markdown(report: DocumentReport, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "violations.md").write_text(render_markdown(report), encoding="utf-8")

def save_txt(report: DocumentReport, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "violations.txt").write_text(report.json(indent=2), encoding="utf-8")
    (out_dir / "_eval_debug.json").write_text(report.json(indent=2), encoding="utf-8")