"""
Minimal v1 LangExtract bridge service - runs with Pydantic v1.
Provides a simple FastAPI wrapper around LangExtract functionality.
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import traceback

# LangExtract imports (v1 compatible)
try:
    import langextract as lx
    LANGEXTRACT_AVAILABLE = True
except ImportError as e:
    LANGEXTRACT_AVAILABLE = False
    LANGEXTRACT_ERROR = str(e)

app = FastAPI(title="LangExtract Bridge Service (Pydantic v1)")

class ExtractRequest(BaseModel):
    text: str
    prompt: str = ""
    examples: List[Dict[str, Any]] = []

class ExtractResponse(BaseModel):
    documents: Optional[List[Dict[str, Any]]] = None
    entities: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None

@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "langextract_available": LANGEXTRACT_AVAILABLE,
        "langextract_error": LANGEXTRACT_ERROR if not LANGEXTRACT_AVAILABLE else None,
        "pydantic_version": "1.x"
    }

@app.post("/extract", response_model=ExtractResponse)
def extract_entities(request: ExtractRequest):
    """
    Extract entities from text using LangExtract.

    Args:
        request: Contains text, prompt, and optional examples

    Returns:
        Extraction results or error information
    """
    if not LANGEXTRACT_AVAILABLE:
        raise HTTPException(
            status_code=500,
            detail=f"LangExtract not available: {LANGEXTRACT_ERROR}"
        )

    try:
        # Convert examples to LangExtract format if provided
        lx_examples = []
        for ex in request.examples:
            if isinstance(ex, dict):
                text_val = ex.get("text", "")
                extractions = ex.get("extractions", [])
                ex_objs = []
                for ext in extractions:
                    label = ext.get("label", "")
                    span = ext.get("span", "")
                    attrs = ext.get("attributes", {})
                    ex_objs.append(lx.data.Extraction(label, span, attributes=attrs))
                lx_examples.append(lx.data.ExampleData(text=text_val, extractions=ex_objs))

        # Perform extraction using LangExtract
        result = lx.extract(
            text_or_documents=request.text,
            prompt=request.prompt,
            examples=lx_examples if lx_examples else None
        )

        # Convert result to JSON-serializable format
        response_data = {"documents": [], "entities": None}

        # Handle different result types
        if hasattr(result, 'documents') and result.documents:
            # Multiple documents
            docs = []
            for doc in result.documents:
                doc_dict = {
                    "text": getattr(doc, "text", ""),
                    "extractions": []
                }
                if hasattr(doc, "extractions"):
                    for ext in doc.extractions:
                        ext_dict = {
                            "label": getattr(ext, "label", ""),
                            "span": getattr(ext, "span", ""),
                            "attributes": getattr(ext, "attributes", {})
                        }
                        doc_dict["extractions"].append(ext_dict)
                docs.append(doc_dict)
            response_data["documents"] = docs

        elif hasattr(result, 'extractions'):
            # Single document with extractions
            doc_dict = {
                "text": request.text,
                "extractions": []
            }
            for ext in result.extractions:
                ext_dict = {
                    "label": getattr(ext, "label", ""),
                    "span": getattr(ext, "span", ""),
                    "attributes": getattr(ext, "attributes", {})
                }
                doc_dict["extractions"].append(ext_dict)
            response_data["documents"] = [doc_dict]

        elif hasattr(result, 'entities'):
            # Entity-style result
            entities = []
            for ent in result.entities:
                ent_dict = {
                    "name": getattr(ent, "name", getattr(ent, "label", "")),
                    "value": getattr(ent, "value", getattr(ent, "text", "")),
                    "attributes": getattr(ent, "attributes", {})
                }
                entities.append(ent_dict)
            response_data["entities"] = entities
        else:
            # Fallback: try to extract any useful data
            response_data["documents"] = [{
                "text": request.text,
                "extractions": []
            }]

        return ExtractResponse(**response_data)

    except Exception as e:
        # Log full traceback for debugging
        error_details = f"Extraction failed: {str(e)}\nTraceback:\n{traceback.format_exc()}"
        print(f"[ERROR] {error_details}")

        # Return error response
        return ExtractResponse(error=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8091)