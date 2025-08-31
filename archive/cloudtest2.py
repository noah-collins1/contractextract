# cloudtest.py — cloud-backed runner with rule packs + doc-type detection
from ingest import ingest
from pathlib import Path
import shutil, os, re, hashlib, json, time, random, logging
import langextract as lx
from llm_factory import load_provider

from evaluator import make_report, save_markdown, save_txt
from archive.rule_registry import load_rulepacks
from doc_type import guess_doc_type_id

# ------------------------------
# Silence noisy telemetry
# ------------------------------
os.environ.setdefault("ABSL_LOGGING_MIN_SEVERITY", "3")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
logging.basicConfig(level=logging.WARNING)
for noisy in ("absl", "httpx", "urllib3", "langchain", "opentelemetry"):
    logging.getLogger(noisy).setLevel(logging.ERROR)

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
    if hasattr(result, "documents"):
        return list(getattr(result, "documents") or [])
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
    with open(path, "w", encoding="utf-8") as f:
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
# Sanity fallback (regex) for empty cloud output
# ------------------------------
TITLE_RE = re.compile(r"STRATEGIC ALLIANCE AGREEMENT", re.IGNORECASE)
PARTY_RE = re.compile(r"(ChipMOS TECHNOLOGIES INC\.|Tsinghua Unigroup Ltd\.)", re.IGNORECASE)

def run_sanity_rules(text: str):
    extractions = []
    m = TITLE_RE.search(text)
    if m:
        extractions.append(lx.data.Extraction("agreement_title", m.group(0)))
    for m in PARTY_RE.finditer(text):
        extractions.append(lx.data.Extraction("party_names", m.group(1)))
    return lx.data.AnnotatedDocument(text=text, extractions=extractions)

# ------------------------------
# Cloud extract with retries/backoff (handles 503/UNAVAILABLE)
# ------------------------------
def extract_with_retries(provider, *, text, prompt, examples, passes=1, workers=1, buf=800):
    delays = [1, 2, 4, 8, 16]
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
            transient = ("503" in msg) or ("UNAVAILABLE" in msg.upper()) or ("overloaded" in msg.lower())
            if transient and i < len(delays):
                print(f"[WARN] Provider 503/UNAVAILABLE (attempt {i}/{len(delays)}). Retrying in {d}s…")
                time.sleep(d + random.random())
                last_err = e
                continue
            last_err = e
            break
    raise last_err

# ------------------------------
# Main
# ------------------------------
def main():
    # Provider is configured via llm_cloud.yaml (Gemini/OpenAI)
    provider = load_provider("llm_cloud.yaml")

    # Cloud API key check (works for either provider)
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing cloud API key in environment!")

    # Load rule packs (first pack is default)
    packs_list = load_rulepacks()
    packs = {p.id: p for p in packs_list}
    default_pack_id = packs_list[0].id

    texts = ingest()  # { name: text, ... }

    outputs_dir = Path("../outputs")
    outputs_dir.mkdir(parents=True, exist_ok=True)

    for name, text in texts.items():
        print(f"Running extraction on {name}...")
        out_dir = safe_out_dir(outputs_dir, name)
        ensure_file_path_is_clear(out_dir)

        # --- Select rule pack by doc-type detection (regex-based)
        pack_id = guess_doc_type_id(text, packs) or default_pack_id
        pack = packs[pack_id]

        # Convert examples from pack into LangExtract objects
        lx_examples = []
        for e in pack.examples:
            ex_objs = [lx.data.Extraction(ex["label"], ex["span"], attributes=ex.get("attributes", {}))
                       for ex in e.get("extractions", [])]
            lx_examples.append(lx.data.ExampleData(text=e["text"], extractions=ex_objs))

        try:
            # --- Primary (cloud) pass with retries/backoff
            result = extract_with_retries(
                provider,
                text=text,
                prompt=pack.prompt,       # <- from selected pack
                examples=lx_examples,     # <- from selected pack
                passes=1,
                workers=1,
                buf=800
            )

            # --- Fallback to sanity rules if empty
            if not has_extractions(result):
                print("[WARN] Cloud extraction returned no extractions; running sanity rules fallback...")
                result = run_sanity_rules(text)

            # Save JSONL (UTF-8)
            save_jsonl_utf8(result, out_dir)

            # Visualize
            vis = lx.visualize(str(out_dir / "data.jsonl"))
            with open(out_dir / "review.html", "w", encoding="utf-8", errors="replace") as f:
                f.write(vis if isinstance(vis, str) else vis.data)

            # Evaluate policy & save reports (use rules from pack)
            report = make_report(document_name=name, text=text, rules=pack.rules)
            save_markdown(report, out_dir)
            save_txt(report, out_dir)

            print(f"✓ Finished {name} (pack: {pack.id}):")
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

            report = make_report(document_name=name, text=text, rules=pack.rules)
            save_markdown(report, out_dir)
            save_txt(report, out_dir)

            print(f"✓ Finished {name} (fallback, pack: {pack.id}):")
            print(f"   - {out_dir/'review.html'}")
            print(f"   - {out_dir/'violations.md'}")
            print(f"   - {out_dir/'violations.txt'}")

        time.sleep(0.75)  # gentle throttle between docs

    print("=== Done with all PDFs ===")

if __name__ == "__main__":
    main()
