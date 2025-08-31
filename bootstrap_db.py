# bootstrap_db.py
import os
from pathlib import Path
from db import init_db, SessionLocal
from yaml_importer import import_rulepack_yaml
from rulepack_repo import publish_pack

def main():
    # If you didn't set DATABASE_URL elsewhere, set it here:
    os.environ.setdefault(
        "DATABASE_URL",
        "postgresql+psycopg2://postgres:1219@localhost:5432/contractextract"
    )

    # 1) Create tables if missing
    init_db()

    # 2) Import YAML → draft (adjust path if needed)
    yaml_path = Path("rules_packs/strategic_alliance.yml")
    if not yaml_path.exists():
        raise FileNotFoundError(f"Missing {yaml_path} — put your YAML there.")

    with SessionLocal() as db:
        draft = import_rulepack_yaml(db, yaml_path.read_text(encoding="utf-8"), created_by="bootstrap")
        # 3) Publish the draft so main.py can load it
        pub = publish_pack(db, pack_id=draft.id, version=draft.version)
        print(f"Published: {pub.id}@{pub.version} ({pub.status})")

if __name__ == "__main__":
    main()
