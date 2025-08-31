# evaluator.py  (patched)
from pathlib import Path
from schemas import RuleSet, DocumentReport, Finding
from archive.placeholder_rules_contracts import evaluate_text_against_rules

def make_report(document_name: str, text: str, rules: RuleSet) -> DocumentReport:
    findings, _guess = evaluate_text_against_rules(text, rules) or ([], None)
    # Guardrail: never return an empty set of findings
    if not findings:
        findings = [
            Finding(rule_id="liability_cap_present_and_within_bounds", passed=False,
                    details="No findings returned by rules; treat as fail.", citations=[]),
            Finding(rule_id="contract_value_within_limit", passed=False,
                    details="No findings returned by rules; treat as fail.", citations=[]),
            Finding(rule_id="fraud_clause_present_and_assigned", passed=False,
                    details="No findings returned by rules; treat as fail.", citations=[]),
            Finding(rule_id="jurisdiction_present_and_allowed", passed=False,
                    details="No findings returned by rules; treat as fail.", citations=[]),
        ]
    passed_all = all(f.passed for f in findings)
    return DocumentReport(document_name=document_name, passed_all=passed_all, findings=findings)

def save_markdown(report: DocumentReport, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    lines = []
    lines.append(f"# Compliance Report — {report.document_name}")
    lines.append("")
    lines.append(f"**Overall:** {'✅ PASS' if report.passed_all else '❌ FAIL'}")
    lines.append("")
    for f in report.findings:
        lines.append(f"## {f.rule_id.replace('_',' ').title()}")
        lines.append(f"- **Result:** {'PASS' if f.passed else 'FAIL'}")
        lines.append(f"- **Details:** {f.details}")
        if f.citations:
            lines.append("- **Citations:**")
            for c in f.citations:
                quote = c.quote.replace("\r"," ").replace("\n"," ").strip()
                if len(quote) > 420:
                    quote = quote[:420] + "…"
                lines.append(f"  - chars [{c.char_start}-{c.char_end}]: “{quote}”")
        lines.append("")
    (out_dir / "violations.md").write_text("\n".join(lines), encoding="utf-8")

def save_txt(report: DocumentReport, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    # Debug dump for quick inspection
    (out_dir / "_eval_debug.json").write_text(report.json(indent=2), encoding="utf-8")  # <-- NEW
    (out_dir / "violations.txt").write_text(report.json(indent=2), encoding="utf-8")
