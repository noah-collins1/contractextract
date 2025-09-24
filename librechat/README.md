# LibreChat Integration for ContractExtract MCP

This folder contains configuration files to integrate ContractExtract with LibreChat using the Model Context Protocol (MCP).

## 📁 Files in this Directory

### `librechat.yaml`
Complete LibreChat configuration file that includes:
- **MCP server configuration** pointing to ContractExtract at `http://host.docker.internal:8000/mcp`
- **Optimal timeout settings** (60s for tools, 30s for initialization)
- **File upload support** for PDF documents and YAML rule packs
- **Custom welcome message** mentioning ContractExtract integration
- **Example API endpoint configurations** for OpenAI and Anthropic models
- **Actions allowlist** for ContractExtract domain access

### `docker-compose.override.yml`
Docker Compose override file that ensures:
- **Host networking access** via `host.docker.internal` resolution
- **Environment variable support** for API keys
- **Restart policies** for service reliability
- **Bridge networking** for container communication

## 🚀 Installation Instructions

### Step 1: Copy Configuration Files

Copy both files to your LibreChat installation directory:

```powershell
# Copy the configuration files to your LibreChat directory
copy librechat.yaml C:\path\to\your\LibreChat\
copy docker-compose.override.yml C:\path\to\your\LibreChat\
```

### Step 2: Set Environment Variables (Optional)

If using external LLM providers, set your API keys:

```powershell
# Create .env file in LibreChat directory (if it doesn't exist)
echo OPENAI_API_KEY=your_openai_key_here >> .env
echo ANTHROPIC_API_KEY=your_anthropic_key_here >> .env
```

### Step 3: Start ContractExtract Server

Before starting LibreChat, ensure ContractExtract is running:

```powershell
# Navigate to ContractExtract directory
cd C:\path\to\contractextract

# Activate v2 environment and start server
.\.venv-v2\Scripts\Activate.ps1
uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```

### Step 4: Start LibreChat

```powershell
# Navigate to LibreChat directory
cd C:\path\to\your\LibreChat

# Start LibreChat with Docker Compose
docker-compose up -d
```

## ✅ Verification Steps

### 1. Check LibreChat Logs
```bash
docker-compose logs -f api
```
Look for successful MCP initialization messages.

### 2. Test MCP Connection
In LibreChat chat interface, try:
- `Get system information about ContractExtract`
- `List all available rule packs`
- `Generate a template for a new rule pack`

### 3. Verify ContractExtract Tools
You should see 16 ContractExtract tools available in the chat interface.

## 🔧 Configuration Options

### Network Configuration

**For Docker deployments** (recommended):
```yaml
url: "http://host.docker.internal:8000/mcp"
```

**For native/local deployments**:
```yaml
url: "http://localhost:8000/mcp"
```

### Timeout Configuration

The provided timeouts are optimized for ContractExtract:
- `timeout: 60000` - 60 seconds for tool execution (document analysis can take time)
- `initTimeout: 30000` - 30 seconds for server initialization

### File Upload Configuration

Configured to support contract analysis files:
- **PDF documents** - Primary contract format
- **Text files** - Plain text contracts
- **YAML files** - Rule pack definitions
- **JSON files** - Structured data exchange
- **Markdown files** - Documentation and reports

## 🆘 Troubleshooting

### "MCP server failed to initialize"

**Check ContractExtract server is running:**
```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}'
```

**Expected response:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "protocolVersion": "2024-11-05",
    "capabilities": {"tools": {}},
    "serverInfo": {"name": "ContractExtract MCP Server", "version": "1.0.0"}
  }
}
```

### Network Connectivity Issues

**For Docker on Windows/Linux:**
- Ensure `host.docker.internal` resolves correctly
- Check that port 8000 is not blocked by firewall
- Verify Docker has access to host networking

**For native deployments:**
- Change URL to `http://localhost:8000/mcp`
- Ensure no proxy or firewall interference

### Port Conflicts

If port 8000 is in use:
1. Change ContractExtract port: `uvicorn app:app --port 8001`
2. Update librechat.yaml URL accordingly

### Timeout Issues

For slow operations, increase timeouts:
```yaml
mcpServers:
  contractextract:
    timeout: 120000      # 2 minutes
    initTimeout: 60000   # 1 minute
```

## 🎯 Available MCP Tools

Once integration is complete, these tools will be available in LibreChat:

### Rule Pack Management
- `list_all_rulepacks` - View all rule packs
- `list_active_rulepacks` - View active rule packs
- `get_rulepack_details` - Get detailed rule pack info
- `get_rulepack_yaml` - Download YAML content
- `list_rulepack_versions` - View version history

### Rule Pack Creation & Editing
- `create_rulepack_from_yaml` - Create new rule packs
- `update_rulepack_yaml` - Edit existing rule packs
- `publish_rulepack` - Activate draft rule packs
- `deprecate_rulepack` - Deprecate old versions
- `delete_rulepack` - Remove unwanted rule packs

### Document Analysis
- `analyze_document` - Comprehensive contract analysis
- `preview_document_analysis` - Quick analysis preview

### Utilities
- `generate_rulepack_template` - Create YAML templates
- `validate_rulepack_yaml` - Validate YAML syntax
- `get_system_info` - System status and monitoring

### Legacy Tools
- `list_rulepacks`, `get_rulepack`, `analyze` - Backward compatibility

## 📚 Usage Examples

### Basic Contract Analysis
```
"Analyze this service agreement: [paste contract text here]"
```

### Rule Pack Management
```
"Create a new rule pack for vendor agreements with liability cap of $2M"
"Show me all versions of the employment_v1 rule pack"
"Publish the draft vendor_agreement rule pack as version 1"
```

### Template Generation
```
"Generate a YAML template for consulting agreements"
"Create a rule pack template for international contracts"
```

## 🔄 Updates and Maintenance

To update the configuration:

1. **Stop LibreChat:**
   ```bash
   docker-compose down
   ```

2. **Update configuration files** as needed

3. **Restart LibreChat:**
   ```bash
   docker-compose up -d
   ```

4. **Verify MCP connection** is restored

## 📞 Support

If you encounter issues:

1. **Check ContractExtract logs** for MCP-related errors
2. **Review LibreChat container logs** for connection issues
3. **Test MCP endpoint directly** using curl commands above
4. **Verify network connectivity** between containers and host

For development questions, see the main [ContractExtract README](../README.md) and [CLAUDE.md](../CLAUDE.md) files.