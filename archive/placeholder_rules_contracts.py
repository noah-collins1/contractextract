# rules/contracts.py
import re
from typing import List, Tuple, Optional, Iterable
# placeholder_rules_contracts.py
import re
from typing import List, Tuple, Optional
from schemas import RuleSet, Finding, Citation

# ---------- Regex patterns ----------
MONEY_RE = re.compile(r'(?P<currency>\$|USD|US\$|EUR|€|GBP|£|AUD|A\$)?\s?(?P<amount>\d{1,3}(?:[,.\s]\d{3})*(?:\.\d{2})?|\d+(?:\.\d{2})?)', re.IGNORECASE)
GOV_LAW_RE = re.compile(r'(governing law|jurisdiction|venue)\s*[:\-]?\s*(?:of|in)?\s*([A-Za-z][A-Za-z\s().,&\-]+)', re.IGNORECASE)
LIAB_SECTION_RE = re.compile(r'(limitation of liability|liability(?:\s+limit| cap)?)', re.IGNORECASE)
MONTHS_FEES_RE = re.compile(r'(?:twelve|12)\s*\(?12?\)?\s*months? of (?:fees|payments|service fees)', re.IGNORECASE)
FRAUD_RE = re.compile(r'\bfraud\b', re.IGNORECASE)
OTHER_PARTY_HEURISTIC_RE = re.compile(r'(sole|entire)\s+responsibility|liab(?:ility)?\s+(?:of|on)\s+(?:the\s+)?other\s+party', re.IGNORECASE)
SIGNATURE_NOISE = re.compile(r'(signature page follows|confidential|translation, for reference only)', re.IGNORECASE)

# ---------- Helpers ----------
def _norm_amount(txt: str) -> Optional[float]:
    try:
        return float(re.sub(r'[,\s]', '', txt))
    except Exception:
        return None

def parse_money(text: str) -> List[Tuple[float, str, Tuple[int,int]]]:
    out = []
    for m in MONEY_RE.finditer(text):
        amt = _norm_amount(m.group('amount'))
        cur = m.group('currency') or ''
        if amt is not None:
            out.append((amt, cur, m.span()))
    return out

def max_money(text: str) -> Optional[Tuple[float, str, Tuple[int,int]]]:
    vals = parse_money(text)
    return max(vals, key=lambda t: t[0]) if vals else None

def find_liability_section(text: str) -> Optional[Tuple[int,int]]:
    m = LIAB_SECTION_RE.search(text)
    if not m:
        return None
    start = max(0, m.start() - 600)
    end = min(len(text), m.end() + 1200)
    return (start, end)

def window_quote(text: str, span: Tuple[int,int], pad: int = 140) -> Citation:
    s, e = span
    qs = max(0, s - pad)
    qe = min(len(text), e + pad)
    return Citation(char_start=s, char_end=e, quote=text[qs:qe])

def _strip_noise(text: str) -> str:
    lines = text.splitlines()
    keep = []
    for ln in lines:
        if SIGNATURE_NOISE.search(ln):
            continue
        keep.append(ln)
    return "\n".join(keep)

# ---------- Rule checks ----------
def check_liability_cap_present_and_within_bounds(text: str, rules: RuleSet, contract_value_guess: Optional[float]) -> Finding:
    sec_span = find_liability_section(text)
    if sec_span is None:
        return Finding(
            rule_id="liability_cap_present_and_within_bounds",
            passed=False,
            details="No clear ‘Limitation of Liability’ section found.",
            citations=[]
        )
    cit = window_quote(text, sec_span)
    section = text[sec_span[0]:sec_span[1]]

    cap_ok = True
    notes = []

    if MONTHS_FEES_RE.search(section):
        if rules.liability_cap.max_cap_multiplier is not None and rules.liability_cap.max_cap_multiplier < 1.0:
            cap_ok = False
            notes.append("Found ‘12 months of fees’ (~1x), exceeds configured multiplier.")
        else:
            notes.append("Found ‘12 months of fees’ (~1x multiplier).")

    money_in_section = parse_money(section)
    if money_in_section:
        highest_cap = max(money_in_section, key=lambda t: t[0])
        cap_amt, cap_cur, cap_span = highest_cap
        notes.append(f"Found explicit monetary cap candidate: {cap_cur}{cap_amt:,.2f}.")
        if rules.liability_cap.max_cap_amount is not None and cap_amt > rules.liability_cap.max_cap_amount:
            cap_ok = False
            notes.append(f"Cap {cap_amt:,.2f} exceeds allowed {rules.liability_cap.max_cap_amount:,.2f}.")
        if contract_value_guess is not None and rules.liability_cap.max_cap_multiplier is not None:
            if cap_amt > rules.liability_cap.max_cap_multiplier * contract_value_guess:
                cap_ok = False
                notes.append(f"Cap {cap_amt:,.2f} exceeds {rules.liability_cap.max_cap_multiplier}× inferred contract value {contract_value_guess:,.2f}.")

    if not money_in_section and not MONTHS_FEES_RE.search(section):
        cap_ok = False
        notes.append("No clear cap indicator (‘12 months of fees’ or explicit monetary cap) detected.")

    return Finding(
        rule_id="liability_cap_present_and_within_bounds",
        passed=cap_ok,
        details="; ".join(notes) if notes else ("Cap appears within configured bounds." if cap_ok else "Cap not within bounds."),
        citations=[cit]
    )

def check_contract_value_within_limit(text: str, rules: RuleSet) -> Finding:
    if rules.contract.max_contract_value is None:
        return Finding(
            rule_id="contract_value_within_limit",
            passed=True,
            details="No max contract value configured; skipping.",
            citations=[]
        )
    mm = max_money(text)
    if not mm:
        return Finding(
            rule_id="contract_value_within_limit",
            passed=True,
            details="Could not identify a contract value; no obvious monetary amounts found.",
            citations=[]
        )
    amt, cur, span = mm
    passed = amt <= rules.contract.max_contract_value
    return Finding(
        rule_id="contract_value_within_limit",
        passed=passed,
        details=f"Largest detected amount {cur}{amt:,.2f} {'is within' if passed else 'exceeds'} configured limit {rules.contract.max_contract_value:,.2f}.",
        citations=[window_quote(text, span)]
    )

def check_fraud_clause_present_and_assigned(text: str, rules: RuleSet) -> Finding:
    if not rules.fraud.require_fraud_clause:
        return Finding(
            rule_id="fraud_clause_present_and_assigned",
            passed=True,
            details="Fraud clause not required by config.",
            citations=[]
        )
    m = FRAUD_RE.search(text)
    if not m:
        return Finding(
            rule_id="fraud_clause_present_and_assigned",
            passed=False,
            details="No ‘fraud’ mention found.",
            citations=[]
        )
    s,e = m.span()
    window_s = max(0, s-300)
    window_e = min(len(text), e+300)
    nearby = text[window_s:window_e]
    assigned_ok = True
    note = "‘fraud’ found."
    if rules.fraud.require_liability_on_other_party:
        if not OTHER_PARTY_HEURISTIC_RE.search(nearby):
            assigned_ok = False
            note += " Could not confirm liability assigned to the ‘other party’ near the fraud reference."
        else:
            note += " Liability appears assigned to the other party."
    return Finding(
        rule_id="fraud_clause_present_and_assigned",
        passed=assigned_ok,
        details=note,
        citations=[Citation(char_start=s, char_end=e, quote=nearby)]
    )

def check_jurisdiction_present_and_allowed(text: str, rules: RuleSet) -> Finding:
    m = GOV_LAW_RE.search(text)
    if not m:
        return Finding(
            rule_id="jurisdiction_present_and_allowed",
            passed=False,
            details="No clear ‘governing law / jurisdiction’ clause detected.",
            citations=[]
        )
    loc = m.group(2).strip()
    allowed = rules.jurisdiction.allowed_countries
    is_allowed = any(a.lower() in loc.lower() for a in allowed)
    return Finding(
        rule_id="jurisdiction_present_and_allowed",
        passed=is_allowed,
        details=f"Governing law/jurisdiction detected as “{loc}”. {'Allowed' if is_allowed else 'Not in allowed list.'}",
        citations=[window_quote(text, m.span(2))]
    )

# ---------- Orchestrator ----------
def evaluate_text_against_rules(text: str, rules: RuleSet):
    text = _strip_noise(text or "")
    # Rough contract value guess (largest monetary amount)
    mm = max_money(text)
    contract_value_guess = mm[0] if mm else None

    findings = [
        check_liability_cap_present_and_within_bounds(text, rules, contract_value_guess),
        check_contract_value_within_limit(text, rules),
        check_fraud_clause_present_and_assigned(text, rules),
        check_jurisdiction_present_and_allowed(text, rules),
    ]
    return findings, contract_value_guess
