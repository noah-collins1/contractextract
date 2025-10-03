# ContractExtract Pure MCP - Startup Checklist

Quick startup guide for the **Phase 4 pure stdio MCP architecture**.

---

## 📋 **Prerequisites (One-time Setup)**
- [ ] Python 3.11+ installed
- [ ] PostgreSQL running with `contractextract` database created
- [ ] LibreChat installed and configured
- [ ] Single virtual environment `.venv` created

---

## 🚀 **Quick Start (Every Demo)**

### **Step 1: Start Database**
- [ ] Ensure PostgreSQL is running
- [ ] Verify database `contractextract` exists and is accessible

```powershell
# Verify PostgreSQL running
psql -l | grep contractextract
```

### **Step 2: Configure LibreChat**

Ensure `librechat.yaml` in your LibreChat directory has:

```yaml
mcpServers:
  contractextract:
    command: "python"
    args: ["mcp_server.py"]
    cwd: "C:\\Users\\noahc\\PycharmProjects\\langextract"  # Update path!
    initTimeout: 150000
    serverInstructions: true
```

**✅ Verify:**
- [ ] Absolute path in `cwd` is correct
- [ ] Using `python` command (not `uvicorn`)
- [ ] No HTTP URL specified (pure stdio)

### **Step 3: Start LibreChat**

```powershell
# Navigate to LibreChat directory
cd C:\Users\noahc\LibreChat

# Start LibreChat (Docker Compose)
docker-compose up -d
```

**✅ Verify:**
- [ ] LibreChat accessible at: http://localhost:3080
- [ ] No "failed to initialize mcp server" errors in logs
- [ ] Check logs: `docker-compose logs -f`

### **Step 4: Test MCP Connection**

In LibreChat chat:

1. **Test System Info:** `Get ContractExtract system information`
2. **Test List Packs:** `List all available rule packs`
3. **Test Analysis:** Upload a PDF and ask: `Analyze this contract`

**✅ Verify:**
- [ ] All tools return responses (not errors)
- [ ] System info shows correct version and database stats
- [ ] Rule packs are listed with details

---

## 🎯 **Architecture Changes (Phase 4)**

### **What Changed from Previous Versions:**

#### ✅ **New Pure MCP Architecture**
- **No FastAPI server** - LibreChat spawns `mcp_server.py` directly
- **No HTTP endpoints** - Pure stdio communication
- **Single environment** - Only `.venv` with Pydantic v2
- **5 core files** - Consolidated from 23 files

#### ❌ **Removed Components**
- No need to start `app.py` separately
- No React frontend to run
- No dual environment switching
- No bridge services

### **Simplified Workflow:**

**Old (Phase 2-3):**
```powershell
# Terminal 1: Start FastAPI
.\.venv-v2\Scripts\Activate.ps1
uvicorn app:app --port 8000 --reload

# Terminal 2: Start LibreChat
cd C:\Users\noahc\LibreChat
docker-compose up -d

# Terminal 3: Optional bridge
.\.venv-v1\Scripts\Activate.ps1
uvicorn langextract_service:app --port 8091
```

**New (Phase 4):**
```powershell
# Just start LibreChat - it handles everything!
cd C:\Users\noahc\LibreChat
docker-compose up -d
```

---

## 🔧 **Development Mode (Manual Testing)**

If you need to run the MCP server manually for debugging:

```powershell
# Navigate to project
cd C:\Users\noahc\PycharmProjects\langextract

# Activate environment
.\.venv\Scripts\Activate.ps1

# Run MCP server (stdio mode)
python mcp_server.py

# Server will wait for stdio input
# Use MCP Inspector or test with LibreChat
```

**Testing Imports:**
```powershell
# Test module loading
python -c "import mcp_server; print('✅ MCP server ready')"
python -c "from infrastructure import init_db; init_db(); print('✅ Database connected')"
python -c "from contract_analyzer import make_report; print('✅ Analysis engine ready')"
```

---

## 📊 **Demo Flow Suggestions**

### **Basic Demo (5 minutes)**
1. Show LibreChat interface at http://localhost:3080
2. **System Info:** "Get system information" → Shows database stats
3. **List Packs:** "List all rule packs" → Shows 8 available packs
4. **Quick Analysis:** "Analyze sample contract text" → Shows compliance check
5. Explain pure MCP integration - no separate servers needed

### **Technical Demo (10 minutes)**
1. Show `librechat.yaml` stdio configuration
2. Demonstrate LibreChat spawning MCP process automatically
3. Show 5 consolidated Python files (down from 23)
4. Execute `analyze_document` and show markdown report in chat
5. Explain architecture: LibreChat → stdio → MCP Server → PostgreSQL

### **Advanced Demo (15 minutes)**
1. Upload actual contract PDF
2. Show auto-detection of document type
3. Display full analysis with markdown report
4. Create new rule pack via natural language
5. Re-analyze with new rule pack
6. Show rule pack versioning and lifecycle

---

## 🆘 **Troubleshooting Quick Fixes**

### **"MCP server failed to initialize"**
1. **Check Python version:** `python --version` (should be 3.11+)
2. **Verify path in librechat.yaml:** Ensure `cwd` is absolute and correct
3. **Test imports:** `python -c "import mcp_server"`
4. **Increase timeout:** Set `initTimeout: 300000` in librechat.yaml
5. **Check LibreChat logs:** `docker-compose logs contractextract`

### **"Database connection failed"**
```powershell
# Start PostgreSQL
# Windows: Services → PostgreSQL → Start

# Verify database exists
psql -U postgres -c "\l" | grep contractextract

# Test connection
python -c "from infrastructure import init_db; init_db()"
```

### **"Import errors / Module not found"**
```powershell
# Ensure correct environment
.\.venv\Scripts\Activate.ps1

# Reinstall dependencies
pip install -r requirements.txt

# Verify Pydantic v2
python -c "import pydantic; print(pydantic.__version__)"  # Should be 2.x
```

### **"Tool responses are empty"**
1. Check database has rule packs: `python -c "from rulepack_manager import list_all; print(list_all())"`
2. Seed database if empty: `python rulepack_manager.py`
3. Check telemetry logs for errors

---

## 📝 **Key Files Reference**

### **Core Application (5 Files)**
| File | Purpose | Lines |
|------|---------|-------|
| `mcp_server.py` | Pure stdio MCP server with 16 tools | 959 |
| `infrastructure.py` | Config, DB, schemas, telemetry | 267 |
| `contract_analyzer.py` | Analysis engine + LLM integration | 590 |
| `document_analysis.py` | PDF processing pipeline | 514 |
| `rulepack_manager.py` | Rule pack data access | 313 |

### **Configuration**
| File | Purpose |
|------|---------|
| `requirements.txt` | Unified Pydantic v2 dependencies |
| `librechat_mcp_config.yaml` | LibreChat stdio MCP configuration example |
| `llm.yaml` | LLM provider settings |

### **Data**
| Directory | Purpose |
|-----------|---------|
| `rules_packs/` | YAML rule definitions (8 packs) |
| `data/` | Test PDF documents |
| `outputs/` | Generated analysis reports |

---

## ✅ **Success Indicators**

**🎯 Demo Ready When:**
- [ ] LibreChat starts without MCP initialization errors
- [ ] System info tool returns database statistics
- [ ] List rule packs shows 8 available packs
- [ ] Document analysis returns compliance report
- [ ] Markdown report displays formatted in chat

**🚀 Ready to demonstrate pure MCP-powered contract analysis!**

---

## 🎓 **Quick Commands Reference**

```powershell
# ============================================
# START LIBRECHAT (Auto-starts MCP server)
# ============================================
cd C:\Users\noahc\LibreChat
docker-compose up -d

# ============================================
# MANUAL MCP SERVER (Development/Debug)
# ============================================
cd C:\Users\noahc\PycharmProjects\langextract
.\.venv\Scripts\Activate.ps1
python mcp_server.py

# ============================================
# TEST DATABASE CONNECTION
# ============================================
python -c "from infrastructure import init_db; init_db(); print('✅ Connected')"

# ============================================
# TEST MODULE IMPORTS
# ============================================
python -c "import mcp_server; print('✅ MCP ready')"
python -c "from contract_analyzer import make_report; print('✅ Analyzer ready')"

# ============================================
# VIEW LIBRECHAT LOGS
# ============================================
cd C:\Users\noahc\LibreChat
docker-compose logs -f

# ============================================
# RESTART LIBRECHAT (After code changes)
# ============================================
docker-compose down
docker-compose up -d
```

---

## 🔄 **After Code Changes**

When you modify `mcp_server.py` or any core files:

1. **Stop LibreChat:** `docker-compose down`
2. **Verify changes:** Test imports locally
3. **Restart LibreChat:** `docker-compose up -d`
4. **Test in chat:** Run a quick tool call

**No need to restart any Python servers manually!**

---

**Updated for Phase 4 Pure MCP Architecture**
**No FastAPI • No React • No Dual Environments • Just Pure MCP!**