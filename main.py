# main.py — local runner with Postgres rule packs + doc-type detection + optional concurrency
from __future__ import annotations

import os, re, json, time, hashlib, logging, shutil, sys
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from telemetry import go_quiet
import langextract as lx
import pydantic
from ingest import ingest
from llm_factory import load_provider
import os
os.environ["ENABLE_LLM_EXPLANATIONS"] = "1"

from evaluator import make_report, save_markdown, save_txt
from doc_type import guess_doc_type_id

# DB loader (active packs from Postgres)
from db import SessionLocal, init_db
from rulepack_loader import load_packs_for_runtime
from schemas import RulePack as RuntimeRulePack, ExampleItem, ExampleExtraction


# --- UTF-8 + version sanity at boot ---
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("PYTHONUTF8", "1")
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

print(f"[boot] Pydantic: {pydantic.__version__}")
print(f"[boot] Stdout encoding: {sys.stdout.encoding}")

# ------------------------------
# Silence noisy telemetry
# ------------------------------
go_quiet()

# ------------------------------
# Tunables (env)  # [ADDED]
# ------------------------------
MAX_CHAR_BUFFER = int(os.getenv("CE_MAX_CHAR_BUFFER", "1500"))         # for provider.extract
MAX_WORKERS_EXTRACT = int(os.getenv("CE_MAX_WORKERS_EXTRACT", "1"))    # per-call extract workers
CHUNK_TARGET = int(os.getenv("CE_CHUNK_TARGET", "9000"))               # [ADDED] chunk target size (chars)

# ------------------------------
# Path & write guards
# ------------------------------
def ensure_file_path_is_clear(out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    data_path = out_dir / "data.jsonl"
    if data_path.exists() and data_path.is_dir():
        shutil.rmtree(data_path)
    return data_path

def safe_out_dir(outputs_dir: Path, raw_name: str) -> Path:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", raw_name)[:50]
    h = hashlib.sha1(raw_name.encode("utf-8")).hexdigest()[:8]
    return outputs_dir / f"{stem}-{h}"

# ---------- helpers to coerce entities → extraction-like dicts  # [ADDED]
def _entity_to_extraction_dict(ent) -> dict:
    """
    Try to robustly map an 'entity' (object or dict) into an extraction-like dict:
    {label, span, attributes}
    """
    if hasattr(ent, "to_dict"):
        d = ent.to_dict()
    elif isinstance(ent, dict):
        d = ent
    else:
        # last-ditch introspection
        d = {
            "label": getattr(ent, "label", None) or getattr(ent, "type", None) or "entity",
            "text": getattr(ent, "text", None) or getattr(ent, "value", None) or "",
            "span": getattr(ent, "span", None) or "",
        }
    label = d.get("label") or d.get("type") or "entity"
    span = d.get("span") or ""
    text_val = d.get("text") or d.get("value") or ""
    attrs = d.get("attributes") or {}
    if text_val and "text" not in attrs:
        attrs = {**attrs, "text": text_val}
    return {"label": label, "span": span, "attributes": attrs}

def _doc_has_any_extractions_or_entities(doc) -> bool:  # [ADDED]
    if isinstance(doc, dict):
        return bool(doc.get("extractions")) or bool(doc.get("entities"))
    return bool(getattr(doc, "extractions", None) or getattr(doc, "entities", None))

def has_extractions(result) -> bool:
    try:
        # support both object-with-attr and dict-with-key  # [CHANGED]
        docs = _to_docs(result)
        if not docs:
            # also consider top-level entities-only shape
            if isinstance(result, dict) and result.get("entities"):
                return True
            if getattr(result, "entities", None):
                return True
            return False
        # each doc can be an object or dict; look for extractions OR entities  # [CHANGED]
        for d in docs:
            if _doc_has_any_extractions_or_entities(d):
                return True
        return False
    except Exception:
        return False

# ------------------------------
# Robust JSONL saver (UTF-8; handles corpus or single doc)
# ------------------------------
def _to_docs(result):  # [CHANGED]
    # Handle dict merges
    if isinstance(result, dict):
        if "documents" in result:
            return list(result["documents"] or [])
        # top-level entity-only payload → wrap into single doc
        if "entities" in result and result["entities"]:
            return [{"text": result.get("text", ""), "entities": result["entities"]}]
    # Objects with .documents
    if hasattr(result, "documents"):
        return list(getattr(result, "documents") or [])
    # Single AnnotatedDocument
    AD = getattr(lx.data, "AnnotatedDocument", None)
    if AD and isinstance(result, AD):
        return [result]
    # Objects that expose top-level entities
    if getattr(result, "entities", None):
        return [{"text": getattr(result, "text", ""), "entities": list(getattr(result, "entities"))}]
    # Already a list
    if isinstance(result, (list, tuple)):
        return list(result)
    return []

def save_jsonl_utf8(result, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "data.jsonl"
    docs = _to_docs(result)
    count = 0

    def _norm_extraction_dict(dct_or_obj) -> dict:
        """
        Normalize any extraction/entity-like object or dict into a plain dict:
          { "label": str, "span": str|list|tuple, "attributes": dict }
        No .to_dict() calls (works across langextract versions).
        """
        if isinstance(dct_or_obj, dict):
            d = dct_or_obj
        else:
            d = {
                "label": getattr(dct_or_obj, "label", None) or getattr(dct_or_obj, "type", None) or "entity",
                "span": getattr(dct_or_obj, "span", None) or "",
                "attributes": getattr(dct_or_obj, "attributes", None) or {},
                "text": getattr(dct_or_obj, "text", None) or getattr(dct_or_obj, "value", None) or "",
            }

        label = d.get("label") or d.get("type") or "entity"
        span = d.get("span", "")
        attrs = d.get("attributes") or {}
        txt = d.get("text") or d.get("value")
        if txt and "text" not in attrs:
            attrs = {**attrs, "text": txt}
        return {"label": label, "span": span, "attributes": attrs}

    with open(path, "w", encoding="utf-8", errors="replace") as f:
        for d in docs:
            # Obtain text and a list of extraction-like items (from either extractions or entities)
            if isinstance(d, dict):
                text_val = d.get("text", "")
                ex_list = d.get("extractions")
                if ex_list is None:
                    ents = d.get("entities") or []
                    ex_list = [_norm_extraction_dict(ent) for ent in ents]
                else:
                    ex_list = [_norm_extraction_dict(ex) for ex in (ex_list or [])]
            else:
                text_val = getattr(d, "text", "")
                raw_extractions = getattr(d, "extractions", None)
                if raw_extractions is not None:
                    ex_list = [_norm_extraction_dict(e) for e in (raw_extractions or [])]
                else:
                    ents = getattr(d, "entities", None) or []
                    ex_list = [_norm_extraction_dict(ent) for ent in ents]

            # Ensure normalized dicts only
            norm_ex = [_norm_extraction_dict(ex) for ex in (ex_list or [])]
            doc_dict = {"text": text_val, "extractions": norm_ex}
            f.write(json.dumps(doc_dict, ensure_ascii=False) + "\n")
            count += 1

    print(f"[INFO] Wrote {count} docs to {path}")
    return path



# Small debug helper  # [ADDED]
def print_doc_stats(tag: str, result):
    docs = _to_docs(result)
    n = len(docs)
    k = 0
    for d in docs:
        if _doc_has_any_extractions_or_entities(d):
            k += 1
    print(f"[debug] {tag}: docs={n}, docs_with_extractions_or_entities={k}")

# ------------------------------
# Simple sanity fallback (regex) if model returns nothing
# ------------------------------
# old sanity check rules, specific to Strategic Alliance
##TITLE_RE = re.compile(r"STRATEGIC ALLIANCE AGREEMENT", re.IGNORECASE)
##PARTY_RE = re.compile(r"(ChipMOS TECHNOLOGIES INC\.|Tsinghua Unigroup Ltd\.)", re.IGNORECASE)

def run_sanity_rules(text: str):
    """
    Minimal, pack-agnostic fallback: if the model returns nothing,
    emit a couple of generic extractions so downstream artifacts aren’t empty.
    """
    import langextract as lx
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    title_guess = (lines[0][:120] if lines else "Document")
    ex = [
        lx.data.Extraction("document_title_guess", title_guess),
    ]
    return lx.data.AnnotatedDocument(text=text, extractions=ex)

# ------------------------------
# Helpers for examples
# ------------------------------
def _as_lx_examples(example_items) -> list:
    """
    Accepts pack.examples either as Pydantic objects or dicts and returns a list of lx.data.ExampleData.
    """
    lx_examples = []
    for e in example_items or []:
        # support both dict and Pydantic ExampleItem
        text = e["text"] if isinstance(e, dict) else getattr(e, "text", "")
        exs = e["extractions"] if isinstance(e, dict) else getattr(e, "extractions", [])
        ex_objs = []
        for ex in exs or []:
            if isinstance(ex, dict):
                label = ex.get("label", "")
                span = ex.get("span", "")
                attrs = ex.get("attributes", {}) or {}
            else:
                label = getattr(ex, "label", "")
                span = getattr(ex, "span", "")
                attrs = getattr(ex, "attributes", {}) or {}
            ex_objs.append(lx.data.Extraction(label, span, attributes=attrs))
        lx_examples.append(lx.data.ExampleData(text=text, extractions=ex_objs))
    return lx_examples

# ------------------------------
# Chunking & merge helpers  # [ADDED]
# ------------------------------
def chunk_by_pages(text: str, target_size: int = 9000) -> list[str]:
    """
    Split on form-feed (\f) page breaks (preserved by ingest.py),
    merging adjacent pages up to ~target_size chars.
    """
    pages = (text or "").split("\f")
    if len(pages) <= 1:
        return [text]
    chunks, buf = [], ""
    for p in pages:
        nxt = (buf + "\n" + p) if buf else p
        if len(nxt) <= target_size:
            buf = nxt
        else:
            if buf:
                chunks.append(buf)
            buf = p
    if buf:
        chunks.append(buf)
    return chunks

def merge_extractions(results) -> dict:
    """
    Merge a list of per-chunk results into a single corpus-like dict
    that our saver/visualizer understands.
    """
    docs = []
    for r in results:
        docs.extend(_to_docs(r))
    return {"documents": docs}

# ------------------------------
# Per-document worker (safe for ProcessPool)
# ------------------------------
def process_document(name: str, text: str, pack_dict: dict, outputs_dir_str: str) -> tuple[str, str, str]:
    """
    Reconstruct pack from dict, run local extraction + evaluation, save artifacts.
    Returns (name, pack_id, out_dir_str).
    """
    # Reconstruct RuntimeRulePack (works whether dict came from Pydantic .dict() or similar)
    pack = RuntimeRulePack.parse_obj(pack_dict)

    # Local provider only (ollama or whatever llm.yaml says)
    provider = load_provider("llm.yaml")

    out_dir = safe_out_dir(Path(outputs_dir_str), name)
    ensure_file_path_is_clear(out_dir)

    # Build examples for LangExtract
    lx_examples = _as_lx_examples(pack.examples)

    try:
        # --- Page-chunking + per-chunk extract ---  # [ADDED]
        chunks = chunk_by_pages(text, target_size=CHUNK_TARGET)
        print(f"[debug] chunking: {len(chunks)} chunk(s) (target={CHUNK_TARGET})")  # [ADDED]

        chunk_results = []
        for i, ch in enumerate(chunks, 1):
            res = provider.extract(
                text_or_documents=ch,
                prompt=pack.prompt or "",
                examples=lx_examples,
                extraction_passes=1,
                max_workers=MAX_WORKERS_EXTRACT,
                max_char_buffer=MAX_CHAR_BUFFER,
            )
            chunk_results.append(res)

        # --- Merge all chunk results into one ---  # [ADDED]
        result = merge_extractions(chunk_results)
        print_doc_stats("post-merge", result)  # [ADDED]

        # Fallback to sanity rules if empty
        if not has_extractions(result):
            print(f"[WARN] No extractions/entities for {name}; using sanity rules fallback.")  # [CHANGED]
            result = run_sanity_rules(text)
            print_doc_stats("fallback", result)  # [ADDED]

        # Save JSONL
        save_jsonl_utf8(result, out_dir)

        # Visualize
        try:
            vis = lx.visualize(str(out_dir / "data.jsonl"))
            with open(out_dir / "review.html", "w", encoding="utf-8", errors="replace") as f:
                f.write(vis if isinstance(vis, str) else vis.data)
        except Exception as viz_e:
            (out_dir / "_viz_error.txt").write_text(str(viz_e), encoding="utf-8", errors="replace")

        # Evaluate & save reports
        report = make_report(document_name=name, text=text, rules=pack.rules)
        save_markdown(report, out_dir)
        save_txt(report, out_dir)

        print(f"✓ Finished {name} (pack: {pack.id})")
        return (name, pack.id, str(out_dir))

    except Exception as e:
        # Degrade gracefully
        print(f"[ERROR] {name}: {e} — writing fallback artifacts.")
        (out_dir / "_error.txt").write_text(str(e), encoding="utf-8", errors="replace")

        fb = run_sanity_rules(text)
        save_jsonl_utf8(fb, out_dir)
        try:
            vis = lx.visualize(str(out_dir / "data.jsonl"))
            with open(out_dir / "review.html", "w", encoding="utf-8", errors="replace") as f:
                f.write(vis if isinstance(vis, str) else vis.data)
        except Exception as viz_e:
            (out_dir / "_viz_error.txt").write_text(str(viz_e), encoding="utf-8", errors="replace")

        report = make_report(document_name=name, text=text, rules=pack.rules)
        save_markdown(report, out_dir)
        save_txt(report, out_dir)

        return (name, pack.id, str(out_dir))

# ------------------------------
# Main
# ------------------------------
def main():
    init_db()  # safe to call every run

    # 1) Load active packs from Postgres
    with SessionLocal() as db:
        packs_dict = load_packs_for_runtime(db)  # already {id: RulePack}

    if not packs_dict:
        raise RuntimeError("No active rule packs found in the database. Import/publish one first.")

    # 2) Ingest PDFs → text
    texts = ingest()  # { name: text, ... }

    outputs_dir = Path("outputs")
    outputs_dir.mkdir(parents=True, exist_ok=True)

    # 3) Decide which pack each doc will use (regex-based)
    plan: list[tuple[str, str, dict]] = []  # (name, text, pack_dict)
    default_pack_id = next(iter(packs_dict.keys()))
    for name, text in texts.items():
        pack_id = guess_doc_type_id(text, packs_dict) or default_pack_id
        pack = packs_dict[pack_id]
        # to be picklable across processes, pass a dict
        pack_dict = pack.dict() if hasattr(pack, "dict") else {
            "id": pack.id,
            "doc_type_names": list(getattr(pack, "doc_type_names", [])),
            "rules": getattr(pack, "rules").dict() if hasattr(pack, "rules") else {},
            "prompt": getattr(pack, "prompt", "") or "",
            "examples": [e.dict() if hasattr(e, "dict") else e for e in getattr(pack, "examples", [])],
        }
        plan.append((name, text, pack_dict))

    # 4) Optional concurrency (default to a safe low number for local LLMs)
    max_workers = int(os.getenv("CE_MAX_WORKERS", "1"))  # tune for your machine / model
    if max_workers <= 1:
        # Serial processing
        for (name, text, pack_dict) in plan:
            process_document(name, text, pack_dict, str(outputs_dir))
            time.sleep(0.2)  # gentle throttle
    else:
        # Parallel (per-document) processing
        with ProcessPoolExecutor(max_workers=max_workers) as ex:
            futures = [
                ex.submit(process_document, name, text, pack_dict, str(outputs_dir))
                for (name, text, pack_dict) in plan
            ]
            for fut in as_completed(futures):
                try:
                    name, pack_id, out_dir = fut.result()
                    print(f"Artifacts for {name} → {out_dir}")
                except Exception as e:
                    print(f"[ERROR] Worker failed: {e}")

    print("=== Done with all PDFs ===")

if __name__ == "__main__":
    # Force local provider by default
    os.environ.setdefault("LLM_PROVIDER", "ollama")
    main()
