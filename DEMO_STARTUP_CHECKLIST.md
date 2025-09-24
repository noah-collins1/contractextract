# ContractExtract MCP Demo - Startup Checklist

This checklist ensures you can quickly boot up the ContractExtract MCP demo for presentations.

## 📋 **Prerequisites (One-time Setup)**
- [ ] Python 3.11 installed
- [ ] PostgreSQL running with `contractextract` database created
- [ ] LibreChat installed and configured
- [ ] Two virtual environments created (`.venv` and `.venv-v2`)

---

## 🚀 **Quick Start (Every Demo)**

### **Step 1: Start Database**
- [ ] Ensure PostgreSQL is running
- [ ] Verify database `contractextract` exists and is accessible

### **Step 2: Start ContractExtract FastAPI Server (MCP v2)**
```powershell
# Navigate to project directory
cd C:\Users\noahc\PycharmProjects\langextract

# Activate Pydantic v2 environment
.\.venv-v2\Scripts\Activate.ps1

# Start FastAPI server with MCP integration
uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```

**✅ Verify:**
- Server logs show: `"MCP tools registered: list_rulepacks, get_rulepack, analyze"`
- FastAPI docs accessible at: http://127.0.0.1:8000/docs

### **Step 3: Start LibreChat**
```powershell
# Navigate to LibreChat directory
cd C:\Users\noahc\LibreChat

# Start LibreChat (Docker Compose)
docker-compose up -d
```

**✅ Verify:**
- LibreChat accessible at: http://localhost:3080
- No "failed to initialize mcp server" errors in logs

### **Step 4: Test MCP Connection**
In LibreChat chat:
1. **Test 1:** `List all available rule packs`
2. **Test 2:** `Get details for strategic_alliance_v1 rule pack`
3. **Test 3:** `Analyze this contract: "Service Agreement between Company A and B, value $50,000, California law"`

**✅ Verify:** All tools return responses (stub data initially)

---

## 🛠️ **Optional: LangExtract v1 Bridge (If Needed)**

### **Step 5: Start LangExtract Service (Pydantic v1)**
```powershell
# NEW TERMINAL - Navigate to project directory
cd C:\Users\noahc\PycharmProjects\langextract

# Activate Pydantic v1 environment
.\.venv\Scripts\Activate.ps1

# Start LangExtract bridge service
uvicorn langextract_service:app --host 127.0.0.1 --port 8091 --reload
```

**✅ Verify:** Health check returns: http://127.0.0.1:8091/health

---

## 🔧 **Configuration Files**

### **LibreChat Configuration (`C:\Users\noahc\LibreChat\librechat.yaml`)**
```yaml
mcpServers:
  contractextract:
    type: "streamable-http"
    url: "http://host.docker.internal:8000/mcp"  # Docker setup
    # url: "http://localhost:8000/mcp"           # Native setup
    initTimeout: 300000
    serverInstructions: true
```

### **Key Project Files**
- **Main API:** `app.py` (FastAPI server)
- **MCP Integration:** `mcp_server/server.py` (FastMCP mount)
- **MCP Tools:** `mcp_server/tools.py` (stub implementations)
- **LangExtract Bridge:** `langextract_service.py` (v1 compatibility)

---

## 📊 **Demo Flow Suggestions**

### **Basic Demo (5 minutes)**
1. Show LibreChat interface
2. Ask: "List available rule packs" → Shows 3 stub packs
3. Ask: "Analyze a sample contract" → Shows stub analysis
4. Explain this demonstrates MCP integration working

### **Technical Demo (10 minutes)**
1. Show FastAPI server logs responding to MCP calls
2. Show `/docs` endpoint with existing contract API
3. Demonstrate rule pack management via API
4. Explain architecture: LibreChat → MCP → FastAPI → PostgreSQL

### **Development Demo (15 minutes)**
1. Show dual environment setup (v1/v2 Pydantic)
2. Demonstrate editing MCP tools in real-time
3. Show how to wire stub tools to real business logic
4. Explain bridge pattern for legacy compatibility

---

## 🆘 **Troubleshooting Quick Fixes**

### **"MCP server failed to initialize"**
1. Check LibreChat uses correct URL (`host.docker.internal` vs `localhost`)
2. Verify FastAPI server is running on port 8000
3. Check MCP tools are registered in server logs
4. Increase `initTimeout` to 300000

### **"Port already in use"**
```powershell
# Kill processes on port 8000
Get-Process | Where-Object {$_.ProcessName -like "*python*"} | Stop-Process -Force

# Or use different ports and update URLs
```

### **"Database connection failed"**
1. Start PostgreSQL service
2. Verify database `contractextract` exists
3. Check connection string in `db.py`

### **"Import errors"**
1. Ensure correct virtual environment activated
2. Check `.venv-v2` has: `mcp`, `fastapi==0.103.*`, `pydantic==2.*`
3. Check `.venv` has: `pydantic<2`, `langextract`

---

## 🎯 **Success Indicators**

**✅ Demo Ready When:**
- [ ] FastAPI server shows MCP tools registered
- [ ] LibreChat connects without errors
- [ ] All 3 MCP tools respond with stub data
- [ ] Server logs show MCP requests being processed
- [ ] Demo contract analysis returns results

**🚀 Ready to demonstrate MCP-powered contract analysis!**

---

## 📝 **Quick Commands Reference**

```powershell
# Start v2 server (MCP)
.\.venv-v2\Scripts\Activate.ps1; uvicorn app:app --host 127.0.0.1 --port 8000 --reload

# Start v1 bridge (optional)
.\.venv\Scripts\Activate.ps1; uvicorn langextract_service:app --host 127.0.0.1 --port 8091 --reload

# Start LibreChat
cd C:\Users\noahc\LibreChat; docker-compose up -d

# Test endpoints
curl http://localhost:8000/docs              # FastAPI docs
curl http://localhost:8000/mcp-test          # MCP test (if available)
curl http://localhost:8091/health            # LangExtract bridge health
```