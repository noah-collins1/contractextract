# 

Contract Analyzer Logic Analysis

## Understanding Why Rule Packs Are Ignored or Fail

**Document Created:** November 25, 2025
**Analysis of:** `contract_analyzer.py` (590 lines)
**Focus:** Hardcoded evaluation logic and its limitations

---

## Executive Summary

The `contract_analyzer.py` file contains **hardcoded evaluation logic** that processes contract compliance checks. While the system **does support custom rules from YAML**, there is a **critical mismatch** between:

1. **What the YAML rulepacks define** (parameter names, rule types, expected behavior)
2. **What the hardcoded Python functions actually check** (different parameter names, limited rule type coverage)

This mismatch causes many custom rules to be **silently ignored** or **evaluated incorrectly**, even though the dispatcher is working and calling the handler functions.

---

## Architecture Overview

### Two-Tier Evaluation System

```
┌─────────────────────────────────────────────────────────┐
│ TIER 1: Hardcoded Compliance Checks (ALWAYS EXECUTED)  │
│                                                         │
│ evaluate_text_against_rules() - Line 678               │
│ ├── check_liability_cap_present_and_within_bounds()    │
│ ├── check_contract_value_within_limit()                │
│ ├── check_fraud_clause_present_and_assigned()          │
│ └── check_jurisdiction_present_and_allowed()           │
│                                                         │
│ These 4 checks run on EVERY document, regardless       │
│ of rulepack. They use RuleSet fields from YAML.        │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ TIER 2: Custom Rule Dispatching (CONDITIONAL)          │
│                                                         │
│ evaluate_custom_rules() - Line 638                     │
│                                                         │
│ IF pack_data.rules_json exists:                        │
│   For each rule in rules_json:                         │
│     Dispatch to handler based on rule.type:            │
│     ├── lease.property    → check_lease_property()     │
│     ├── lease.tenant      → check_lease_tenant()       │
│     ├── lease.dates       → check_lease_dates()        │
│     ├── lease.rent        → check_lease_rent()         │
│     ├── lease.security    → check_lease_security()     │
│     └── lease.options     → check_lease_options()      │
│                                                         │
│ These handlers run ONLY if rules_json is provided      │
│ AND the rule type matches a known handler.             │
└─────────────────────────────────────────────────────────┘
```

---

## The Core Problem: Parameter Name Mismatches

### Problem Statement

**The hardcoded handler functions expect specific parameter names**, but the **YAML rulepacks define different parameter names**. This causes rules to fail silently or use fallback behavior instead of the intended validation logic.

### Example: Lease Dates Check

**YAML Definition (lease_agreement.yml lines 29-34):**

```yaml
- id: lease_dates_required
  type: lease.dates
  params:
    require_execution_date: true       # ❌ NOT USED
    require_commencement_date: true    # ❌ NOT USED
    require_expiration_date: true      # ❌ NOT USED
```

**Python Handler (contract_analyzer.py lines 494-539):**

```python
def check_lease_dates(text: str, params: dict, extraction: Optional['LeaseExtraction'] = None) -> Finding:
    """Check if required lease dates are present."""

    require_dates = params.get('require_lease_dates', True)  # ⚠️ DIFFERENT NAME!

    if not require_dates:
        return Finding(rule_id="lease.dates", passed=True, ...)

    # If extraction data available, check specific fields
    if extraction:
        has_start = bool(extraction.lease_commencement_date)
        has_end = bool(extraction.lease_expiration_date)

        if has_start and has_end:
            return Finding(rule_id="lease.dates", passed=True, ...)

    # Fallback: Simple text search
    has_dates = bool(re.search(r'(commencement|expiration|term)', text, re.IGNORECASE))
    return Finding(rule_id="lease.dates", passed=has_dates, ...)
```

**What Happens:**

1. YAML defines: `require_execution_date`, `require_commencement_date`, `require_expiration_date`
2. Python looks for: `require_lease_dates`
3. Python doesn't find `require_lease_dates` in params, defaults to `True`
4. Python **ignores** the specific date requirements from YAML
5. Evaluation proceeds with generic logic instead of YAML-specified logic

**Result:** The YAML's detailed requirements (execution date, commencement date, expiration date) are **completely ignored**. The function uses a simple regex fallback.

---

## Complete Mismatch Inventory

### 1. Lease Property Check


| YAML Parameter                   | Python Expected            | Match? | Impact          |
| -------------------------------- | -------------------------- | ------ | --------------- |
| `require_property_details: true` | `require_property_details` | ✅ YES | Works correctly |

**Status:** ✅ **WORKING** - Parameter names match

---

### 2. Lease Tenant Check


| YAML Parameter                 | Python Expected          | Match? | Impact          |
| ------------------------------ | ------------------------ | ------ | --------------- |
| `require_tenant_details: true` | `require_tenant_details` | ✅ YES | Works correctly |

**Status:** ✅ **WORKING** - Parameter names match

---

### 3. Lease Dates Check


| YAML Parameter                    | Python Expected       | Match? | Impact      |
| --------------------------------- | --------------------- | ------ | ----------- |
| `require_execution_date: true`    | `require_lease_dates` | ❌ NO  | **Ignored** |
| `require_commencement_date: true` | `require_lease_dates` | ❌ NO  | **Ignored** |
| `require_expiration_date: true`   | `require_lease_dates` | ❌ NO  | **Ignored** |

**Status:** ⚠️ **PARTIALLY BROKEN** - YAML's granular date requirements ignored, uses generic fallback

**What Actually Happens:**

- Python defaults `require_lease_dates = True` (since YAML param not found)
- If extraction exists, checks only `lease_commencement_date` and `lease_expiration_date`
- **Execution date requirement is NEVER checked** even though YAML specifies it
- Falls back to simple regex: `(commencement|expiration|term)`

---

### 4. Lease Rent Check


| YAML Parameter                    | Python Expected        | Match? | Impact      |
| --------------------------------- | ---------------------- | ------ | ----------- |
| `require_base_rent: true`         | `require_rent_details` | ❌ NO  | **Ignored** |
| `require_payment_frequency: true` | `require_rent_details` | ❌ NO  | **Ignored** |

**Status:** ⚠️ **PARTIALLY BROKEN** - YAML's specific rent requirements ignored

**What Actually Happens:**

- Python defaults `require_rent_details = True`
- Checks for `extraction.base_rent_amount` (generic check)
- **Payment frequency requirement is NEVER checked** even though YAML specifies it
- Falls back to regex: `(base rent|monthly rent|annual rent)`

---

### 5. Lease Security Check


| YAML Parameter                 | Python Expected            | Match?       | Impact              |
| ------------------------------ | -------------------------- | ------------ | ------------------- |
| `check_security_deposit: true` | `require_security_deposit` | ⚠️ SIMILAR | Inconsistent naming |

**Status:** ⚠️ **NAMING INCONSISTENCY** - Using `check_*` vs `require_*` pattern

**What Actually Happens:**

- Python looks for `require_security_deposit`
- YAML defines `check_security_deposit`
- Mismatch causes default behavior (assumes True)
- Works but naming is inconsistent

---

### 6. Lease Options Check


| YAML Parameter                    | Python Expected             | Match? | Impact |
| --------------------------------- | --------------------------- | ------ | ------ |
| `check_renewal_options: true`     | `check_renewal_options`     | ✅ YES | Works  |
| `check_expansion_options: true`   | `check_expansion_options`   | ✅ YES | Works  |
| `check_termination_options: true` | `check_termination_options` | ✅ YES | Works  |

**Status:** ✅ **WORKING** - Parameter names match

---

### 7. Missing Rule Type Handlers

**YAML Defines These Rule Types (lease_agreement.yml):**

```yaml
- type: lease.fees        # ❌ NO HANDLER - SILENTLY IGNORED
- type: lease.default     # ❌ NO HANDLER - SILENTLY IGNORED
- type: lease.expenses    # ❌ NO HANDLER - SILENTLY IGNORED
```

**Python Handlers Available (contract_analyzer.py line 656-663):**

```python
handlers = {
    'lease.property': check_lease_property,
    'lease.tenant': check_lease_tenant,
    'lease.dates': check_lease_dates,
    'lease.rent': check_lease_rent,
    'lease.security': check_lease_security,
    'lease.options': check_lease_options,
    # ❌ lease.fees - NOT IMPLEMENTED
    # ❌ lease.default - NOT IMPLEMENTED
    # ❌ lease.expenses - NOT IMPLEMENTED
}
```

**What Happens:**

1. YAML defines 9 rule types for lease agreements
2. Python implements handlers for only 6 rule types
3. When `evaluate_custom_rules()` processes `lease.fees`, `lease.default`, or `lease.expenses`:
   ```python
   if rule_type in handlers:  # False for missing types
       handler = handlers[rule_type]
       finding = handler(text, rule_params, extraction)
       findings.append(finding)
   # If not in handlers, rule is SILENTLY SKIPPED - no error, no warning
   ```
4. **Result:** 3 out of 9 lease rules are completely ignored with no indication to the user

---

## Employment Agreement Similar Issues

**YAML Defines (employment.yml lines 19-35):**

```yaml
rules:
  - type: emp.notice         # ❌ NO HANDLER
  - type: emp.severance      # ❌ NO HANDLER
  - type: emp.noncompete     # ❌ NO HANDLER
  - type: emp.classification # ❌ NO HANDLER
  - type: emp.wage           # ❌ NO HANDLER
```

**Python Handlers Available:**

```python
handlers = {
    'lease.property': ...,
    'lease.tenant': ...,
    # ❌ NO 'emp.*' handlers implemented AT ALL
}
```

**Result:** **ALL employment-specific rules are silently ignored!** Only the 4 hardcoded compliance checks run (liability, contract value, fraud, jurisdiction).

---

## Why Rules Get Ignored: Technical Deep Dive

### Case 1: Rule Type Not in Handler Map

**Code Path:**

```python
# contract_analyzer.py line 638-675
def evaluate_custom_rules(text, rules_json, extraction):
    handlers = {
        'lease.property': check_lease_property,
        # ... only 6 handlers defined
    }

    findings = []
    for rule in rules_json:
        rule_type = rule.get('type')
        rule_params = rule.get('params', {})

        if rule_type in handlers:  # ⚠️ SILENT FAILURE POINT
            handler = handlers[rule_type]
            finding = handler(text, rule_params, extraction)
            findings.append(finding)
        # ❌ NO else clause - rules just disappear

    return findings
```

**What Goes Wrong:**

- Rule type `lease.fees` is encountered
- `'lease.fees' in handlers` evaluates to `False`
- Loop continues to next rule
- **No finding generated, no error logged, no warning to user**
- User has no idea the rule was skipped

---

### Case 2: Parameter Name Mismatch with Defaults

**Code Path:**

```python
# contract_analyzer.py line 494-506
def check_lease_dates(text, params, extraction):
    require_dates = params.get('require_lease_dates', True)  # ⚠️ ALWAYS True

    if not require_dates:
        return Finding(passed=True, details="Check not required")

    # Continue with check...
```

**What Goes Wrong:**

- YAML provides: `{"require_execution_date": true, "require_commencement_date": true, ...}`
- Python looks for: `params.get('require_lease_dates', True)`
- Key `'require_lease_dates'` doesn't exist in params dict
- Returns default value: `True`
- Function proceeds as if check is required
- **But uses generic logic instead of YAML-specified granular checks**

---

### Case 3: Fallback to Text Regex (Weak Validation)

**Code Path:**

```python
# contract_analyzer.py line 452-459
def check_lease_property(text, params, extraction):
    # ... extraction-based check first ...

    # Fallback: text search
    has_property_info = bool(re.search(r'(property|premises|leased premises)', text, re.IGNORECASE))
    return Finding(
        rule_id="lease.property",
        passed=has_property_info,
        details="Property information found in contract text." if has_property_info else "Property information not clearly identified.",
        citations=[]
    )
```

**What Goes Wrong:**

- If extraction data is unavailable or empty, falls back to simple regex
- Regex `(property|premises|leased premises)` is extremely broad
- Will match **ANY** occurrence of these common words
- **False positives:** Document mentions "property rights" or "intellectual property" → check passes
- **No actual validation** of property name or address as YAML intends
- User thinks rule is working, but it's just doing a keyword search

---

## How Extraction Data Saves Some Rules

### The Extraction Dependency

Many handlers check **extraction data first**, then fall back to text search:

```python
def check_lease_property(text, params, extraction):
    if extraction:  # ✅ BETTER PATH
        has_name = bool(extraction.property_name)
        has_address = bool(extraction.property_address)

        if has_name and has_address:
            return Finding(passed=True, details=f"Property: {extraction.property_name} at {extraction.property_address}")

    # ❌ FALLBACK PATH (weak)
    has_property_info = bool(re.search(r'(property|premises)', text, re.IGNORECASE))
    return Finding(passed=has_property_info, ...)
```

**Implications:**

1. **If LLM extraction works well:**

   - Handlers use `extraction.property_name`, `extraction.base_rent_amount`, etc.
   - Validation is **more accurate** (actual data vs keyword search)
   - Rules work **as intended** (mostly)
2. **If LLM extraction fails or is disabled:**

   - Handlers fall back to regex text search
   - Validation is **weak** (keyword matching)
   - High risk of **false positives**
   - Rules give **misleading results**
3. **If extraction fields don't exist in LeaseExtraction schema:**

   - Handler checks for non-existent field: `extraction.some_field` → `None`
   - Passes as `False`
   - Falls back to regex
   - **Expected behavior is lost**

---

## The Employment Agreement Problem

### Complete Handler Gap

**YAML Defines:**

```yaml
rules:
  - id: notice_period_required
    type: emp.notice
    params:
      require_notice_period: true

  - id: severance_terms_required
    type: emp.severance
    params:
      require_severance_terms: true

  - id: noncompete_scope_check
    type: emp.noncompete
    params:
      check_noncompete_scope: true

  - id: worker_classification_check
    type: emp.classification
    params:
      detect_worker_misclassification: true

  - id: wage_law_compliance
    type: emp.wage
    params:
      ensure_wage_law_compliance: true
```

**Python Handlers:**

```python
handlers = {
    'lease.property': check_lease_property,
    'lease.tenant': check_lease_tenant,
    'lease.dates': check_lease_dates,
    'lease.rent': check_lease_rent,
    'lease.security': check_lease_security,
    'lease.options': check_lease_options,
    # ❌ NO emp.* handlers
}
```

**Analysis Results:**


| Rule Type            | Handler Exists? | What Happens                                                 |
| -------------------- | --------------- | ------------------------------------------------------------ |
| `emp.notice`         | ❌ NO           | **Silently skipped** - notice period requirements ignored    |
| `emp.severance`      | ❌ NO           | **Silently skipped** - severance requirements ignored        |
| `emp.noncompete`     | ❌ NO           | **Silently skipped** - noncompete scope not checked          |
| `emp.classification` | ❌ NO           | **Silently skipped** - worker misclassification not detected |
| `emp.wage`           | ❌ NO           | **Silently skipped** - wage law compliance not verified      |

**User Experience:**

1. User uploads employment contract
2. User selects `employment_v1` rulepack
3. System runs analysis
4. Report shows only 4 findings:
   - Liability cap (hardcoded check)
   - Contract value (hardcoded check)
   - Fraud clause (hardcoded check)
   - Jurisdiction (hardcoded check)
5. **5 employment-specific rules produce ZERO findings**
6. **No error message, no warning**
7. User assumes document is compliant because no violations reported
8. **Critical employment terms are never actually checked**

---

## Why This Design Is Problematic

### 1. Silent Failures

**Problem:** Rules fail without any indication to the user.

**Example:**

```python
# No logging, no error tracking
for rule in rules_json:
    rule_type = rule.get('type')
    if rule_type in handlers:
        findings.append(handler(...))
    # ❌ Missing rule types just disappear
```

**Impact:**

- User creates carefully crafted rulepack with 10 rules
- Only 6 rules have handlers
- 4 rules silently ignored
- User sees 6 findings and thinks analysis is complete
- **False sense of compliance**

---

### 2. Parameter Name Brittleness

**Problem:** Exact parameter name matching required, no flexibility.

**Example:**

```python
require_dates = params.get('require_lease_dates', True)
# If YAML has 'require_dates' instead → ignored
# If YAML has 'dates_required' instead → ignored
# No validation, no suggestions, just silent default
```

**Impact:**

- YAML author must know exact parameter names Python expects
- No schema validation between YAML and Python
- Typos cause rules to use defaults instead of failing loudly
- **Documentation burden** - must maintain separate docs on parameter names

---

### 3. Hardcoded Handler Map

**Problem:** Adding new rule types requires code changes.

**Current Process:**

1. User wants to add `lease.utilities` rule type
2. Must write Python function: `def check_lease_utilities(...)`
3. Must add to handler map: `'lease.utilities': check_lease_utilities`
4. Must redeploy code
5. **Cannot add rule types via YAML alone**

**Impact:**

- Rule packs are **not fully data-driven**
- Business users cannot create new rule types
- Every new compliance requirement needs developer involvement
- **Limits flexibility and extensibility**

---

### 4. Weak Fallback Validation

**Problem:** Regex fallbacks are too permissive.

**Example:**

```python
# This will match almost anything
has_property_info = bool(re.search(r'(property|premises|leased premises)', text, re.IGNORECASE))
```

**False Positives:**

- "This agreement covers intellectual property rights" → Passes property check ❌
- "Premises liability is excluded" → Passes premises check ❌
- "Lessee's property insurance requirements" → Passes property check ❌

**Impact:**

- Rules pass when they shouldn't
- **False sense of compliance**
- Defeats purpose of automated compliance checking

---

### 5. Extraction Data Dependency

**Problem:** Rule accuracy depends on LLM extraction quality.

**Chain of Failures:**

```
LLM extraction fails
    ↓
extraction = None or empty fields
    ↓
Handler falls back to regex
    ↓
Weak validation (false positives)
    ↓
Misleading compliance report
```

**Impact:**

- Rule reliability is **inconsistent**
- Same rule might work well on one document, fail on another
- No way to know if extraction-based path or fallback path was used
- **Unpredictable behavior**

---

## Summary of Issues by Rule Type

### Lease Agreement Rules (9 defined, 6 implemented)


| Rule Type        | Status               | Issue                                                                                        |
| ---------------- | -------------------- | -------------------------------------------------------------------------------------------- |
| `lease.property` | ✅**Working**        | Parameter names match                                                                        |
| `lease.tenant`   | ✅**Working**        | Parameter names match                                                                        |
| `lease.dates`    | ⚠️**Partial**      | YAML params ignored (execution_date, commencement_date, expiration_date), uses generic logic |
| `lease.rent`     | ⚠️**Partial**      | YAML params ignored (base_rent, payment_frequency), uses generic logic                       |
| `lease.security` | ⚠️**Naming Issue** | `check_security_deposit` vs `require_security_deposit` inconsistency                         |
| `lease.options`  | ✅**Working**        | Parameter names match                                                                        |
| `lease.fees`     | ❌**Missing**        | No handler - silently ignored                                                                |
| `lease.default`  | ❌**Missing**        | No handler - silently ignored                                                                |
| `lease.expenses` | ❌**Missing**        | No handler - silently ignored                                                                |

**Effective Coverage:** 6/9 rules (66%) - **3 rules completely ignored**

---

### Employment Agreement Rules (5 defined, 0 implemented)


| Rule Type            | Status        | Issue                         |
| -------------------- | ------------- | ----------------------------- |
| `emp.notice`         | ❌**Missing** | No handler - silently ignored |
| `emp.severance`      | ❌**Missing** | No handler - silently ignored |
| `emp.noncompete`     | ❌**Missing** | No handler - silently ignored |
| `emp.classification` | ❌**Missing** | No handler - silently ignored |
| `emp.wage`           | ❌**Missing** | No handler - silently ignored |

**Effective Coverage:** 0/5 rules (0%) - **ALL employment-specific rules ignored**

---

## What Actually Works

### Tier 1: Hardcoded Compliance Checks (Always Work)

These **always execute** regardless of rulepack:

1. **Liability Cap Check** (`check_liability_cap_present_and_within_bounds`)

   - Searches for "Limitation of Liability" section
   - Extracts monetary caps or "12 months of fees" references
   - Validates against `rules.liability_cap.max_cap_amount` and `max_cap_multiplier`
   - **Status:** ✅ Robust, well-tested
2. **Contract Value Check** (`check_contract_value_within_limit`)

   - Finds largest monetary amount in document
   - Validates against `rules.contract.max_contract_value`
   - **Status:** ✅ Works reliably
3. **Fraud Clause Check** (`check_fraud_clause_present_and_assigned`)

   - Searches for fraud/misrepresentation clauses
   - Validates liability assignment to "other party"
   - **Status:** ✅ Works but heuristic-based
4. **Jurisdiction Check** (`check_jurisdiction_present_and_allowed`)

   - Extracts jurisdiction from "Governing Law" section
   - Validates against `rules.jurisdiction.allowed_countries`
   - **Status:** ✅ Reliable with good regex

---

### Tier 2: Custom Rules That Work (With Caveats)

**Working Lease Rules:**

- `lease.property` - ✅ If extraction has `property_name` and `property_address`
- `lease.tenant` - ✅ If extraction has `tenant_legal_name`
- `lease.options` - ✅ If extraction has renewal/expansion option fields

**Degraded Lease Rules:**

- `lease.dates` - ⚠️ Generic date keyword check (ignores YAML granularity)
- `lease.rent` - ⚠️ Generic rent keyword check (ignores payment frequency requirement)
- `lease.security` - ⚠️ Works but naming inconsistent

---

## Root Cause Analysis

### Why Was It Designed This Way?

**Hypothesis:** Incremental development without full specification

1. **Phase 1:** Built 4 hardcoded compliance checks for common contract requirements
2. **Phase 2:** Added custom rule dispatching for lease-specific checks
3. **Phase 3:** Created YAML rulepacks with detailed requirements
4. **Phase 4 (Missing):** Never aligned YAML schemas with Python handler expectations

**Result:**

- Python handlers were built with **assumed parameter names**
- YAML rulepacks were created with **different parameter names**
- No validation layer to catch mismatches
- No comprehensive testing with real rulepacks
- **System evolved into inconsistent state**

---

## Impact on Users

### Scenario 1: New User Creates Lease Rulepack

**Steps:**

1. User reads `_TEMPLATE.yml`
2. User creates `my_lease.yml` with custom rules:
   ```yaml
   rules:
     - type: lease.fees
       params:
         require_late_fee_terms: true
     - type: lease.default
       params:
         require_default_terms: true
   ```
3. User imports rulepack via MCP tool
4. User analyzes lease document
5. User sees only standard compliance findings
6. **User doesn't know `lease.fees` and `lease.default` were ignored**

**Expected Behavior:** Error message: "Rule type 'lease.fees' not supported"
**Actual Behavior:** Silent failure, no indication

---

### Scenario 2: User Analyzes Employment Contract

**Steps:**

1. User selects `employment_v1` rulepack
2. System auto-detects employment contract
3. Analysis runs
4. Report shows 4 findings (liability, contract value, fraud, jurisdiction)
5. **All 5 employment-specific rules produce zero findings**
6. User assumes employment contract is compliant

**Expected Behavior:**

- Either implement `emp.*` handlers
- Or show warning: "5 rules skipped: emp.notice, emp.severance, emp.noncompete, emp.classification, emp.wage"

**Actual Behavior:** Silent failure, misleading compliance report

---

### Scenario 3: User Specifies Granular Date Requirements

**YAML:**

```yaml
- type: lease.dates
  params:
    require_execution_date: true
    require_commencement_date: true
    require_expiration_date: true
```

**What User Expects:**

- Check must verify all 3 dates are present
- Extraction should include all 3 dates
- Failure if any date missing

**What Actually Happens:**

- Python ignores these 3 parameters
- Uses default `require_lease_dates = True`
- Only checks commencement and expiration (execution date ignored)
- Falls back to regex `(commencement|expiration|term)` if extraction unavailable
- **Execution date requirement never enforced**

---

## Recommendations (For Understanding, Not Implementation)

### 1. Add Comprehensive Logging

**Current Problem:** Silent failures
**Solution:** Log every rule evaluation decision

```python
import logging
logger = logging.getLogger(__name__)

for rule in rules_json:
    rule_type = rule.get('type')
    if rule_type in handlers:
        logger.info(f"Evaluating rule: {rule_type} (id: {rule.get('id')})")
        finding = handler(...)
        findings.append(finding)
    else:
        logger.warning(f"⚠️ Rule type '{rule_type}' not implemented - skipping rule '{rule.get('id')}'")
```

**Benefit:** Users see which rules were skipped

---

### 2. Validate YAML Against Handler Expectations

**Current Problem:** Parameter name mismatches go undetected
**Solution:** Schema validation on import

```python
def validate_rule_params(rule_type: str, params: dict):
    """Validate that params match handler expectations."""
    expected_params = {
        'lease.dates': ['require_execution_date', 'require_commencement_date', 'require_expiration_date'],
        'lease.rent': ['require_base_rent', 'require_payment_frequency'],
        # ...
    }

    if rule_type in expected_params:
        actual_params = set(params.keys())
        expected = set(expected_params[rule_type])

        if actual_params != expected:
            # Warn about unexpected or missing params
            pass
```

**Benefit:** Catch configuration errors at import time, not runtime

---

### 3. Implement Missing Handlers

**Current Problem:** 8 rule types defined but not implemented
**Solution:** Implement or deprecate

**Missing for Lease:**

- `lease.fees` (late fees, penalties)
- `lease.default` (default provisions)
- `lease.expenses` (CAM charges, operating expenses)

**Missing for Employment:**

- `emp.notice` (termination notice periods)
- `emp.severance` (severance terms)
- `emp.noncompete` (non-compete scope)
- `emp.classification` (worker classification)
- `emp.wage` (wage law compliance)

**Benefit:** Rules actually work as documented

---

### 4. Standardize Parameter Naming

**Current Problem:** Inconsistent `require_*` vs `check_*` patterns
**Solution:** Unified naming convention

**Proposal:**

- Boolean flags: `require_[field_name]` (e.g., `require_base_rent`)
- Validation rules: `validate_[check_name]` (e.g., `validate_cap_amount`)
- Detection rules: `detect_[issue]` (e.g., `detect_misclassification`)

**Benefit:** Predictable, self-documenting parameter names

---

### 5. Add Rule Evaluation Metadata to Reports

**Current Problem:** No visibility into which rules ran
**Solution:** Include rule evaluation summary

```markdown
## Rules Evaluated

✅ 6 rules passed
❌ 2 rules failed
⚠️ 3 rules skipped (not implemented)

### Skipped Rules:
- `lease.fees` (late_fee_terms) - Handler not implemented
- `lease.default` (default_provisions) - Handler not implemented
- `lease.expenses` (operating_expenses) - Handler not implemented
```

**Benefit:** Users understand what was actually checked

---

### 6. Make Handlers Data-Driven

**Current Problem:** Hardcoded handler map requires code changes
**Solution:** Generic rule evaluation engine

**Vision:**

```yaml
# Define evaluation logic in YAML
- type: lease.fees
  evaluation:
    extraction_fields:
      - late_fee_percentage
      - grace_period
    text_patterns:
      - "late charge|late fee|late payment"
    required: true
```

**Benefit:** New rule types can be added without code changes

---

## Conclusion

### Key Takeaways

1. **System is partially functional:**

   - 4 hardcoded compliance checks work well
   - 6 lease-specific handlers work (with caveats)
   - 0 employment-specific handlers work
2. **Primary failure mode is silent:**

   - Missing handlers → rules skipped without warning
   - Parameter mismatches → defaults used instead of YAML values
   - Weak fallbacks → false positives mask real issues
3. **YAML rulepacks are not fully respected:**

   - Parameter names don't match Python expectations
   - Many rule types have no implementation
   - Granular requirements get ignored
4. **Extraction data is critical:**

   - Rules work well when LLM extraction succeeds
   - Rules degrade to weak regex when extraction fails
   - No visibility into which code path was used

### What Users Should Know

**For Lease Agreements:**

- ✅ Property, tenant, and options checks **work** (if extraction succeeds)
- ⚠️ Date and rent checks **partially work** (generic validation only)
- ❌ Fees, default, and expenses checks **don't work** (no handlers)

**For Employment Agreements:**

- ✅ Standard compliance checks **work** (liability, fraud, jurisdiction, contract value)
- ❌ ALL employment-specific checks **don't work** (no handlers implemented)

**General Advice:**

- **Don't rely on custom rules** without verifying handler exists
- **Check handler map** in `contract_analyzer.py` line 656-663 before creating YAML rules
- **Review extraction data** to ensure handlers have data to work with
- **Test with known-compliant and known-violating documents** to verify rules work as expected

---

**Document End**
**Analysis Complete**
**No code changes made - understanding only**
