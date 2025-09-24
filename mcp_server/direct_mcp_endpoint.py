"""
Direct MCP (Model Context Protocol) endpoint implementation for FastAPI.
This provides a JSON-RPC 2.0 compliant MCP server without using FastMCP mounting.
"""
from typing import Dict, Any, List, Optional
import json
import logging
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

# Import our MCP tools
from .tools import (
    # Legacy compatibility tools
    list_rulepacks, get_rulepack, analyze,
    # Comprehensive rule pack management
    list_all_rulepacks, list_active_rulepacks, get_rulepack_details,
    get_rulepack_yaml, list_rulepack_versions,
    # Rule pack creation and editing
    create_rulepack_from_yaml, update_rulepack_yaml, publish_rulepack,
    deprecate_rulepack, delete_rulepack,
    # Enhanced document analysis
    analyze_document, preview_document_analysis,
    # Utilities
    generate_rulepack_template, validate_rulepack_yaml, get_system_info
)

log = logging.getLogger("contractextract.mcp.direct")

# Pydantic models for MCP protocol
class MCPRequest(BaseModel):
    jsonrpc: str = Field(default="2.0")
    id: Any
    method: str
    params: Optional[Dict[str, Any]] = Field(default_factory=dict)

class MCPResponse(BaseModel):
    jsonrpc: str = Field(default="2.0")
    id: Any
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None

class MCPError(BaseModel):
    code: int
    message: str
    data: Optional[Any] = None

# Tool registry mapping method names to functions
TOOL_REGISTRY = {
    # Legacy compatibility
    "list_rulepacks": list_rulepacks,
    "get_rulepack": get_rulepack,
    "analyze": analyze,

    # Comprehensive rule pack management
    "list_all_rulepacks": list_all_rulepacks,
    "list_active_rulepacks": list_active_rulepacks,
    "get_rulepack_details": get_rulepack_details,
    "get_rulepack_yaml": get_rulepack_yaml,
    "list_rulepack_versions": list_rulepack_versions,

    # Rule pack creation and editing
    "create_rulepack_from_yaml": create_rulepack_from_yaml,
    "update_rulepack_yaml": update_rulepack_yaml,
    "publish_rulepack": publish_rulepack,
    "deprecate_rulepack": deprecate_rulepack,
    "delete_rulepack": delete_rulepack,

    # Enhanced document analysis
    "analyze_document": analyze_document,
    "preview_document_analysis": preview_document_analysis,

    # Utilities
    "generate_rulepack_template": generate_rulepack_template,
    "validate_rulepack_yaml": validate_rulepack_yaml,
    "get_system_info": get_system_info,
}

# Tool definitions for the tools/list response
TOOL_DEFINITIONS = [
    {
        "name": "list_rulepacks",
        "description": "List active rule packs for document analysis",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_rulepack",
        "description": "Get detailed information about a specific rule pack",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Rule pack name/ID"},
                "version": {"type": "string", "description": "Rule pack version (optional)"}
            },
            "required": ["name"]
        }
    },
    {
        "name": "analyze",
        "description": "Analyze a document for compliance using rule packs",
        "inputSchema": {
            "type": "object",
            "properties": {
                "document_path": {"type": "string", "description": "Path to document file"},
                "document_text": {"type": "string", "description": "Document text content"},
                "doc_type_hint": {"type": "string", "description": "Document type hint"},
                "pack_id": {"type": "string", "description": "Specific rule pack to use"}
            }
        }
    },
    {
        "name": "list_all_rulepacks",
        "description": "List ALL rule packs in the database (any status/version)",
        "inputSchema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "list_active_rulepacks",
        "description": "List only active rule packs for runtime evaluation",
        "inputSchema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "get_rulepack_details",
        "description": "Get detailed information for a specific rule pack version",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pack_id": {"type": "string", "description": "Rule pack ID"},
                "version": {"type": "integer", "description": "Rule pack version (optional)"}
            },
            "required": ["pack_id"]
        }
    },
    {
        "name": "get_rulepack_yaml",
        "description": "Get raw YAML content for a rule pack",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pack_id": {"type": "string", "description": "Rule pack ID"},
                "version": {"type": "integer", "description": "Rule pack version (optional)"}
            },
            "required": ["pack_id"]
        }
    },
    {
        "name": "list_rulepack_versions",
        "description": "List all versions for a given rule pack ID",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pack_id": {"type": "string", "description": "Rule pack ID"}
            },
            "required": ["pack_id"]
        }
    },
    {
        "name": "create_rulepack_from_yaml",
        "description": "Create a new rule pack from YAML content",
        "inputSchema": {
            "type": "object",
            "properties": {
                "yaml_content": {"type": "string", "description": "YAML rule pack definition"},
                "created_by": {"type": "string", "description": "Creator identifier"}
            },
            "required": ["yaml_content"]
        }
    },
    {
        "name": "update_rulepack_yaml",
        "description": "Update a draft rule pack with new YAML content",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pack_id": {"type": "string", "description": "Rule pack ID"},
                "version": {"type": "integer", "description": "Rule pack version"},
                "yaml_content": {"type": "string", "description": "Updated YAML content"}
            },
            "required": ["pack_id", "version", "yaml_content"]
        }
    },
    {
        "name": "publish_rulepack",
        "description": "Publish a draft rule pack to make it active",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pack_id": {"type": "string", "description": "Rule pack ID"},
                "version": {"type": "integer", "description": "Rule pack version"}
            },
            "required": ["pack_id", "version"]
        }
    },
    {
        "name": "deprecate_rulepack",
        "description": "Deprecate an active rule pack",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pack_id": {"type": "string", "description": "Rule pack ID"},
                "version": {"type": "integer", "description": "Rule pack version"}
            },
            "required": ["pack_id", "version"]
        }
    },
    {
        "name": "delete_rulepack",
        "description": "Delete a rule pack version (drafts only by default)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pack_id": {"type": "string", "description": "Rule pack ID"},
                "version": {"type": "integer", "description": "Rule pack version"},
                "force": {"type": "boolean", "description": "Force delete non-draft packs"}
            },
            "required": ["pack_id", "version"]
        }
    },
    {
        "name": "analyze_document",
        "description": "Enhanced document analysis with comprehensive output",
        "inputSchema": {
            "type": "object",
            "properties": {
                "document_path": {"type": "string", "description": "Path to document file"},
                "document_text": {"type": "string", "description": "Document text content"},
                "doc_type_hint": {"type": "string", "description": "Document type hint"},
                "pack_id": {"type": "string", "description": "Specific rule pack to use"}
            }
        }
    },
    {
        "name": "preview_document_analysis",
        "description": "Quick preview analysis without saving files",
        "inputSchema": {
            "type": "object",
            "properties": {
                "document_text": {"type": "string", "description": "Document text to analyze"},
                "pack_id": {"type": "string", "description": "Rule pack to use (optional)"}
            },
            "required": ["document_text"]
        }
    },
    {
        "name": "generate_rulepack_template",
        "description": "Generate YAML template for creating new rule packs",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pack_id": {"type": "string", "description": "Rule pack ID for template"},
                "doc_type_names": {"type": "array", "items": {"type": "string"}, "description": "Document type names"}
            },
            "required": ["pack_id", "doc_type_names"]
        }
    },
    {
        "name": "validate_rulepack_yaml",
        "description": "Validate YAML content before creating/updating rule packs",
        "inputSchema": {
            "type": "object",
            "properties": {
                "yaml_content": {"type": "string", "description": "YAML content to validate"}
            },
            "required": ["yaml_content"]
        }
    },
    {
        "name": "get_system_info",
        "description": "Get system information for debugging and monitoring",
        "inputSchema": {"type": "object", "properties": {}, "required": []}
    }
]

def create_mcp_error(code: int, message: str, data: Any = None) -> Dict[str, Any]:
    """Create an MCP error response"""
    error = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return error

def handle_mcp_request(request: MCPRequest) -> MCPResponse:
    """Handle MCP JSON-RPC request"""
    try:
        method = request.method
        params = request.params or {}

        log.info(f"MCP request: {method}")

        if method == "initialize":
            # MCP initialization
            result = {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "ContractExtract MCP Server",
                    "version": "1.0.0"
                }
            }
            return MCPResponse(id=request.id, result=result)

        elif method == "tools/list":
            # List available tools
            result = {"tools": TOOL_DEFINITIONS}
            return MCPResponse(id=request.id, result=result)

        elif method == "tools/call":
            # Call a tool
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})

            if tool_name not in TOOL_REGISTRY:
                error = create_mcp_error(-32601, f"Tool not found: {tool_name}")
                return MCPResponse(id=request.id, error=error)

            try:
                # Call the tool function
                tool_func = TOOL_REGISTRY[tool_name]

                # Handle different argument patterns
                if tool_name in ["get_rulepack", "analyze"]:
                    # These functions expect individual arguments
                    if tool_name == "get_rulepack":
                        result = tool_func(tool_args.get("name"), tool_args.get("version"))
                    elif tool_name == "analyze":
                        result = tool_func(tool_args)
                elif tool_name in ["get_rulepack_details", "get_rulepack_yaml"]:
                    result = tool_func(tool_args.get("pack_id"), tool_args.get("version"))
                elif tool_name == "list_rulepack_versions":
                    result = tool_func(tool_args.get("pack_id"))
                elif tool_name == "create_rulepack_from_yaml":
                    result = tool_func(tool_args.get("yaml_content"), tool_args.get("created_by", "mcp-llm"))
                elif tool_name in ["update_rulepack_yaml", "publish_rulepack", "deprecate_rulepack"]:
                    result = tool_func(tool_args.get("pack_id"), tool_args.get("version"),
                                     tool_args.get("yaml_content") if tool_name == "update_rulepack_yaml" else None)
                elif tool_name == "delete_rulepack":
                    result = tool_func(tool_args.get("pack_id"), tool_args.get("version"), tool_args.get("force", False))
                elif tool_name == "analyze_document":
                    result = tool_func(tool_args)
                elif tool_name == "preview_document_analysis":
                    result = tool_func(tool_args.get("document_text"), tool_args.get("pack_id"))
                elif tool_name == "generate_rulepack_template":
                    result = tool_func(tool_args.get("pack_id"), tool_args.get("doc_type_names"))
                elif tool_name == "validate_rulepack_yaml":
                    result = tool_func(tool_args.get("yaml_content"))
                else:
                    # Functions with no arguments
                    result = tool_func()

                # Format result for MCP response
                response_result = {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result, indent=2, ensure_ascii=False)
                        }
                    ]
                }

                return MCPResponse(id=request.id, result=response_result)

            except Exception as e:
                log.error(f"Tool execution failed for {tool_name}: {e}")
                error = create_mcp_error(-32603, f"Tool execution failed: {str(e)}")
                return MCPResponse(id=request.id, error=error)

        else:
            # Unknown method
            error = create_mcp_error(-32601, f"Method not found: {method}")
            return MCPResponse(id=request.id, error=error)

    except Exception as e:
        log.error(f"MCP request processing failed: {e}")
        error = create_mcp_error(-32700, f"Parse error: {str(e)}")
        return MCPResponse(id=request.id, error=error)

# Create FastAPI router
router = APIRouter()

@router.post("/mcp")
async def mcp_endpoint(request: Request):
    """MCP JSON-RPC endpoint"""
    try:
        body = await request.json()
        mcp_request = MCPRequest.parse_obj(body)
        response = handle_mcp_request(mcp_request)
        return response.dict(exclude_none=True)
    except Exception as e:
        log.error(f"MCP endpoint error: {e}")
        error_response = MCPResponse(
            id=body.get("id", 1) if 'body' in locals() else 1,
            error=create_mcp_error(-32700, f"Invalid request: {str(e)}")
        )
        return error_response.dict(exclude_none=True)

log.info("Direct MCP endpoint created - ready for LibreChat integration")