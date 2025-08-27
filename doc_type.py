
# doc_type.py
import re
from typing import Optional
from schemas import RulePack

def compile_title_hints(packs: dict[str, RulePack]) -> list[tuple[re.Pattern, str]]:
    hints: list[tuple[re.Pattern, str]] = []
    for pack in packs.values():
        for name in pack.doc_type_names:
            hints.append((re.compile(rf"\b{name}\b", re.IGNORECASE), pack.id))
    return hints

def guess_doc_type_id(text: str, packs: dict[str, RulePack]) -> Optional[str]:
    head = (text or "")[:4000]
    for rx, pack_id in compile_title_hints(packs):
        if rx.search(head):
            return pack_id
    return None  # runner will fall back to default pack
