
#!/usr/bin/env python3
"""
HTTP Bridge Server for ContractExtract
Wraps MCP stdio tools as REST API endpoints for frontend consumption
Runs alongside the stdio MCP server for LibreChat integration
"""

from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging
from pathlib import Path
import tempfile
import asyncio
import sys

# Ensure UTF-8 output with safe error handling, especially on Windows consoles
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception as e:
    # Fall back gracefully; logging should never crash the app
    try:
        print(f"[warning] Failed to reconfigure stdio encoding: {e}")
    except Exception:
        pass

# Import MCP tool handlers directly
from mcp_server import (
    handle_list_all_rulepacks,
    handle_list_active_rulepacks,
    handle_get_rulepack_details,
    handle_get_rulepack_yaml,
    handle_list_rulepack_versions,
    handle_create_rulepack_from_yaml,
    handle_update_rulepack_yaml,
    handle_publish_rulepack,
    handle_deprecate_rulepack,
    handle_delete_rulepack,
    handle_analyze_document,
    handle_preview_document_analysis,
    handle_generate_rulepack_template,
    handle_validate_rulepack_yaml,
    handle_get_system_info
)

from infrastructure import init_db

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
log = logging.getLogger("contractextract.http_bridge")

# Initialize FastAPI app
app = FastAPI(
    title="ContractExtract HTTP Bridge",
    description="REST API bridge to MCP stdio tools",
    version="1.0.0"
)

# CORS configuration for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # Vite default + React default
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========================================
# REQUEST/RESPONSE MODELS
# ========================================

class YamlImportRequest(BaseModel):
    yaml_text: str
    created_by: Optional[str] = "http-bridge"

class YamlUpdateRequest(BaseModel):
    yaml_text: str

class RulePackUpdateRequest(BaseModel):
    patch: Optional[Dict[str, Any]] = None
    yaml_text: Optional[str] = None

class PreviewAnalysisRequest(BaseModel):
    document_text: str
    pack_id: Optional[str] = None

# ========================================
# RULE PACK ENDPOINTS
# ========================================

@app.get("/rule-packs/all")
async def list_all_rule_packs():
    """List ALL rule packs (any status/version)"""
    log.info("GET /rule-packs/all called")
    try:
        result = await handle_list_all_rulepacks()
        log.info(f"GET /rule-packs/all returned {len(result) if isinstance(result, list) else 'N/A'} packs")
        return result
    except Exception as e:
        log.error(f"Error listing all rule packs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/rule-packs")
async def list_rule_packs(status: Optional[str] = None):
    """List rule packs, optionally filtered by status"""
    log.info(f"GET /rule-packs called (status={status})")
    try:
        if status == "active":
            result = await handle_list_active_rulepacks()
        else:
            result = await handle_list_all_rulepacks()
        log.info(f"GET /rule-packs returned {len(result) if isinstance(result, list) else 'N/A'} packs")
        return result
    except Exception as e:
        log.error(f"Error listing rule packs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/rule-packs/{pack_id}")
async def list_pack_versions(pack_id: str):
    """List all versions for a given rule pack"""
    try:
        result = await handle_list_rulepack_versions({"pack_id": pack_id})
        return result
    except Exception as e:
        log.error(f"Error listing pack versions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/rule-packs/{pack_id}/{version}")
async def get_rule_pack_details(pack_id: str, version: int):
    """Get detailed information for a specific rule pack version"""
    try:
        result = await handle_get_rulepack_details({"pack_id": pack_id, "version": version})
        return result
    except Exception as e:
        log.error(f"Error getting rule pack details: {e}")
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/rule-packs/{pack_id}/{version}/yaml", response_class=PlainTextResponse)
async def get_rule_pack_yaml(pack_id: str, version: int):
    """Get raw YAML content for a rule pack"""
    try:
        result = await handle_get_rulepack_yaml({"pack_id": pack_id, "version": version})
        return result
    except Exception as e:
        log.error(f"Error getting rule pack YAML: {e}")
        raise HTTPException(status_code=404, detail=str(e))

@app.post("/rule-packs/import-yaml")
async def import_yaml_text(request: YamlImportRequest):
    """Create a new rule pack from YAML text"""
    log.info(f"POST /rule-packs/import-yaml called (yaml length={len(request.yaml_text)} chars)")
    try:
        result = await handle_create_rulepack_from_yaml({
            "yaml_content": request.yaml_text,
            "created_by": request.created_by
        })
        log.info(f"POST /rule-packs/import-yaml created pack: {result.get('id', 'unknown')}@{result.get('version', 'unknown')}")
        return result
    except Exception as e:
        log.error(f"Error importing YAML: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/rule-packs/upload-yaml")
async def upload_yaml_file(file: UploadFile = File(...)):
    """Create a new rule pack from uploaded YAML file"""
    try:
        yaml_content = await file.read()
        yaml_text = yaml_content.decode('utf-8')
        result = await handle_create_rulepack_from_yaml({
            "yaml_content": yaml_text,
            "created_by": "http-bridge"
        })
        return result
    except Exception as e:
        log.error(f"Error uploading YAML file: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@app.put("/rule-packs/{pack_id}/{version}")
async def update_rule_pack(pack_id: str, version: int, request: RulePackUpdateRequest):
    """Update a draft rule pack with either YAML content or patch object"""
    log.info(f"PUT /rule-packs/{pack_id}/{version} called")
    try:
        # Support both YAML text updates and patch updates
        if request.yaml_text:
            log.info(f"PUT /rule-packs/{pack_id}/{version} - updating with YAML (length={len(request.yaml_text)} chars)")
            result = await handle_update_rulepack_yaml({
                "pack_id": pack_id,
                "version": version,
                "yaml_content": request.yaml_text
            })
        elif request.patch:
            log.info(f"PUT /rule-packs/{pack_id}/{version} - updating with patch: {list(request.patch.keys())}")
            # For patch updates, use the rulepack_manager update_draft function
            from rulepack_manager import update_draft, RulePackUpdate
            from infrastructure import get_db_session

            # Convert dict patch to RulePackUpdate model
            patch_model = RulePackUpdate(**request.patch)

            with get_db_session() as db:
                result = update_draft(db, pack_id, version, patch_model)
                # Convert result to dict for JSON response
                result = result.model_dump() if hasattr(result, 'model_dump') else dict(result)
        else:
            raise HTTPException(status_code=400, detail="Either yaml_text or patch must be provided")

        log.info(f"PUT /rule-packs/{pack_id}/{version} succeeded")
        return result
    except Exception as e:
        log.error(f"Error updating rule pack: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/rule-packs/{pack_id}/{version}:publish")
async def publish_rule_pack(pack_id: str, version: int):
    """Publish a draft rule pack to make it active"""
    try:
        result = await handle_publish_rulepack({"pack_id": pack_id, "version": version})
        return result
    except Exception as e:
        log.error(f"Error publishing rule pack: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/rule-packs/{pack_id}/{version}:deprecate")
async def deprecate_rule_pack(pack_id: str, version: int):
    """Deprecate an active rule pack"""
    try:
        result = await handle_deprecate_rulepack({"pack_id": pack_id, "version": version})
        return result
    except Exception as e:
        log.error(f"Error deprecating rule pack: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/rule-packs/{pack_id}/{version}")
async def delete_rule_pack(pack_id: str, version: int, force: bool = False):
    """Delete a rule pack version"""
    try:
        result = await handle_delete_rulepack({
            "pack_id": pack_id,
            "version": version,
            "force": force
        })
        return result
    except Exception as e:
        log.error(f"Error deleting rule pack: {e}")
        raise HTTPException(status_code=400, detail=str(e))

# ========================================
# DOCUMENT ANALYSIS ENDPOINTS
# ========================================

@app.post("/preview-run")
async def preview_run(file: UploadFile = File(...), pack_id: Optional[str] = Form(None)):
    """
    Analyze a document using rule packs
    Returns analysis report in the format expected by the frontend
    """
    try:
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_path = tmp_file.name

        try:
            # Call the MCP analyze_document handler
            # BUGFIX: Pass original filename so report shows real name, not temp path
            result = await handle_analyze_document({
                "document_path": tmp_path,
                "pack_id": pack_id,
                "source_filename": file.filename  # Pass original filename
            })

            # Transform to frontend format
            response = {
                "document_name": result["document_name"],
                "pack_id": result["doc_type"],
                "report_markdown": result["markdown_report"]
            }

            return response
        finally:
            # Clean up temp file
            Path(tmp_path).unlink(missing_ok=True)

    except Exception as e:
        log.error(f"Error in preview run: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/preview-analysis")
async def preview_analysis(request: PreviewAnalysisRequest):
    """Quick preview analysis from text without saving files"""
    try:
        result = await handle_preview_document_analysis({
            "document_text": request.document_text,
            "pack_id": request.pack_id
        })
        return result
    except Exception as e:
        log.error(f"Error in preview analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ========================================
# UTILITY ENDPOINTS
# ========================================

@app.post("/rule-packs/generate-template")
async def generate_template(pack_id: str, doc_type_names: List[str]):
    """Generate a YAML template for creating new rule packs"""
    try:
        result = await handle_generate_rulepack_template({
            "pack_id": pack_id,
            "doc_type_names": doc_type_names
        })
        return PlainTextResponse(content=result)
    except Exception as e:
        log.error(f"Error generating template: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/rule-packs/validate-yaml")
async def validate_yaml(request: YamlImportRequest):
    """Validate YAML content before creating/updating rule packs"""
    try:
        result = await handle_validate_rulepack_yaml({"yaml_content": request.yaml_text})
        return result
    except Exception as e:
        log.error(f"Error validating YAML: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/system-info")
async def get_system_info():
    """Get system information for debugging and monitoring"""
    try:
        result = await handle_get_system_info()
        return result
    except Exception as e:
        log.error(f"Error getting system info: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "contractextract-http-bridge",
        "version": "1.0.0"
    }

# ========================================
# STARTUP
# ========================================

@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    log.info("Starting ContractExtract HTTP Bridge Server...")
    try:
        init_db()
        log.info("Database initialized successfully")

        # Log report version configuration
        from infrastructure import settings
        log.info(f"Report Version: V2 Renderer = {settings.USE_REPORT_V2}")
        if settings.USE_REPORT_V2:
            log.info("Using new 8-section markdown template with enhanced metadata")
        else:
            log.info("Using legacy markdown renderer")
    except Exception as e:
        log.error(f"Database initialization failed: {e}")

if __name__ == "__main__":
    import uvicorn

    log.info("=" * 60)
    log.info("ContractExtract HTTP Bridge Server")
    log.info("Exposes MCP tools as REST API endpoints")
    log.info("Frontend: http://localhost:5173")
    log.info("API Docs: http://localhost:8000/docs")
    log.info("=" * 60)

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
