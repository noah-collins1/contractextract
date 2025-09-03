import pdfplumber
from pathlib import Path
import tempfile, os

PAGE_BREAK = "\f"  # keep page boundaries in the text

def ingest():
    pdf_folder = Path("data")
    text_store = dict()
    for pdf_path in pdf_folder.glob("*.pdf"):
        title = pdf_path.name
        print(f"Reading {title}...")
        pages = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""  # avoid None
                pages.append(text.strip())
        full_text = PAGE_BREAK.join(pages)
        text_store[pdf_path.stem] = full_text
    return text_store


# ---- NEW helper for FastAPI ----
def ingest_bytes_to_text(data: bytes, filename: str | None = None) -> str:
    """
    Accept raw PDF bytes, write to a temp file, extract text with pdfplumber,
    and return the combined string with form-feed page breaks.
    """
    suffix = ""
    if filename and "." in filename:
        suffix = "." + filename.split(".")[-1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(data)
        tmp_path = tmp.name

    try:
        pages = []
        with pdfplumber.open(tmp_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                pages.append(text.strip())
        return PAGE_BREAK.join(pages)
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass


if __name__ == "__main__":
    results = ingest()
    print(f"Loaded {len(results)} PDFs")



