# Lease Agreement Rulepack

## Overview

This directory contains the lease agreement rulepack for ContractExtract, designed to extract comprehensive information from commercial lease agreements following the standard Manager Abstract format.

## Files

- **lease_agreement.yml** - The main rulepack configuration file
- **02 Manager Abstract - Lease Agreement.xls** - Reference template showing all 118 standard lease fields

## Rulepack Details

**ID:** `lease_agreement_v1`
**Schema Version:** 1.0
**Document Types:** Lease Agreement, Commercial Lease, Rental Agreement, Lease Contract, Lease Abstract

## Extracted Information Categories

The rulepack extracts information across the following categories:

### 1. Property Information (4 fields)
- Property Name
- Property Address
- Property ID/Number
- Suite Number

### 2. Tenant Information (7 fields)
- Tenant legal name and entity type
- Billing address
- Contact details (name, phone, fax, email)

### 3. Lease Dates (4+ fields)
- Execution Date
- Commencement Date
- Expiration Date
- Possession Date

### 4. Rent Terms (6+ fields)
- Base Rent Amount (monthly)
- Rent Start Date
- Rent Escalation (CPI adjustments, fixed increases)
- CPI Index details
- Annual caps on increases

### 5. Recovery Charges (4 fields)
- CAM (Common Area Maintenance)
- Real Estate Taxes
- Insurance Recovery
- Sales Tax Rate

### 6. Additional Charges (5+ fields)
- Overtime HVAC
- Parking
- Storage
- Utilities (electricity, water, etc.)

### 7. Security & Deposits (9 fields)
- Security Deposit Amount
- Letter of Credit details
- Bank information
- Dates (issue, maturity, expiration)

### 8. Late Fees & Default (4 fields)
- Late Fee Calculation Type
- Default Percentage
- Grace Period
- Holdover Charges

### 9. Percentage Rent (4 fields)
- Required status
- Sales reporting requirements
- Percentage rate
- Breakpoint amount

### 10. Lease Options (7 types)
- Renewal Options
- Right of First Refusal (ROFR)
- Right of First Offer (ROFO)
- Expansion Options
- Contraction Rights
- Termination Options
- Relocation Rights

### 11. Special Rights (8 types)
- Building Naming Rights
- Roof Access
- Signage Rights
- Telecommunications
- Antenna/Dish Rights
- Conference Center Access
- Emergency Generator
- Fitness Center Access

### 12. Tenant Obligations (4+ fields)
- Repair & Maintenance Requirements
- Insurance Requirements
- Service Request Markup
- Advanced Rent

### 13. Landlord Obligations (3 fields)
- Landlord Improvements (TI allowance)
- Landlord Fees
- Amortization Terms

### 14. Assignment & Subletting (3 fields)
- Assignment Rights
- Subletting Rights
- Consent Requirements

### 15. Legal & Compliance (8 fields)
- Audit Rights
- Credit Review
- Guarantor Information
- Financial Requirements
- OFAC Requirements
- Estoppel Certificates
- Subordination & Non-Disturbance

### 16. Notices (3 fields)
- Landlord Notice Address
- Tenant Notice Address
- Notice Requirements

### 17. Commission (3 fields)
- Broker Name(s)
- Commission Amount
- Commission Terms

### 18. Other Terms (3+ fields)
- Rent Concessions/Abatements
- Month-to-Month Terms
- Amendment Information

## Total Fields Covered

**118 standard commercial lease fields** covering all aspects of lease agreements from basic property and tenant information to complex financial terms, rights, and obligations.

## Usage

### 1. Import to Database

```bash
python mcp_server.py
# Use MCP tool: create_rulepack_from_yaml
# Or use HTTP API: POST /rule-packs/upload-yaml
```

### 2. Copy to rules_packs Directory

```bash
cp lease_agreement.yml ../rules_packs/
```

### 3. Validate YAML

```bash
# Use MCP tool: validate_rulepack_yaml
# Or use HTTP API: POST /rule-packs/validate
```

### 4. Test with Sample Lease

Upload a sample commercial lease agreement through:
- **Frontend:** http://localhost:5173/upload
- **API:** POST /preview-run with file upload
- **LibreChat:** Via MCP tool `analyze_document`

## Extraction Output Format

The rulepack extracts information with structured attributes:

```yaml
- label: base_rent
  span: "$15,000.00 per month"
  attributes:
    amount: 15000
    currency: "USD"
    frequency: "monthly"

- label: renewal_options
  span: "two (2) options to renew for five (5) year terms"
  attributes:
    number_of_options: 2
    term_years: 5
    notice_months: 6
```

## Compliance Focus

The rulepack focuses on these key compliance areas:

1. **Financial Terms** - Complete rent, escalation, and expense tracking
2. **Critical Dates** - All lease commencement, expiration, and option dates
3. **Security** - Deposits, letters of credit, financial guarantees
4. **Rights & Options** - Renewal, expansion, termination, ROFR/ROFO
5. **Obligations** - Both tenant and landlord responsibilities
6. **Legal Requirements** - Default provisions, compliance, assignments

## Notes

- Based on standard Manager Abstract format used in commercial real estate
- Covers all major lease types: office, retail, industrial, multi-family
- Designed for both new leases and amendments
- Supports various rent structures: gross, net, modified gross, triple net (NNN)
- Handles complex escalation clauses: CPI, fixed, stepped, percentage

## References

- Original template: `02 Manager Abstract - Lease Agreement.xls`
- Schema version: 1.0 (ContractExtract)
- Commercial real estate industry standard fields

---

**Created:** 2025-11-20
**Status:** Ready for testing
**Next Steps:** Import to database, test with sample leases, refine based on results