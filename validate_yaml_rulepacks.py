#!/usr/bin/env python3
"""
YAML RulePack Validation Script
Validates all YAML files in rules_packs/ against the canonical schema.
"""

import yaml
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, ValidationError

# Standard schema fields that must be present
REQUIRED_FIELDS = {
    "id": str,
    "schema_version": str,
    "doc_type_names": list,
    "jurisdiction_allowlist": list,
    "liability_cap": dict,
    "contract": dict,
    "fraud": dict,
    "prompt": str,
    "examples": list,
}

OPTIONAL_FIELDS = {
    "rules": list,
    "notes": str,
    "extensions": dict,
    "extensions_schema": dict,
}

def validate_yaml_structure(yaml_content: Dict[str, Any], filename: str) -> List[str]:
    """Validate YAML structure against the standard schema."""
    errors = []

    # Check required fields
    for field, expected_type in REQUIRED_FIELDS.items():
        if field not in yaml_content:
            errors.append(f"Missing required field: {field}")
        elif not isinstance(yaml_content[field], expected_type):
            errors.append(f"Field '{field}' should be {expected_type.__name__}, got {type(yaml_content[field]).__name__}")

    # Validate specific field constraints
    if "liability_cap" in yaml_content:
        cap = yaml_content["liability_cap"]
        required_cap_fields = ["max_cap_amount", "max_cap_multiplier"]
        for cap_field in required_cap_fields:
            if cap_field not in cap:
                errors.append(f"liability_cap missing required field: {cap_field}")

    if "contract" in yaml_content:
        contract = yaml_content["contract"]
        if "max_contract_value" not in contract:
            errors.append("contract missing required field: max_contract_value")

    if "fraud" in yaml_content:
        fraud = yaml_content["fraud"]
        required_fraud_fields = ["require_fraud_clause", "require_liability_on_other_party"]
        for fraud_field in required_fraud_fields:
            if fraud_field not in fraud:
                errors.append(f"fraud missing required field: {fraud_field}")

    # Validate doc_type_names
    if "doc_type_names" in yaml_content:
        doc_types = yaml_content["doc_type_names"]
        if not doc_types or len(doc_types) == 0:
            errors.append("doc_type_names cannot be empty")
        for doc_type in doc_types:
            if not isinstance(doc_type, str):
                errors.append(f"doc_type_names entries must be strings, got {type(doc_type).__name__}")

    # Validate examples structure
    if "examples" in yaml_content:
        examples = yaml_content["examples"]
        if not isinstance(examples, list):
            errors.append("examples must be a list")
        else:
            for i, example in enumerate(examples):
                if not isinstance(example, dict):
                    errors.append(f"examples[{i}] must be a dict")
                    continue
                if "text" not in example:
                    errors.append(f"examples[{i}] missing required field: text")
                if "extractions" not in example:
                    errors.append(f"examples[{i}] missing required field: extractions")

    return errors

def validate_yaml_file(file_path: Path) -> Dict[str, Any]:
    """Validate a single YAML file."""
    result = {
        "file": str(file_path),
        "valid": True,
        "errors": [],
        "warnings": []
    }

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            yaml_content = yaml.safe_load(f)

        if yaml_content is None:
            result["valid"] = False
            result["errors"].append("YAML file is empty or invalid")
            return result

        # Validate structure
        structure_errors = validate_yaml_structure(yaml_content, file_path.name)
        result["errors"].extend(structure_errors)

        # Check for template compliance
        if file_path.name != "_TEMPLATE.yml":
            # Check schema version
            schema_version = yaml_content.get("schema_version")
            if schema_version != "1.0":
                result["warnings"].append(f"Schema version '{schema_version}' may not be compatible with current template")

            # Check if all jurisdiction entries are strings
            if "jurisdiction_allowlist" in yaml_content:
                jurisdictions = yaml_content["jurisdiction_allowlist"]
                for j in jurisdictions:
                    if not isinstance(j, str):
                        result["errors"].append(f"jurisdiction_allowlist entries must be strings, got {type(j).__name__}")

        if result["errors"]:
            result["valid"] = False

    except yaml.YAMLError as e:
        result["valid"] = False
        result["errors"].append(f"YAML parsing error: {e}")
    except Exception as e:
        result["valid"] = False
        result["errors"].append(f"Unexpected error: {e}")

    return result

def main():
    """Main validation function."""
    rules_dir = Path(__file__).parent / "rules_packs"

    if not rules_dir.exists():
        print(f"ERROR: Rules directory not found: {rules_dir}")
        sys.exit(1)

    yaml_files = list(rules_dir.glob("*.yml")) + list(rules_dir.glob("*.yaml"))

    if not yaml_files:
        print("No YAML files found in rules_packs directory")
        sys.exit(1)

    print(f"Validating {len(yaml_files)} YAML files...")
    print("=" * 60)

    all_valid = True
    results = []

    for yaml_file in sorted(yaml_files):
        result = validate_yaml_file(yaml_file)
        results.append(result)

        # Print immediate results
        status = "VALID" if result["valid"] else "INVALID"
        print(f"{status}: {yaml_file.name}")

        if result["errors"]:
            for error in result["errors"]:
                print(f"  ERROR: {error}")

        if result["warnings"]:
            for warning in result["warnings"]:
                print(f"  WARNING: {warning}")

        if result["errors"] or result["warnings"]:
            print()

        if not result["valid"]:
            all_valid = False

    # Summary
    print("=" * 60)
    valid_count = sum(1 for r in results if r["valid"])
    total_count = len(results)

    print(f"SUMMARY: {valid_count}/{total_count} files are valid")

    if all_valid:
        print("All YAML files are valid!")
        sys.exit(0)
    else:
        print("Some YAML files have validation errors")
        sys.exit(1)

if __name__ == "__main__":
    main()