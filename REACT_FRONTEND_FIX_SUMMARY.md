# React Frontend Rulepacks Fix - Summary

## What Was Broken

### 1. **Backend PUT Endpoint Mismatch**
**Problem:** The frontend was sending `{ patch: {...} }` but the backend expected `{ yaml_text: "..." }`

**Location:** `http_bridge.py:186` - PUT /rule-packs/{pack_id}/{version}

**Root Cause:** The `RulePackUpdateRequest` model only had a `patch` field, but the endpoint handler only processed `yaml_text` via `handle_update_rulepack_yaml()`.

### 2. **Frontend Missing Features**
**Problem:** `RulePacks.tsx` had no error handling, loading states, or debug info

**Issues:**
- No loading indicator while fetching rulepacks
- No error messages when API calls failed
- No debug panel to show API base URL and request status
- YAML import textarea didn't have controlled state
- No visual feedback for upload/import operations

### 3. **Missing Logging**
**Problem:** Backend endpoints had no logging for debugging

**Impact:** Couldn't see when frontend was making requests or what data was being sent/received.

---

## What Was Fixed

### Backend Changes (`http_bridge.py`)

#### 1. Updated `RulePackUpdateRequest` Model (Line 87-89)
**Before:**
```python
class RulePackUpdateRequest(BaseModel):
    patch: Dict[str, Any]
```

**After:**
```python
class RulePackUpdateRequest(BaseModel):
    patch: Optional[Dict[str, Any]] = None
    yaml_text: Optional[str] = None
```

Now supports both patch updates and YAML text updates.

#### 2. Fixed PUT Endpoint to Handle Both Update Methods (Lines 186-219)
**Before:**
```python
@app.put("/rule-packs/{pack_id}/{version}")
async def update_rule_pack(pack_id: str, version: int, request: YamlUpdateRequest):
    result = await handle_update_rulepack_yaml({
        "pack_id": pack_id,
        "version": version,
        "yaml_content": request.yaml_text
    })
    return result
```

**After:**
```python
@app.put("/rule-packs/{pack_id}/{version}")
async def update_rule_pack(pack_id: str, version: int, request: RulePackUpdateRequest):
    if request.yaml_text:
        # Handle YAML text updates
        result = await handle_update_rulepack_yaml({
            "pack_id": pack_id,
            "version": version,
            "yaml_content": request.yaml_text
        })
    elif request.patch:
        # Handle patch updates using rulepack_manager
        from rulepack_manager import update_draft, RulePackUpdate
        from infrastructure import get_db_session

        patch_model = RulePackUpdate(**request.patch)
        with get_db_session() as db:
            result = update_draft(db, pack_id, version, patch_model)
            result = result.model_dump() if hasattr(result, 'model_dump') else dict(result)
    else:
        raise HTTPException(status_code=400, detail="Either yaml_text or patch must be provided")

    return result
```

Now properly handles both update types that the frontend sends.

#### 3. Added Logging to All Endpoints (Lines 101-165)
Added `log.info()` calls to:
- GET /rule-packs/all
- GET /rule-packs
- POST /rule-packs/import-yaml
- PUT /rule-packs/{pack_id}/{version}

**Example:**
```python
@app.get("/rule-packs/all")
async def list_all_rule_packs():
    log.info("GET /rule-packs/all called")  # ← ADDED
    try:
        result = await handle_list_all_rulepacks()
        log.info(f"GET /rule-packs/all returned {len(result)} packs")  # ← ADDED
        return result
```

Now you can see in the terminal:
```
INFO - GET /rule-packs/all called
INFO - GET /rule-packs/all returned 3 packs
```

---

### Frontend Changes (`frontend/src/pages/RulePacks.tsx`)

#### Complete Rewrite with:

**1. Loading States**
```tsx
{isLoading && (
  <div className="sub" style={{ padding: "20px", textAlign: "center" }}>
    Loading rule packs...
  </div>
)}
```

**2. Error Handling**
```tsx
{error && (
  <div className="card" style={{ border: "1px solid var(--bad)" }}>
    <div className="sub" style={{ color: "var(--bad)" }}>
      Error loading rule packs: {error.message}
    </div>
    <button onClick={() => refetch()}>Retry</button>
  </div>
)}
```

**3. Debug Panel**
```tsx
<div className="card" style={{ marginTop: "20px", backgroundColor: "#f5f5f5" }}>
  <div className="sub" style={{ fontFamily: "monospace", fontSize: "12px" }}>
    <strong>Debug Info:</strong><br />
    API Base: {import.meta.env.VITE_API_BASE_URL || "(default)"}<br />
    Packs Loaded: {all?.length ?? 0}<br />
    Loading: {isLoading ? "Yes" : "No"}<br />
    Error: {error ? String(error.message) : "none"}
  </div>
</div>
```

**4. Controlled YAML Import**
```tsx
const [yamlText, setYamlText] = React.useState("");

<textarea
  value={yamlText}
  onChange={(e) => setYamlText(e.target.value)}
/>
```

**5. Proper Mutation Handling**
```tsx
const importMutation = useMutation({
  mutationFn: importYamlText,
  onSuccess: () => {
    qc.invalidateQueries({ queryKey: ["packs"] });
    setYamlText("");
    setUploadError(null);
    alert("Rule pack imported successfully!");
  },
  onError: (error: any) => {
    setUploadError(error.response?.data?.detail || error.message);
  },
});
```

**6. Visual Feedback**
```tsx
<button
  className="primary"
  onClick={handleImportYaml}
  disabled={importMutation.isPending || !yamlText.trim()}
>
  {importMutation.isPending ? "Importing..." : "Import YAML"}
</button>
```

---

### Test Script (`test_http_bridge.py`)

Created automated test script to verify:
- ✓ Health endpoint
- ✓ System info endpoint
- ✓ List all rulepacks (empty or populated)
- ✓ Import YAML creates new rulepack
- ✓ Verify import by listing again

**Usage:**
```bash
# Terminal 1: Start backend
python http_bridge.py

# Terminal 2: Run tests
python test_http_bridge.py
```

---

## Final JSON Response Shape

**GET /rule-packs/all** returns:
```json
[
  {
    "id": "strategic_alliance_v1",
    "version": 1,
    "status": "active",
    "doc_type_names": ["Strategic Alliance Agreement", "Alliance Agreement"]
  },
  {
    "id": "test_pack_http_v1",
    "version": 1,
    "status": "draft",
    "doc_type_names": ["Test Document"]
  }
]
```

**POST /rule-packs/import-yaml** returns:
```json
{
  "id": "test_pack_http_v1",
  "version": 1,
  "status": "draft",
  "doc_type_names": ["Test Document"],
  "created_at": "2025-12-02T12:00:00Z"
}
```

---

## How to Use

### Start the Backend
```powershell
cd C:\Users\noahc\PycharmProjects\langextract
.\.venv\Scripts\Activate.ps1
python http_bridge.py
```

Backend will be available at: http://localhost:8000

### Start the Frontend
```powershell
cd frontend
npm install  # Only needed first time
npm run dev
```

Frontend will be available at: http://localhost:5173

### Test the Full Flow

1. **Go to http://localhost:5173/rule-packs**

2. **Check Debug Panel** (bottom of page):
   - Should show API Base: `http://localhost:8000`
   - Should show `Loading: No`
   - Should show `Error: none`
   - Should show `Packs Loaded: X` (where X is the number of packs in DB)

3. **Import a Sample Rule Pack**:
   Paste this YAML into the textarea:
   ```yaml
   schema_version: "1.0"
   id: "test_pack_v1"
   doc_type_names:
     - "Test Document"

   jurisdiction_allowlist:
     - "United States"

   liability_cap:
     require_cap: false

   contract:
     max_contract_value: null

   fraud:
     require_fraud_clause: false

   notes: "Test pack created from React UI"
   ```

4. **Click "Import YAML"**
   - Button should show "Importing..." while processing
   - Should get success alert
   - Table should refresh and show the new pack
   - Debug panel should show `Packs Loaded: 1` (or more)

5. **Verify in Backend Logs**:
   ```
   INFO - POST /rule-packs/import-yaml called (yaml length=XXX chars)
   INFO - POST /rule-packs/import-yaml created pack: test_pack_v1@1
   INFO - GET /rule-packs/all called
   INFO - GET /rule-packs/all returned 1 packs
   ```

---

## Files Changed

### Backend
- `http_bridge.py`:
  - Updated `RulePackUpdateRequest` model
  - Fixed PUT endpoint to handle both patch and yaml_text
  - Added logging to all rule pack endpoints

### Frontend
- `frontend/src/pages/RulePacks.tsx`:
  - Complete rewrite with error handling
  - Added loading states
  - Added debug panel
  - Fixed YAML import with controlled state
  - Added visual feedback for mutations

### New Files
- `test_http_bridge.py`: Automated test script for backend endpoints

---

## Troubleshooting

### Frontend shows "Error loading rule packs"
**Check:**
1. Is backend running? (`python http_bridge.py`)
2. Is backend on port 8000? (check terminal output)
3. Check backend logs for errors
4. Check browser console for network errors

### Import YAML fails
**Check:**
1. YAML syntax is valid (no tabs, proper indentation)
2. `schema_version` field is present
3. `id` field is present and unique
4. Backend logs for specific error message

### Backend logs show database errors
**Check:**
1. PostgreSQL is running
2. Database `contractextract` exists
3. Connection string in `infrastructure.py` is correct
4. Run `init_db()` if tables don't exist

---

## Success Criteria

✓ **Frontend loads and shows table** (even if empty)
✓ **Debug panel shows correct API base**
✓ **Pasting YAML and clicking Import creates a new pack**
✓ **Table refreshes automatically after import**
✓ **Backend logs show request details**
✓ **Error messages are visible if something fails**

---

**All fixes are now complete and tested!**
