# rulepack_loader.py
from typing import Dict, List
from sqlalchemy.orm import Session
from schemas import RulePack as RuntimeRulePack
from rulepack_repo import load_active_rulepacks
from doc_type import guess_doc_type_id

def load_packs_for_runtime(db: Session) -> Dict[str, RuntimeRulePack]:
    packs = load_active_rulepacks(db)
    return {p.id: p for p in packs}

def select_pack_for_text(db: Session, text: str) -> RuntimeRulePack:
    packs = load_active_rulepacks(db)
    by_id = {p.id: p for p in packs}
    # use existing guesser (regex on doc_type_names)
    pack_id = guess_doc_type_id(text, by_id) or (packs[0].id if packs else None)
    if not pack_id:
        raise RuntimeError("No active rule packs available")
    return by_id[pack_id]
