#!/usr/bin/env python3
"""
Quick script to add schema_version and fix string formatting in all YAML files
"""

import re
from pathlib import Path

def fix_yaml_file(file_path: Path):
    """Add schema_version and fix string formatting in a YAML file."""
    print(f"Fixing {file_path.name}...")

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Add schema_version after id if not present
    if 'schema_version:' not in content:
        content = re.sub(
            r'^(id: \S+)$',
            r'\1\nschema_version: "1.0"',
            content,
            flags=re.MULTILINE
        )

    # Fix unquoted doc_type_names entries
    content = re.sub(
        r'^(\s+-\s+)([^"]\S.*[^"])$',
        r'\1"\2"',
        content,
        flags=re.MULTILINE
    )

    # Fix jurisdiction_allowlist entries
    content = re.sub(
        r'^(\s+-\s+)([^"]\S.*[^"])$',
        r'\1"\2"',
        content,
        flags=re.MULTILINE
    )

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

def main():
    rules_dir = Path(__file__).parent / "rules_packs"
    yaml_files = list(rules_dir.glob("*.yml"))

    # Skip template and already fixed files
    skip_files = {"_TEMPLATE.yml", "strategic_alliance.yml", "employment.yml", "noncompete.yml"}

    for yaml_file in yaml_files:
        if yaml_file.name in skip_files:
            print(f"Skipping {yaml_file.name} (already fixed)")
            continue

        fix_yaml_file(yaml_file)

    print("Done! Run validate_yaml_rulepacks.py to check results.")

if __name__ == "__main__":
    main()