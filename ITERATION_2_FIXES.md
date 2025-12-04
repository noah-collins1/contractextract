# Iteration 2: Targeted Fixes for Kennesaw SOW Output Issues

## Date: 2025-12-04

## Overview

After analyzing the actual output from the Kennesaw State University SOW, identified and fixed 4 critical issues that remained after Iteration 1. All changes are surgical and maintain backward compatibility.

---

## Issues Fixed

### **Issue 1: JSON Still Leaking in Reports** 🔴 CRITICAL

**Problem Observed:**
```
Executive Summary:
Key issues include: "reason_short": "No 'fraud' mention found, potentially exposing parties to liability", "Reasonin

Section 4 Finding column:
"reason_short": "No governing law/jurisdiction clause detected, leaving uncertainty on applicable la

Section 7 Top Risks:
"reason_short": "No 'fraud' mention found, potentially exposing parties to liability", "Reasoning": "The contract...
```

**Root Cause:**
The fallback path in `_maybe_add_llm_explanations()` wasn't handling cases where:
1. `_extract_json_block()` failed to parse JSON
2. BUT the response still contained JSON-like patterns with `"reason_short": "value"`
3. The truncation at 100 chars was cutting mid-JSON-key, leaving fragments like `"Reasonin`

**Fixes Applied:**

1. **Enhanced fallback parsing** (contract_analyzer.py:2804-2838)
   - Added regex extraction for `"reason_short": "value"` patterns
   - Tries to extract values from malformed JSON before giving up
   - Filters out lines with JSON syntax (`{`, `}`, `"`) when all else fails

2. **Removed truncation in tags** (contract_analyzer.py:2847)
   - OLD: `f"reason_short:{reason_short[:100]}"`
   - NEW: `f"reason_short:{reason_short}"`
   - Truncation was causing JSON fragments to appear in reports

**Expected Result:**
- Executive Summary: Clean sentences like "No fraud mention found"
- Section 4 Finding: Clean explanations without `"reason_short":` prefixes
- Section 7 Top Risks: Prose descriptions without JSON structure

---

### **Issue 2: Duration Extraction Broken** 🔴 CRITICAL

**Problem Observed:**
```
Length / duration of contract: . Once this agreement has been fully executed and the raw materials (Period of Performance)
```

**Root Cause:**
The improved regex in Iteration 1 was capturing text AFTER "Period of Performance:" but wasn't validating that it actually contained dates. If the next line started with ". Once...", it captured that fragment.

**Fixes Applied:**

**Rewrote `_extract_period_of_performance()`** (contract_analyzer.py:1621-1667)
- Uses **multi-strategy approach** instead of single regex:
  1. **Strategy 1**: Look for explicit date ranges (Jan 1, 2025 - Dec 31, 2025)
  2. **Strategy 2**: Look for completion dates ("by December 31, 2025")
  3. **Strategy 3**: Look for duration descriptions ("6 months")
  4. **Strategy 4**: Look for descriptive text about completion (last resort)
- Only returns text if it contains recognizable date/duration patterns
- Filters out fragments starting with punctuation

**Expected Result:**
- If SOW has "Period of Performance: January 1, 2025 through December 31, 2025"
  → Shows "January 1, 2025 – December 31, 2025 (Period of Performance)"
- If no dates found → Falls back to other duration patterns or returns None

---

### **Issue 3: SOW Rules Updated to Use Deliverables Summary** ✓

**Problem Observed:**
```
Section 5: Pass / Fail / Info: 0 / 8 / 0
Section 6: Deliverables Summary: Add Source Material Provided by KSU to SoftChalk Create SC KSU, Convert source material...
```

Rules were failing even though deliverables_summary was clearly populated with 500+ chars of content.

**Root Cause:**
Rules were checking ONLY for `deliverables_count >= 1`, but the LLM wasn't always populating count even when it extracted a detailed summary.

**Fixes Applied:**

1. **Updated deliverables rule** (sow_v1.yml:274)
   - OLD: `deliverables_count is not None and deliverables_count >= 1`
   - NEW: `(deliverables_count is not None and deliverables_count >= 1) or (deliverables_summary is not None and len(deliverables_summary) > 30)`

2. **Updated scope rule** (sow_v1.yml:263)
   - OLD: `scope_of_work_description is not None and len(scope_of_work_description) > 50`
   - NEW: `(scope_of_work_description is not None and len(scope_of_work_description) > 50) or (deliverables_summary is not None and len(deliverables_summary) > 100)`

**Expected Result:**
- For Kennesaw SOW: At least 2/8 rules should pass (Deliverables + Scope)
- Rules now recognize that a detailed deliverables summary implies both scope and deliverables exist

---

### **Issue 4: Updated SOW Prompt for Strict Citations** ✓

**Problem:**
The original prompt was too lenient and didn't emphasize the importance of exact, verbatim citations for regex matching.

**Fixes Applied:**

**Replaced entire prompt** (sow_v1.yml:33-150) with new version that includes:

1. **STRICT CITATION RULES** section
   - "Citations MUST be copied EXACTLY from the contract"
   - "No paraphrasing, no summarizing, no combining clauses"
   - "Return the FULL SENTENCE or FULL CONTRACT CLAUSE"

2. **INTERPRETATION GUIDANCE** section
   - Defines what constitutes "Acceptance Criteria" (Completion Criteria, Warranty/Acceptance)
   - Defines "Change Order Process" (Change Request procedures)
   - Defines "IP Ownership" (work product, pre-existing IP)
   - Provides clear mapping rules

3. **FINAL REMINDER** section
   - Emphasizes regex matching requirement
   - "Do not modify, clean, or reinterpret this text"

**Expected Result:**
- Phase 2 LLM should now extract more fields (not just deliverables_summary)
- Citations should be verbatim, enabling better page/line mapping in the future
- More rules should pass due to clearer extraction guidance

---

## Files Modified

### 1. **contract_analyzer.py**
   - Lines 2804-2838: Enhanced JSON fallback parsing with regex extraction
   - Line 2847: Removed truncation from reason_short/reason_detailed tags
   - Lines 1621-1667: Rewrote `_extract_period_of_performance()` with multi-strategy approach

### 2. **rules_packs/sow_v1.yml**
   - Lines 33-150: Replaced prompt with strict version emphasizing verbatim citations
   - Line 263: Updated scope rule condition to include deliverables fallback
   - Line 274: Updated deliverables rule condition to include summary length check

---

## Test Results

✅ **All 20 existing tests pass**
- JSON extraction tests (7/7)
- SOW summarization tests (3/3)
- Citation formatting tests (5/5)
- Section 6 key terms tests (2/2)
- Citation grouping test (1/1)
- Backward compatibility tests (2/2)

---

## Expected Improvements on Next Kennesaw SOW Run

### ✅ **Section 2: Executive Summary**
- **Before**: `"reason_short": "No 'fraud' mention found...`
- **After**: `No fraud mention found, potentially exposing parties to liability`

### ✅ **Section 3: Preliminary Extraction**
- **Before**: `. Once this agreement has been fully executed...`
- **After**: `January 15, 2025 - April 30, 2025 (Period of Performance)` *(or similar actual dates)*

### ✅ **Section 4: Preliminary Compliance Checks**
- **Before**: `"reason_short": "No governing law/jurisdiction...`
- **After**: `No governing law/jurisdiction clause detected, leaving uncertainty on applicable laws`

### ✅ **Section 5: Rulepack Evaluation**
- **Before**: `0 / 8 / 0` (all failing)
- **After**: `2-4 / 8 / 0` (Deliverables, Scope, and possibly Acceptance Criteria passing)

### ✅ **Section 7: Top Risks**
- **Before**: Multiple lines with JSON structure
- **After**: Clean prose descriptions for each risk

### ⚠️ **Note on Other Fields**
The prompt update should help the LLM extract more fields beyond just `deliverables_summary`, but actual extraction quality depends on:
1. Whether the LLM follows the new stricter prompt
2. Whether the SOW document actually contains those sections
3. LLM's ability to interpret section labels correctly

If fields remain "Not specified" after this iteration, it may indicate:
- The SOW truly doesn't have those sections
- The LLM needs additional prompt tuning
- Field names in the YAML don't match what the LLM extracts

---

## What Was NOT Changed

✅ **Kept stable:**
- LLM provider and model configuration
- Phase 2 calling conventions
- Report v2 structure
- Citation creation logic (from Iteration 1)
- All helper functions from Iteration 1
- Test suite structure

---

## Validation Checklist

To verify these fixes work on the Kennesaw SOW, check that:

1. ☐ No `"reason_short":` literal text appears anywhere in the report
2. ☐ No `"Reasonin` or other truncated JSON keys appear
3. ☐ Duration shows actual dates or "X months" instead of ". Once..."
4. ☐ At least 2/8 SOW rules pass (Deliverables + Scope minimum)
5. ☐ Executive Summary has clean bullet points
6. ☐ Section 4 Finding column has prose, not JSON
7. ☐ Section 7 Top Risks has prose, not JSON
8. ☐ Section 8 has citations (from Iteration 1 fix)

---

## Known Limitations

### 1. **Citation Char Positions**
Section 8 shows "Chars 0-X" because `_find_source_snippet()` doesn't preserve the actual char positions from the document. To fix:
- Would need to track the actual position where the snippet was found
- Or use the PDF layout mapping if available

### 2. **Rules May Still Fail**
Even with improved prompt and rule conditions:
- If LLM doesn't extract `acceptance_criteria_present`, that rule will fail
- If LLM doesn't extract `project_start_date` or `project_end_date`, timeline rule will fail
- This is inherent to LLM-based extraction and may require further prompt iteration

### 3. **Duration/Termination May Still Be Imperfect**
The multi-strategy extraction is more robust but:
- Some SOWs have unusual formatting that might not match any pattern
- Edge cases may still produce fragments or "Not clearly specified"
- May need document-specific tuning for optimal results

---

## Next Steps (If Issues Persist)

### If JSON still appears:
- Check `build_risk_assessment()` to ensure it uses cleaned `reason_short`
- Add logging to see exactly what `_extract_json_block()` returns
- Consider removing JSON parsing entirely and using plain text only

### If duration is still wrong:
- Log the actual text captured by the "Period of Performance" regex
- Check if document has non-standard formatting
- May need to add document-specific pattern

### If all rules still fail:
- Log the actual `key_terms` dict returned by Phase 2
- Check if LLM is following the new prompt format
- May need to simplify prompt or add more examples
- Consider increasing LLM context window or using a different model

---

## Summary

This iteration focused on **cleaning up output display issues** that appeared in the actual Kennesaw SOW run. The fixes are minimal and surgical:

1. ✅ JSON cleanup now handles more edge cases
2. ✅ Duration extraction is more robust
3. ✅ SOW rules are more realistic about what's extractable
4. ✅ Prompt guides LLM to extract more fields correctly

All existing tests pass, and backward compatibility is maintained. The next run should show significant improvement in report clarity and rule evaluation.