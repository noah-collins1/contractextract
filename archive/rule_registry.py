from __future__ import annotations
from pathlib import Path
from typing import List, Optional
import yaml

from sqlalchemy import select
from db import Base, get_engine, session_scope
from rulepack_orm import RulePackORM
from schemas import RuleSet, RulePack, ExampleItem, ExampleExtraction

# --- DB init ---
def init_db():
    engine = get_engine()
    Base.metadata.create_all(engine)

# --- Conversions ---
def orm_to_pyd(orm: RulePackORM) -> RulePack:
    rules = RuleSet.parse_obj(orm.rules or {})
    examples = [ExampleItem.parse_obj(e) for e in (orm.examples or [])]
    return RulePack(
        id=orm.id,
        doc_type_names=list(orm.doc_type_names or []),
        rules=rules,
        prompt=orm.prompt or "",
        examples=examples,
    )

def pyd_to_orm_fields(p: RulePack) -> dict:
    return {
        "id": p.id,
        "doc_type_names": list(p.doc_type_names or []),
        "rules": p.rules.dict(),
        "prompt": p.prompt or "",
        "examples": [e.dict() for e in (p.examples or [])],
    }

# --- YAML bootstrap (optional) ---
def _load_yaml_file(path: Path) -> RulePack:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    rules = RuleSet(
        jurisdiction={"allowed_countries": raw.get("jurisdiction_allowlist", [])},
        liability_cap=raw.get("liability_cap", {}),
        contract=raw.get("contract", {}),
        fraud=raw.get("fraud", {}),
    )
    examples = []
    for e in raw.get("examples", []) or []:
        exs = [ExampleExtraction(**ex) for ex in e.get("extractions", [])]
        examples.append(ExampleItem(text=e.get("text",""), extractions=exs))
    return RulePack(
        id=raw["id"],
        doc_type_names=raw.get("doc_type_names", []),
        rules=rules,
        prompt=raw.get("prompt",""),
        examples=examples,
    )

def bootstrap_from_yaml(dir_path: str = "rules_packs") -> List[RulePack]:
    packs: List[RulePack] = []
    for p in Path(dir_path).glob("*.y*ml"):
        packs.append(_load_yaml_file(p))
    return packs

# --- CRUD ---
def create_rulepack(p: RulePack) -> RulePack:
    with session_scope() as s:
        if s.get(RulePackORM, p.id):
            raise ValueError(f"RulePack id '{p.id}' already exists")
        s.add(RulePackORM(**pyd_to_orm_fields(p)))
    return p

def upsert_rulepack(p: RulePack) -> RulePack:
    with session_scope() as s:
        existing = s.get(RulePackORM, p.id)
        if existing:
            for k,v in pyd_to_orm_fields(p).items():
                setattr(existing, k, v)
        else:
            s.add(RulePackORM(**pyd_to_orm_fields(p)))
    return p

def get_rulepack(rulepack_id: str) -> Optional[RulePack]:
    with session_scope() as s:
        orm = s.get(RulePackORM, rulepack_id)
        return orm_to_pyd(orm) if orm else None

def list_rulepacks() -> List[RulePack]:
    with session_scope() as s:
        rows = s.execute(select(RulePackORM)).scalars().all()
        return [orm_to_pyd(r) for r in rows]

def update_rulepack(rulepack_id: str, data: dict) -> RulePack:
    with session_scope() as s:
        orm = s.get(RulePackORM, rulepack_id)
        if not orm:
            raise ValueError(f"RulePack '{rulepack_id}' not found")
        current = orm_to_pyd(orm)
        updated = current.copy(update=data)
        for k,v in pyd_to_orm_fields(updated).items():
            setattr(orm, k, v)
        return updated

def delete_rulepack(rulepack_id: str) -> bool:
    with session_scope() as s:
        orm = s.get(RulePackORM, rulepack_id)
        if not orm:
            return False
        s.delete(orm)
        return True

# --- Public loader used by pipeline ---
def load_rulepacks(dir_path: str = "rules_packs", bootstrap: bool = True) -> List[RulePack]:
    """
    Returns all rule packs from the database. If the table is empty and
    bootstrap=True, will seed from YAML files in dir_path.
    """
    init_db()
    packs = list_rulepacks()
    if packs or not bootstrap:
        return packs
    seed = bootstrap_from_yaml(dir_path)
    for p in seed:
        upsert_rulepack(p)
    return list_rulepacks()