"""
Export utilities for lease extraction data.
Provides CSV and Excel export functionality for LeaseExtraction objects.
"""

import csv
from typing import List, Dict
from pathlib import Path

from infrastructure import LeaseExtraction


def lease_extraction_to_row(extraction: LeaseExtraction) -> Dict[str, str]:
    """
    Convert LeaseExtraction object to flat dictionary for CSV export.

    Args:
        extraction: LeaseExtraction object to convert

    Returns:
        Dictionary with human-readable column names and values
    """
    return {
        # Property Information
        "Property Name": extraction.property_name or "",
        "Property Address": extraction.property_address or "",
        "Property Type": extraction.property_type or "",
        "Square Footage": extraction.property_square_footage or "",
        "Zoning": extraction.property_zoning or "",

        # Tenant Information
        "Tenant Legal Name": extraction.tenant_legal_name or "",
        "Tenant Trade Name": extraction.tenant_trade_name or "",
        "Tenant Address": extraction.tenant_address or "",
        "Tenant Contact Person": extraction.tenant_contact_person or "",
        "Tenant Phone": extraction.tenant_phone or "",
        "Tenant Email": extraction.tenant_email or "",

        # Landlord Information
        "Landlord Legal Name": extraction.landlord_legal_name or "",
        "Landlord Address": extraction.landlord_address or "",
        "Landlord Contact Person": extraction.landlord_contact_person or "",
        "Landlord Phone": extraction.landlord_phone or "",
        "Landlord Email": extraction.landlord_email or "",

        # Important Dates
        "Lease Commencement Date": extraction.lease_commencement_date or "",
        "Lease Expiration Date": extraction.lease_expiration_date or "",
        "Lease Term (Months)": extraction.lease_term_months or "",
        "Rent Commencement Date": extraction.rent_commencement_date or "",
        "Option to Renew Deadline": extraction.option_to_renew_deadline or "",
        "Notice to Vacate (Days)": extraction.notice_to_vacate_days or "",

        # Rent and Financial Terms
        "Base Rent Amount": extraction.base_rent_amount or "",
        "Base Rent Frequency": extraction.base_rent_frequency or "",
        "Rent Increase Percentage": extraction.rent_increase_percentage or "",
        "Rent Increase Frequency": extraction.rent_increase_frequency or "",
        "CAM Charges (Monthly)": extraction.cam_charges_monthly or "",
        "CAM Charges (Annual)": extraction.cam_charges_annual or "",
        "Real Estate Tax Responsibility": extraction.real_estate_tax_responsibility or "",
        "Insurance Responsibility": extraction.insurance_responsibility or "",
        "Utilities Responsibility": extraction.utilities_responsibility or "",

        # Security and Deposits
        "Security Deposit Amount": extraction.security_deposit_amount or "",
        "Security Deposit Held By": extraction.security_deposit_held_by or "",
        "Additional Deposit Amount": extraction.additional_deposit_amount or "",
        "Deposit Return (Days)": extraction.deposit_return_days or "",

        # Options and Rights
        "Option to Renew Terms": extraction.option_to_renew_terms or "",
        "Option to Expand": extraction.option_to_expand or "",
        "Right of First Refusal": extraction.right_of_first_refusal or "",
        "Sublease Allowed": extraction.sublease_allowed or "",
        "Assignment Allowed": extraction.assignment_allowed or "",

        # Use and Restrictions
        "Permitted Use": extraction.permitted_use or "",
        "Prohibited Uses": extraction.prohibited_uses or "",
        "Exclusive Use Clause": extraction.exclusive_use_clause or "",
        "Operating Hours": extraction.operating_hours or "",
        "Signage Rights": extraction.signage_rights or "",

        # Maintenance and Repairs
        "Landlord Maintenance Obligations": extraction.landlord_maintenance_obligations or "",
        "Tenant Maintenance Obligations": extraction.tenant_maintenance_obligations or "",
        "Structural Repair Responsibility": extraction.structural_repair_responsibility or "",
        "HVAC Maintenance Responsibility": extraction.hvac_maintenance_responsibility or "",

        # Insurance and Liability
        "General Liability Coverage Required": extraction.general_liability_coverage_required or "",
        "Property Insurance Required": extraction.property_insurance_required or "",
        "Additional Insured Requirement": extraction.additional_insured_requirement or "",

        # Default and Termination
        "Default Notice (Days)": extraction.default_notice_days or "",
        "Cure Period (Days)": extraction.cure_period_days or "",
        "Late Payment Grace Period": extraction.late_payment_grace_period or "",
        "Late Payment Penalty": extraction.late_payment_penalty or "",
        "Early Termination Rights": extraction.early_termination_rights or "",

        # Special Provisions
        "Force Majeure Clause": extraction.force_majeure_clause or "",
        "Casualty Damage Provisions": extraction.casualty_damage_provisions or "",
        "Condemnation Provisions": extraction.condemnation_provisions or "",
        "Estoppel Certificate Requirement": extraction.estoppel_certificate_requirement or "",
        "Subordination Clause": extraction.subordination_clause or "",

        # Parking and Access
        "Parking Spaces Allocated": extraction.parking_spaces_allocated or "",
        "Parking Type": extraction.parking_type or "",
        "Common Area Access": extraction.common_area_access or "",
    }


def export_single_lease_to_csv(extraction: LeaseExtraction, output_path: str):
    """
    Export single lease extraction to CSV file.

    Args:
        extraction: LeaseExtraction object to export
        output_path: Path to output CSV file
    """
    row = lease_extraction_to_row(extraction)
    fieldnames = list(row.keys())

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(row)


def export_multiple_leases_to_csv(extractions: List[LeaseExtraction], output_path: str):
    """
    Export multiple lease extractions to CSV file.

    Args:
        extractions: List of LeaseExtraction objects to export
        output_path: Path to output CSV file
    """
    if not extractions:
        return

    rows = [lease_extraction_to_row(ext) for ext in extractions]
    fieldnames = list(rows[0].keys())

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def export_multiple_leases_to_excel(extractions: List[LeaseExtraction], output_path: str):
    """
    Export multiple lease extractions to Excel file.

    Args:
        extractions: List of LeaseExtraction objects to export
        output_path: Path to output Excel file

    Requires:
        pandas library (optional dependency)
    """
    try:
        import pandas as pd
    except ImportError:
        raise ImportError(
            "pandas is required for Excel export. Install with: pip install pandas openpyxl"
        )

    if not extractions:
        return

    rows = [lease_extraction_to_row(ext) for ext in extractions]
    df = pd.DataFrame(rows)

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    df.to_excel(output_file, index=False, engine='openpyxl')


__all__ = [
    'lease_extraction_to_row',
    'export_single_lease_to_csv',
    'export_multiple_leases_to_csv',
    'export_multiple_leases_to_excel',
]
