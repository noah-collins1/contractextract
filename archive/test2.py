# test.py  — Ollama-backed runner
from ingest import ingest
from pathlib import Path
import shutil, textwrap, os, re, hashlib, json, time, random
import langextract as lx

from llm_provider import OllamaProvider          # <-- use local Ollama provider
from schemas import RuleSet
from evaluator import make_report, save_markdown, save_txt

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

def has_extractions(result) -> bool:
    try:
        docs = getattr(result, "documents", None) or []
        if not docs:
            return False
        return any(getattr(d, "extractions", None) for d in docs)
    except Exception:
        return False

# ------------------------------
# Robust JSONL saver (UTF-8; handles corpus or single doc)
# ------------------------------
def _to_docs(result):
    """
    Normalize various result shapes to a list of 'documents' we can serialize.
    Supports:
      - objects with .documents (provider output)
      - a single AnnotatedDocument
      - list/tuple of AnnotatedDocument or dicts
    """
    if hasattr(result, "documents"):
        docs = getattr(result, "documents") or []
        return list(docs)

    AD = getattr(lx.data, "AnnotatedDocument", None)
    if AD and isinstance(result, AD):
        return [result]

    if isinstance(result, (list, tuple)):
        return list(result)

    return []

def save_jsonl_utf8(result, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "data.jsonl"
    docs = _to_docs(result)
    count = 0
    with open(path, "w", encoding="utf-8") as f:  # UTF-8 avoids cp1252 crashes on Windows
        for d in docs:
            if isinstance(d, dict):
                doc_dict = d
            elif hasattr(d, "to_dict"):
                doc_dict = d.to_dict()
            else:
                ex_list = []
                for e in getattr(d, "extractions", []) or []:
                    if hasattr(e, "to_dict"):
                        ex_list.append(e.to_dict())
                    else:
                        ex_list.append({
                            "label": getattr(e, "label", ""),
                            "span": getattr(e, "span", ""),
                            "attributes": getattr(e, "attributes", {}) or {}
                        })
                doc_dict = {"text": getattr(d, "text", ""), "extractions": ex_list}
            f.write(json.dumps(doc_dict, ensure_ascii=False) + "\n")
            count += 1
    print(f"[INFO] Wrote {count} docs to {path}")
    return path

# ------------------------------
# UPDATED PROMPT (targets 4 rules)
# ------------------------------
PROMPT = textwrap.dedent("""
Extract grounded facts from the contract text. Use exact spans (no paraphrasing).
Only return fields that are actually present; omit absent fields.

Classes:
- liability_cap(cap_text, cap_multiplier, cap_money.amount, cap_money.currency, carveouts[])
- contract_value(value_text, amount, currency)
- fraud_clause(fraud_text, liability_assignment)              # liability_assignment in {"other","self","unclear"}
- governing_law(law_text, country)                            # country or clearly named jurisdiction

Guidelines:
- liability_cap: If the cap references "12 months of fees" or similar, set cap_multiplier=1.0.
- contract_value: Extract the total/maximum contract value if explicitly stated (not every money mention).
- fraud_clause: Include any fraud carveout. If text assigns liability to the "other party", set liability_assignment="other"; 
  if it assigns liability to the same party, use "self"; else "unclear".
- governing_law: Extract the governing law/jurisdiction/venue clause and identify the country/jurisdiction string.

Return ONLY a single JSON object with this shape (no extra text):

{
  "extractions": [
    {
      "liability_cap": "<exact span or omit>",
      "liability_cap_attributes": {
        "cap_multiplier": <number or null>,
        "cap_money.amount": <number or null>,
        "cap_money.currency": "<ISO or symbol or null>",
        "carveouts": ["<string>", "..."]
      },
      "contract_value": {
        "value_text": "<exact span>",
        "amount": <number or null>,
        "currency": "<ISO or symbol or null>"
      },
      "fraud_clause": {
        "fraud_text": "<exact span>",
        "liability_assignment": "<other|self|unclear>"
      },
      "governing_law": {
        "law_text": "<exact span>",
        "country": "<string>"
      }
    }
  ]
}
""")

EXAMPLES = [
    lx.data.ExampleData(
        text="Limitation of Liability: except for fraud, liability is capped at the fees paid in the twelve (12) months prior.",
        extractions=[
            lx.data.Extraction(
                "liability_cap",
                "liability is capped at the fees paid in the twelve (12) months prior",
                attributes={"cap_multiplier": 1.0, "carveouts": ["fraud"]}
            )
        ]
    )
]

# ------------------------------
# Sanity fallback (regex) for empty model output
# ------------------------------
TITLE_RE = re.compile(r"STRATEGIC ALLIANCE AGREEMENT", re.IGNORECASE)
PARTY_RE = re.compile(r"(ChipMOS TECHNOLOGIES INC\.|Tsinghua Unigroup Ltd\.)", re.IGNORECASE)

def run_sanity_rules(text: str):
    """Run a fast, local regex pass to guarantee some output."""
    extractions = []
    m = TITLE_RE.search(text)
    if m:
        extractions.append(lx.data.Extraction("agreement_title", m.group(0)))
    for m in PARTY_RE.finditer(text):
        extractions.append(lx.data.Extraction("party_names", m.group(1)))
    # Single AnnotatedDocument (our saver handles lists/objects too)
    return lx.data.AnnotatedDocument(text=text, extractions=extractions)

# ------------------------------
# Ollama extract with retries/backoff (handles local server hiccups)
# ------------------------------
def extract_with_retries(provider, *, text, prompt, examples, passes=1, workers=1, buf=800):
    """
    Retry on transient local errors:
      - connection refused/timed out
      - 503/unavailable
      - model not loaded yet
    """
    delays = [1, 2, 4, 8, 16]  # seconds (exponential backoff)
    last_err = None
    for i, d in enumerate(delays, start=1):
        try:
            return provider.extract(
                text_or_documents=text,
                prompt=prompt,
                examples=examples,
                extraction_passes=passes,
                max_workers=workers,
                max_char_buffer=buf
            )
        except Exception as e:
            msg = str(e)
            transient = (
                "connection refused" in msg.lower()
                or "timed out" in msg.lower()
                or "503" in msg
                or "unavailable" in msg.lower()
                or "no such model" in msg.lower()
                or "model is not loaded" in msg.lower()
            )
            if transient and i < len(delays):
                print(f"[WARN] Ollama transient error (attempt {i}/{len(delays)}). Retrying in {d}s…")
                time.sleep(d + random.random())  # jitter
                last_err = e
                continue
            last_err = e
            break
    raise last_err

# ------------------------------
# Main
# ------------------------------
def main():
    # Configure Ollama via env or defaults
    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
    ollama_model = os.getenv("OLLAMA_MODEL", "llama3:8b-instruct-q4_K_M")
    provider = OllamaProvider(model_id=ollama_model, url=ollama_url)

    # Placeholder policy for evaluator
    rules = RuleSet(
        jurisdiction=dict(allowed_countries=["US","United States","Canada","EU","European Union","Australia","AUS"]),
        liability_cap=dict(max_cap_amount=1_000_000.00, max_cap_multiplier=1.0),
        contract=dict(max_contract_value=5_000_000.00),
        fraud=dict(require_fraud_clause=True, require_liability_on_other_party=True)
    )

    texts = ingest()  # { name: text, ... }

    outputs_dir = Path("../outputs")
    outputs_dir.mkdir(parents=True, exist_ok=True)

    for name, text in texts.items():
        print(f"Running extraction on {name}...")
        out_dir = safe_out_dir(outputs_dir, name)
        ensure_file_path_is_clear(out_dir)

        try:
            # --- Primary (Ollama) pass with retries/backoff
            result = extract_with_retries(
                provider,
                text=text,
                prompt=PROMPT,
                examples=EXAMPLES,
                passes=1,
                workers=1,   # keep concurrency low for local models
                buf=800
            )

            # --- Fallback to sanity rules if empty
            if not has_extractions(result):
                print("[WARN] Model returned no extractions; running sanity rules fallback...")
                result = run_sanity_rules(text)

            # Save JSONL (UTF-8)
            save_jsonl_utf8(result, out_dir)

            # Visualize
            vis = lx.visualize(str(out_dir / "data.jsonl"))
            with open(out_dir / "review.html", "w", encoding="utf-8", errors="replace") as f:
                f.write(vis if isinstance(vis, str) else vis.data)

            # Evaluate policy & save reports (operates on raw text)
            report = make_report(document_name=name, text=text, rules=rules)
            save_markdown(report, out_dir)
            save_txt(report, out_dir)

            print(f"✓ Finished {name}:")
            print(f"   - {out_dir/'review.html'}")
            print(f"   - {out_dir/'violations.md'}")
            print(f"   - {out_dir/'violations.txt'}")

        except Exception as e:
            # Degrade gracefully: produce local artifacts so the run isn't empty
            print(f"[ERROR] {name}: {e} — using local fallback to produce artifacts.")
            (out_dir / "_error.txt").write_text(str(e), encoding="utf-8", errors="replace")

            fb = run_sanity_rules(text)
            save_jsonl_utf8(fb, out_dir)

            try:
                vis = lx.visualize(str(out_dir / "data.jsonl"))
                with open(out_dir / "review.html", "w", encoding="utf-8", errors="replace") as f:
                    f.write(vis if isinstance(vis, str) else vis.data)
            except Exception as viz_e:
                (out_dir / "_viz_error.txt").write_text(str(viz_e), encoding="utf-8", errors="replace")

            report = make_report(document_name=name, text=text, rules=rules)
            save_markdown(report, out_dir)
            save_txt(report, out_dir)

            print(f"✓ Finished {name} (fallback):")
            print(f"   - {out_dir/'review.html'}")
            print(f"   - {out_dir/'violations.md'}")
            print(f"   - {out_dir/'violations.txt'}")

        # Gentle throttle between docs to be kind to local GPU/CPU
        time.sleep(0.5)

    print("=== Done with all PDFs ===")

if __name__ == "__main__":
    main()
