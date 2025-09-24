from mcp.server.fastmcp import FastMCP
from .tools import list_rulepacks, get_rulepack, analyze
import logging

# Set up logging
log = logging.getLogger("contractextract")
log.setLevel(logging.INFO)

# Create FastMCP server instance
log.info("Creating FastMCP instance")
mcp = FastMCP("ContractExtract MCP")

# Register tools with stub implementations
log.info("Registering tools")
mcp.tool()(list_rulepacks)
mcp.tool()(get_rulepack)
mcp.tool()(analyze)

log.info("MCP tools registered: list_rulepacks, get_rulepack, analyze")

# Test the streamable HTTP app
try:
    mcp_app = mcp.streamable_http_app()
    log.info(f"FastMCP streamable app created: {type(mcp_app)}")
except Exception as e:
    log.error(f"Failed to create streamable HTTP app: {e}")
    raise

# Import and mount to existing FastAPI app
from app import app as fastapi_app

# Mount MCP at /mcp endpoint
log.info("Mounting MCP server at /mcp")
try:
    fastapi_app.mount("/mcp", mcp_app, name="mcp")
    log.info("MCP server mounted successfully")
except Exception as e:
    log.error(f"Failed to mount MCP server: {e}")
    raise