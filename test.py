#!/usr/bin/env python3

import fitz  # PyMuPDF
from PIL import Image
import pytesseract
import io
import os



def extract_text_from_ocr_pdf(pdf_path):
    """
    Extract text from a scanned PDF using OCR
    """
    print(f"Opening PDF: {pdf_path}")
    
    # Open the PDF
    pdf_document = fitz.open(pdf_path)
    
    # Initialize text storage
    all_text = ""
    
    # Process each page
    for page_num in range(len(pdf_document)):
        print(f"Processing page {page_num + 1}/{len(pdf_document)}...")
        
        # Get the page
        page = pdf_document[page_num]
        
        # Convert page to image with higher resolution for better OCR
        # Increase matrix values for higher quality (2.0 = 2x resolution)
        mat = fitz.Matrix(2.0, 2.0)
        pix = page.get_pixmap(matrix=mat)
        
        # Convert pixmap to PIL Image
        img_data = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_data))
        
        # Perform OCR on the image
        text = pytesseract.image_to_string(img, lang='eng')
        
        # Add page separator and text
        all_text += f"\n\n========== Page {page_num + 1} ==========\n\n"
        all_text += text
        
        # Clean up
        pix = None
    
    # Close the document
    pdf_document.close()
    
    return all_text

# Process the PDF
pdf_path = "gast.pdf"
extracted_text = extract_text_from_ocr_pdf(pdf_path)

# Save the extracted text
output_path = "lease_extracted_text.txt"
with open(output_path, "w", encoding="utf-8") as f:
    f.write(extracted_text)

print(f"\nExtraction complete! Text saved to: {output_path}")
print(f"Total characters extracted: {len(extracted_text)}")