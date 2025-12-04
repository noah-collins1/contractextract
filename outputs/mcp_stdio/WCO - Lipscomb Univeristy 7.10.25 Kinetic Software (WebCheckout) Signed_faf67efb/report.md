# Contract Analysis Report

## 1. Document Metadata

- **File name:** WCO - Lipscomb Univeristy 7.10.25 Kinetic Software (WebCheckout) Signed
- **Document ID:** N/A
- **Classified type:** SaaS Agreement
- **Rulepack used:** saas_msa_v1 (SaaS Agreement)
- **Analysis date:** 2025-12-04T06:49:18.325123+00:00
- **Overall result:** ❌ FAIL

---

## 2. Executive Summary

This SaaS Agreement has an overall risk level of High. Key issues include: Fraud Clause Present And Assigned: No 'fraud' mention found; Jurisdiction Present And Allowed: Governing law/jurisdiction detected as "to be
unenforceable for any reason, such provision will be changed and interpreted to accomplish the objectives of such
provision to the greatest extent possible under applicable law and the remaining provisions hereof shall be
unaffected and remain in full force and effect.". Not in allowed list. The agreement appears to be governed by to be
unenforceable for any reason, such provision will be changed and interpreted to accomplish the objectives of such
provision to the greatest extent possible under applicable law and the remaining provisions hereof shall be
unaffected and remain in full force and effect..

- **Overall risk level:** 🟠 High
- **Key concerns:**
  - Fraud Clause Present And Assigned: No 'fraud' mention found
  - Jurisdiction Present And Allowed: Governing law/jurisdiction detected as "to be
unenforceable for any reason, such provision will be changed and interpreted to accomplish the objectives of such
provision to the greatest extent possible under applicable law and the remaining provisions hereof shall be
unaffected and remain in full force and effect.". Not in allowed list
  - Low uptime commitments expose the customer to unacceptable service downtime, potentially disrupting business operations.

---

## 3. Preliminary Extraction (Base Fields)

These fields are extracted for every document, regardless of rulepack.

- **Document type (inferred):** SaaS Agreement
- **Parties involved:** WebCheckout and
Client, shall be the subject of a separate agreement between the parties for development services. Client
acknowledges that WebCheckout makes available a single general release of the SaaS and shall have complete
control of the design and development of the SaaS, including with respect to any enhancements or modifications.
- **Length / duration of contract:** Not clearly specified
- **Fees & payment terms (summary):** Contract value approximately $8,500.00
- **Terms of termination (summary):** No clear termination clause identified
- **Jurisdiction (extracted):** to be
unenforceable for any reason, such provision will be changed and interpreted to accomplish the objectives of such
provision to the greatest extent possible under applicable law and the remaining provisions hereof shall be
unaffected and remain in full force and effect.

> **Citations:** None collected

---

## 4. Preliminary Compliance Checks

These core compliance rules are evaluated for every document.

| Check | Status | Severity | Finding |
|-------|--------|----------|---------|
| Jurisdiction allowed | ❌ FAIL | High | Governing law/jurisdiction detected as "to be unenforceable for any reason, such provision will be changed and interpreted to accomplish th… |
| Liability cap within allowed bounds | ✅ PASS | High | Found explicit monetary cap candidate: 101.00. [auto-guard: numeric citations lacked currency context or referenced shares/units] |
| Fraud / willful misconduct carve-out | ❌ FAIL | High | No 'fraud' mention found. |
| Contract value within limit | ✅ PASS | Medium | No max contract value configured; skipping. |

> **Citations:**  
> - Jurisdiction allowed: p. 5
> - Liability cap within allowed bounds: p. 3
> - Fraud / willful misconduct carve-out: None
> - Contract value within limit: None

---

## 5. Rulepack Evaluation (SaaS Agreement)

### 5.1 Summary

- **Rulepack ID:** saas_msa_v1
- **Matched doc type:** SaaS Agreement
- **Total rules evaluated:** 6
- **Pass / Fail / Info:** 1 / 5 / 0

### 5.2 Detailed Rules

| Rule | Status | Severity | Finding |
|------|--------|----------|---------|
| Uptime Commitment Meets Minimum | ❌ FAIL | High | Uptime commitment is below 99.9% or not specified. |
| Auto-Renewal Term Reasonable | ✅ PASS | Medium | Auto-renewal term is 12 months or less, or not specified. |
| Termination for Convenience Allowed | ❌ FAIL | Medium | Termination for convenience requires more than 90 days notice or is not allowed. |
| Customer Data Ownership Confirmed | ❌ FAIL | High | Customer data ownership is not clearly stated. |
| Data Retention Period Specified | ❌ FAIL | Medium | Post-termination data retention period is not specified. |
| Security Standards Documented | ❌ FAIL | Medium | No security standards or certifications are documented. |

---

## 6. Extracted Key Terms

- **Service Description:** _Not specified_
- **Uptime Commitment (%):** _Not specified_
- **Support Response Time:** _Not specified_
- **Data Retention Period:** _Not specified_
- **Auto-Renewal Term (Months):** _Not specified_
- **Termination Notice Period (Days):** _Not specified_
- **Customer Data Ownership:** _Not specified_
- **Security Standards:** _Not specified_
- **Payment Terms:** _Not specified_

---

## 7. Risks & Recommendations

### 7.1 Top Risks

1. **Fraud Clause Present And Assigned:** No 'fraud' mention found

2. **Jurisdiction Present And Allowed:** Governing law/jurisdiction detected as "to be
unenforceable for any reason, such provision will be changed and interpreted to accomplish the objectives of such
provision to the greatest extent possible under applicable law and the remaining provisions hereof shall be
unaffected and remain in full force and effect.". Not in allowed list

3. **Uptime Commitment Meets Minimum:** Uptime commitment is below 99.9% or not specified

4. **Termination for Convenience Allowed:** Termination for convenience requires more than 90 days notice or is not allowed

5. **Customer Data Ownership Confirmed:** Customer data ownership is not clearly stated


### 7.2 Recommendations

_The following recommendations are AI-generated and should be reviewed by legal counsel._

**For Fraud Clause Present And Assigned:** Insert a fraud clause in Section 1.3 of the contract, stating that 'Client shall not engage in any fraudulent activity while using the Software' and assign it to WebCheckout.

**For Jurisdiction Present And Allowed:** Replace the governing law/jurisdiction provision with a clear and specific statement, such as 'This Agreement shall be governed by and construed in accordance with the laws of the State of Pennsylvania, without giving effect to any principles of conflicts of law.'

**For Uptime Commitment Meets Minimum:** Add a uptime commitment clause in Section 1.2, stating that WebCheckout guarantees an uptime of at least 99.9% for the Software, and specify the method of measurement (e.g., 'Uptime shall be measured using [insert method]')

**For Termination for Convenience Allowed:** Modify the termination provision to allow for termination with a notice period of no more than 30 days, stating that 'Either party may terminate this Agreement upon thirty (30) days' written notice to the other party.'

**For Customer Data Ownership Confirmed:** Insert a data ownership clause in Section 2.3, stating that 'Client retains all rights, title, and interest in and to its Data, including any intellectual property rights, and WebCheckout shall not claim or assert any ownership over such Data' and specify the definition of 'Data'

---

## 8. Appendix: Citations

This section groups all citations by the report section where they appear.

### Section 3: Preliminary Extraction

1. Chars 0–147: "otiated and agreed to between WebCheckout and Client, shall be the subject of a separate agreement between the parties for development services...."

2. Chars 0–149: "zed Users” mean Client’s employees or independent contractors working within their job responsibilities or engagement by Client or other end user for"

3. Chars 0–149: "explicitly stated in this Agreement. 5. Term and Termination. 5.1 Term. This Agreement shall commence on the Effective Date and continue for a term o"

### Section 4: Preliminary Compliance Checks

1. **[Liability Cap Present And Within Bounds]** Page 3, Lines 27–45: "on, or the configuration of Client’s computer systems, may prevent, interrupt or delay Client’s access to the SaaS or data stored within the SaaS. Web…"

2. **[Jurisdiction Present And Allowed]** Page 5, Lines 15–18: "t regard to conflicts of law principles. 12.2 Severability. If any provision of this Agreement is held by a court of competent jurisdiction to be unen…"

---

_Page and line numbers are computed from the PDF text extraction layout._
