import pdfplumber
from pathlib import Path
##This file loops through the data folder for pdfs, converts each pdf to text, and then adds to a dictionary. Will be added on later


def ingest():
    pdf_folder = Path("data")
    text_store = dict()
    for pdf_path in pdf_folder.glob("*.pdf"):
        title = pdf_path.name
        print(f"Reading {title}...")
        with pdfplumber.open(pdf_path) as pdf:
            # iterate over each page
            for page in pdf.pages:
                # extract text
                text = page.extract_text()
                text_store[pdf_path] = text
                print(text)
    return text_store

results = ingest()
print(results)




