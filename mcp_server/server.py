from mcp.server.fastmcp import FastMCP
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
import logging

# Set up logging
log = logging.getLogger("contractextract")
log.setLevel(logging.INFO)

# Create FastMCP server instance
log.info("Creating comprehensive ContractExtract MCP server")
mcp = FastMCP("ContractExtract MCP - Full API Coverage")

# Register legacy compatibility tools
log.info("Registering legacy compatibility tools")
mcp.tool()(list_rulepacks)
mcp.tool()(get_rulepack)
mcp.tool()(analyze)

# Register comprehensive rule pack management tools
log.info("Registering rule pack management tools")
mcp.tool()(list_all_rulepacks)
mcp.tool()(list_active_rulepacks)
mcp.tool()(get_rulepack_details)
mcp.tool()(get_rulepack_yaml)
mcp.tool()(list_rulepack_versions)

# Register rule pack creation and editing tools
log.info("Registering rule pack creation/editing tools")
mcp.tool()(create_rulepack_from_yaml)
mcp.tool()(update_rulepack_yaml)
mcp.tool()(publish_rulepack)
mcp.tool()(deprecate_rulepack)
mcp.tool()(delete_rulepack)

# Register enhanced document analysis tools
log.info("Registering document analysis tools")
mcp.tool()(analyze_document)
mcp.tool()(preview_document_analysis)

# Register utility tools
log.info("Registering utility tools")
mcp.tool()(generate_rulepack_template)
mcp.tool()(validate_rulepack_yaml)
mcp.tool()(get_system_info)

log.info("All MCP tools registered successfully - 16 total tools available for LibreChat")

# Test the streamable HTTP app
try:
    mcp_app = mcp.streamable_http_app()
    log.info(f"FastMCP streamable app created: {type(mcp_app)}")
except Exception as e:
    log.error(f"Failed to create streamable HTTP app: {e}")
    raise

# Import and mount to existing FastAPI app
from app import app as fastapi_app

# Mount MCP at /mcp-stream to avoid path conflicts
log.info("Mounting MCP server at /mcp-stream")
try:
    fastapi_app.mount("/mcp-stream", mcp_app, name="mcp")
    log.info("MCP server mounted successfully - tools are now available via LibreChat at /mcp-stream/mcp")
except Exception as e:
    log.error(f"Failed to mount MCP server: {e}")
    raise