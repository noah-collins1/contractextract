# rule_registry.py
from pathlib import Path
from dataclasses import dataclass
from typing import List
import yaml
from schemas import RuleSet

@dataclass
class RulePack:
    id: str
    doc_type_names: List[str]
    rules: RuleSet
    prompt: str
    examples: list  # list[dict] with {text, extractions:[{label, span, attributes}]}

def load_rulepacks(dir_path: str = "rules_packs") -> list[RulePack]:
    packs: list[RulePack] = []
    for p in Path(dir_path).glob("*.y*ml"):
        raw = yaml.safe_load(p.read_text(encoding="utf-8"))
        rules = RuleSet(
            jurisdiction={"allowed_countries": raw["jurisdiction_allowlist"]},
            liability_cap=raw.get("liability_cap", {}),
            contract=raw.get("contract", {}),
            fraud=raw.get("fraud", {}),
        )
        packs.append(
            RulePack(
                id=raw["id"],
                doc_type_names=raw.get("doc_type_names", []),
                rules=rules,
                prompt=raw["prompt"],
                examples=raw.get("examples", []),
            )
        )
    if not packs:
        raise RuntimeError("No rule packs found in rules_packs/. Add at least one .yml file.")
    return packs
