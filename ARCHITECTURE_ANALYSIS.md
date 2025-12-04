# ContractExtract Architecture Analysis
## Complete answers to system behavior questions

---

## SECTION 1 — Rule Evaluation Logic

### Q1: Where are non-compliance rules (e.g., lease.* types) evaluated?

**Answer: They are NOT evaluated at all.**

**Evidence:**
- `contract_analyzer.py:298-316` - `evaluate_text_against_rules()` function
- This function returns a **hardcoded list** of only 4 findings:
  ```python
  findings = [
      check_liability_cap_present_and_within_bounds(text, rules, contract_value_guess),
      check_contract_value_within_limit(text, rules),
      check_fraud_clause_present_and_assigned(text, rules),
      check_jurisdiction_present_and_allowed(text, rules),
  ]
  ```

**What this means:**
- Your YAML `rules:` section with `lease.property`, `lease.tenant`, etc. **is completely ignored**
- These custom rule types are **stored in the database** but **never executed**
- Only the 4 hardcoded compliance checks run

---

### Q2: Does make_report() add findings for rules defined under rules: in my YAML?

**Answer: NO. It only processes hard-coded compliance checks.**

**Evidence:**
- `contract_analyzer.py:711-751` - `make_report()` function
- Line 727: `findings, _guess = evaluate_text_against_rules(text, rules)`
- This calls the function above, which returns only 4 hardcoded findings
- `report.findings` will ONLY contain:
  1. `liability_cap_present_and_within_bounds`
  2. `contract_value_within_limit`
  3. `fraud_clause_present_and_assigned`
  4. `jurisdiction_present_and_allowed`

**What IS included in report.findings:**
- ✅ Liability cap checks (from `rules.liability_cap`)
- ✅ Contract value checks (from `rules.contract`)
- ✅ Fraud clause checks (from `rules.fraud`)
- ✅ Jurisdiction checks (from `rules.jurisdiction`)

**What IS NOT included:**
- ❌ Custom rule types (lease.property, lease.dates, etc.)
- ❌ LLM-extracted information
- ❌ Any rules defined in the `rules_json` field

---

### Q3: What structure is expected for a RuleFinding?

**Answer: The `Finding` class from `infrastructure.py`**

**Exact structure (infrastructure.py:168-177):**
```python
class Finding(BaseModel):
    rule_id: str
    passed: bool
    details: str
    citations: List[Citation] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    llm_explanation: Optional[str] = None
```

**Required fields for Markdown output:**
- `rule_id`: Used as section header (e.g., "Lease Property" from "lease_property")
- `passed`: Determines "PASS" or "FAIL" display
- `details`: The explanation text
- `citations`: List of Citation objects (optional but recommended)

**Citation structure (infrastructure.py:154-166):**
```python
class Citation(BaseModel):
    char_start: int
    char_end: int
    quote: str
    page: Optional[int] = None
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    confidence: float = 1.0
```

---

## SECTION 2 — Extraction Pipeline

### Q4: Which function runs the LLM extraction from prompt: and examples:?

**Answer: NONE. There is NO extraction pipeline.**

**Evidence:**
- Searched entire `contract_analyzer.py` for usage of `llm_prompt` or `examples`
- Result: **0 matches** (except in LLM provider class definitions)
- The `prompt:` and `examples:` from your YAML are:
  - ✅ Stored in database (`rulepack_manager.py:50` - `llm_prompt` column)
  - ✅ Retrieved when loading rule packs (`rulepack_manager.py:167`)
  - ❌ NEVER passed to any extraction function
  - ❌ NEVER used during analysis

**Where LLM IS used:**
- `contract_analyzer.py:557-603` - `_call_llm_any()` function
- BUT this is ONLY used for adding **explanations to failed findings**
- Line 741: `findings = _maybe_add_llm_explanations(text, rules, findings, llm_override=llm_override)`
- This adds `llm_explanation` to existing findings, doesn't extract new data

---

### Q5: Is LLM extraction output attached to DocumentReport?

**Answer: NO. There is no extraction output to attach.**

**DocumentReport structure (infrastructure.py:179-183):**
```python
class DocumentReport(BaseModel):
    document_name: str
    passed_all: bool
    findings: List[Finding]
```

**What's stored:**
- `findings`: Only the 4 hardcoded compliance findings
- NO field for `extractions`, `data`, `lease_info`, or any extracted fields

---

### Q6: Does extraction run separately from compliance pipeline?

**Answer: There is NO extraction pipeline at all.**

**Current flow:**
1. PDF → Text extraction (with OCR)
2. Text → Document type classification
3. Text → Compliance evaluation (4 hardcoded checks only)
4. Report generation (Markdown)

**What's missing:**
- NO step that uses `prompt:` from YAML
- NO step that uses `examples:` from YAML
- NO LLM extraction of structured data
- NO lease field extraction

---

## SECTION 3 — Markdown Generation

### Q7: Does render_markdown() iterate over anything besides report.findings?

**Answer: NO. It ONLY iterates over report.findings.**

**Evidence (contract_analyzer.py:758-835):**
```python
def render_markdown(report: DocumentReport) -> str:
    lines = []
    lines.append(f"# Compliance Report — {report.document_name}")
    # ...
    for f in report.findings:  # ← ONLY source of data
        # Skip status findings
        if f.rule_id == "llm_explanations_status":
            continue

        title = (f.rule_id or "").replace("_", " ").title() or "Finding"
        lines.append(f"## {title}")
        lines.append(f"- **Result:** {'PASS' if f.passed else 'FAIL'}")
        lines.append(f"- **Details:** {f.details}")
        # ... citations ...
```

**What can appear in Markdown:**
- ONLY what's in `report.findings`
- NO other data source is consulted

---

### Q8: Is there functionality to render extraction fields into Markdown?

**Answer: NO. You must implement this manually.**

**Current capabilities:**
- ✅ Renders findings (compliance checks)
- ✅ Renders citations with page/line numbers
- ✅ Adds executive summary for failures
- ❌ NO extraction field rendering
- ❌ NO structured data display
- ❌ NO lease abstract section

**To add extraction fields, you would need to:**
1. Create new fields in `DocumentReport` class
2. Modify `render_markdown()` to render these fields
3. Implement extraction logic to populate them

---

## SECTION 4 — Intent of Rulepack Structure

### Q9: Which sections are used for compliance vs. extraction?

**Answer:**

| YAML Section | Purpose | Currently Used? |
|--------------|---------|----------------|
| `id` | Rulepack identifier | ✅ YES - for selection |
| `doc_type_names` | Document classification | ✅ YES - for auto-detect |
| `jurisdiction_allowlist` | Compliance check | ✅ YES - evaluated |
| `liability_cap` | Compliance check | ✅ YES - evaluated |
| `contract.max_contract_value` | Compliance check | ✅ YES - evaluated |
| `fraud` | Compliance check | ✅ YES - evaluated |
| `rules:` (custom types) | **Intended for extraction** | ❌ **NOT USED** |
| `prompt:` | **Intended for LLM extraction** | ❌ **NOT USED** |
| `examples:` | **Intended for LLM extraction** | ❌ **NOT USED** |
| `notes:` | Documentation | ✅ YES - stored only |

**Currently unused sections:**
- `rules:` array with custom types (lease.property, etc.)
- `prompt:` field
- `examples:` array
- These are **stored in database** but **never executed**

---

### Q10: Are rule types like lease.property hooked into any evaluation system?

**Answer: NO. They are arbitrary metadata fields with no evaluation logic.**

**Evidence:**
- `rulepack_manager.py:50-51` - Database schema:
  ```python
  rules_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
  ```
- This stores your `rules:` array as JSON
- But there's NO code that:
  - Reads `rules_json` during analysis
  - Dispatches based on rule type (lease.property, etc.)
  - Evaluates custom rules
  - Creates findings from custom rules

**What would be needed:**
- A rule dispatcher that reads `rules_json`
- Evaluator functions for each rule type
- Integration into `evaluate_text_against_rules()`

---

## SECTION 5 — What You Need to Add

### Q11: How to make each lease rule produce a PASS/FAIL finding?

**Answer: You must implement custom rule evaluators.**

**Implementation location:**
Add to `contract_analyzer.py` after line 316:

```python
def evaluate_custom_rules(text: str, rules_json: List[dict]) -> List[Finding]:
    """Evaluate custom rule types from YAML rules: section."""
    findings = []

    for rule in rules_json:
        rule_id = rule.get('id', 'unknown')
        rule_type = rule.get('type', '')
        params = rule.get('params', {})

        # Dispatch based on type
        if rule_type == 'lease.property':
            findings.append(check_lease_property(text, params))
        elif rule_type == 'lease.tenant':
            findings.append(check_lease_tenant(text, params))
        elif rule_type == 'lease.dates':
            findings.append(check_lease_dates(text, params))
        # ... etc for each lease.* type

    return findings

# Then in evaluate_text_against_rules(), line 315:
findings.extend(evaluate_custom_rules(text, rules.rules_json or []))
```

**Each evaluator function should:**
```python
def check_lease_property(text: str, params: dict) -> Finding:
    """Check if property information is present and complete."""
    # Your logic here
    # Use regex, pattern matching, or LLM

    return Finding(
        rule_id="lease_property_check",
        passed=True/False,
        details="Property name and address found/missing",
        citations=[...],
    )
```

---

### Q12: How to add a 'Lease Abstract' section with extracted fields?

**Answer: Extend DocumentReport and modify render_markdown().**

**Step 1: Extend DocumentReport (infrastructure.py:179)**

```python
class LeaseExtraction(BaseModel):
    """Structured lease data extraction."""
    property_name: Optional[str] = None
    property_address: Optional[str] = None
    tenant_name: Optional[str] = None
    lease_commencement: Optional[str] = None
    lease_expiration: Optional[str] = None
    base_rent: Optional[str] = None
    security_deposit: Optional[str] = None
    # ... all 118 fields

class DocumentReport(BaseModel):
    document_name: str
    passed_all: bool
    findings: List[Finding]
    extraction: Optional[LeaseExtraction] = None  # ← ADD THIS
```

**Step 2: Implement extraction (contract_analyzer.py after line 751)**

```python
def extract_lease_fields(text: str, prompt: str, examples: list) -> LeaseExtraction:
    """Use LLM to extract structured lease fields."""
    provider = load_provider()

    result = provider.extract(
        text_or_documents=text,
        prompt=prompt,
        examples=examples,
        extraction_passes=1,
        max_workers=1,
        max_char_buffer=1500,
    )

    # Parse result into LeaseExtraction object
    return LeaseExtraction(**parse_llm_result(result))
```

**Step 3: Modify make_report() (line 751)**

```python
def make_report(document_name, text, rules, pack_data, llm_override=None):
    # ... existing code ...

    # Add extraction if prompt provided
    extraction = None
    if pack_data.llm_prompt and pack_data.examples:
        extraction = extract_lease_fields(
            text,
            pack_data.llm_prompt,
            pack_data.examples
        )

    return DocumentReport(
        document_name=document_name,
        passed_all=passed_all,
        findings=findings,
        extraction=extraction  # ← ADD THIS
    )
```

**Step 4: Modify render_markdown() (insert after line 791)**

```python
def render_markdown(report: DocumentReport) -> str:
    lines = []
    # ... existing title and executive summary ...

    # ADD THIS: Lease Abstract section
    if report.extraction:
        lines.append("## Lease Abstract")
        lines.append("")
        lines.append("### Property Information")
        lines.append(f"- **Property Name:** {report.extraction.property_name or 'Not specified'}")
        lines.append(f"- **Address:** {report.extraction.property_address or 'Not specified'}")
        lines.append("")
        lines.append("### Tenant Information")
        lines.append(f"- **Tenant Name:** {report.extraction.tenant_name or 'Not specified'}")
        lines.append("")
        lines.append("### Lease Terms")
        lines.append(f"- **Commencement Date:** {report.extraction.lease_commencement or 'Not specified'}")
        lines.append(f"- **Expiration Date:** {report.extraction.lease_expiration or 'Not specified'}")
        lines.append(f"- **Base Rent:** {report.extraction.base_rent or 'Not specified'}")
        lines.append(f"- **Security Deposit:** {report.extraction.security_deposit or 'Not specified'}")
        lines.append("")
        # ... add all 118 fields organized by category ...

    # ... then existing compliance findings loop ...
```

---

## Summary: Current State

**What Works:**
✅ PDF text extraction (with OCR)
✅ Document type classification
✅ 4 hardcoded compliance checks
✅ Citation extraction with page/line numbers
✅ LLM explanations for failed findings
✅ Markdown report generation
✅ Database storage of rulepacks

**What Doesn't Work:**
❌ Custom rule evaluation (lease.property, etc.)
❌ LLM extraction from prompt/examples
❌ Structured data extraction
❌ Lease abstract generation
❌ Custom findings from YAML rules

**What You Need to Build:**
1. Custom rule dispatcher and evaluators
2. LLM extraction pipeline
3. Structured data models (LeaseExtraction)
4. Enhanced report rendering for extracted data
5. Integration of extraction into analysis flow

---

## Recommended Implementation Order

1. **Start with extraction** - Get LLM extraction working first
   - Modify `make_report()` to call LLM with prompt/examples
   - Parse extraction results into structured data
   - Add extraction field to DocumentReport

2. **Enhance Markdown rendering** - Display extracted data
   - Add Lease Abstract section to `render_markdown()`
   - Format extracted fields into readable sections

3. **Add custom rule evaluation** - Make YAML rules work
   - Implement rule dispatcher
   - Create evaluator functions for each lease.* type
   - Integrate into findings pipeline

4. **Test and iterate** - Refine extraction
   - Test with real lease documents
   - Tune prompts and examples
   - Adjust formatting

---

**Next Steps:** Would you like me to implement any of these components for you?