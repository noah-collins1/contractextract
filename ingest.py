import pdfplumber
from pathlib import Path
##This file loops through the data folder for pdfs, converts each pdf to text, and then adds to a dictionary. Will be added on later

PAGE_BREAK = "\f"  # keep page boundaries in the text

def ingest():
    pdf_folder = Path("data")
    text_store = dict()
    for pdf_path in pdf_folder.glob("*.pdf"):
        title = pdf_path.name
        print(f"Reading {title}...")
        pages = [] #accumulate all pages first
        with pdfplumber.open(pdf_path) as pdf:
            # iterate over each page
            for page in pdf.pages:
                # extract text
                text = page.extract_text() or "" # avoid None
                pages.append(text.strip())       # collect per page text
        full_text = PAGE_BREAK.join(pages)       # join pages with form-feed
        text_store[pdf_path.stem] = full_text    # key by stem (filename w/o pdf

    return text_store

if __name__ == "__main__":
    results = ingest()
    print(f"Loaded {len(results)} PDFs")




