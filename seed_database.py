#!/usr/bin/env python3
"""
Seed the database with rule packs from YAML files
Run this to populate the database with initial rule packs
"""

import sys
from pathlib import Path
from infrastructure import init_db, SessionLocal
from rulepack_manager import import_rulepack_yaml, publish_pack, list_packs

def seed_rulepacks():
    """Load all YAML rule packs into the database"""

    print("\n" + "=" * 60)
    print("SEEDING DATABASE WITH RULE PACKS")
    print("=" * 60)

    # Initialize database
    print("\n1. Initializing database...")
    init_db()
    print("   [OK] Database initialized")

    # Find all YAML files
    rules_dir = Path("rules_packs")
    yaml_files = list(rules_dir.glob("*.yml"))
    yaml_files = [f for f in yaml_files if f.name != "_TEMPLATE.yml"]  # Skip template

    print(f"\n2. Found {len(yaml_files)} rule pack files:")
    for f in yaml_files:
        print(f"   - {f.name}")

    # Import each YAML file
    print("\n3. Importing rule packs...")
    imported = []
    failed = []

    with SessionLocal() as db:
        for yaml_file in yaml_files:
            try:
                print(f"\n   Importing: {yaml_file.name}")

                # Read YAML content
                yaml_content = yaml_file.read_text(encoding='utf-8')

                # Import as draft
                result = import_rulepack_yaml(db, yaml_content, created_by="seed_script")
                pack_id = result.id
                version = result.version

                print(f"   [OK] Imported as draft: {pack_id} v{version}")

                # Publish immediately
                publish_result = publish_pack(db, pack_id, version)
                print(f"   [OK] Published to active: {pack_id} v{version}")

                imported.append(f"{pack_id} v{version}")

            except Exception as e:
                print(f"   [FAIL] Failed: {e}")
                failed.append((yaml_file.name, str(e)))

    # Summary
    print("\n" + "=" * 60)
    print("IMPORT SUMMARY")
    print("=" * 60)
    print(f"\n[OK] Successfully imported and published: {len(imported)}")
    for pack in imported:
        print(f"   - {pack}")

    if failed:
        print(f"\n[FAIL] Failed to import: {len(failed)}")
        for filename, error in failed:
            print(f"   - {filename}: {error}")

    # Verify database state
    print("\n" + "=" * 60)
    print("DATABASE STATUS")
    print("=" * 60)

    with SessionLocal() as db:
        all_packs = list_packs(db)  # Returns list of RulePackRead objects
        active_packs = [p for p in all_packs if p.status == "active"]

        print(f"\nTotal rule packs: {len(all_packs)}")
        print(f"Active rule packs: {len(active_packs)}")

        if active_packs:
            print("\nActive rule packs:")
            for pack in active_packs:
                print(f"   - {pack.id} v{pack.version}: {', '.join(pack.doc_type_names)}")

    print("\n" + "=" * 60)

    if len(imported) == len(yaml_files):
        print("[SUCCESS] All rule packs loaded and activated.")
        print("\nYou can now:")
        print("  1. Test in LibreChat: 'call get_system_info'")
        print("  2. Analyze documents: 'use analyze_document with text...'")
        print("=" * 60)
        return 0
    else:
        print("[WARNING] Some rule packs failed to import. Check errors above.")
        print("=" * 60)
        return 1

if __name__ == "__main__":
    try:
        exit_code = seed_rulepacks()
        sys.exit(exit_code)
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
