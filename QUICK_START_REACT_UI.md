# Quick Start: React Frontend for Rule Packs

## 🚀 Start Servers

### Backend (Terminal 1)
```powershell
cd C:\Users\noahc\PycharmProjects\langextract
.\.venv\Scripts\Activate.ps1
python http_bridge.py
```
✓ Backend running at: **http://localhost:8000**
✓ API docs at: **http://localhost:8000/docs**

### Frontend (Terminal 2)
```powershell
cd C:\Users\noahc\PycharmProjects\langextract\frontend
npm run dev
```
✓ Frontend running at: **http://localhost:5173**

---

## 📍 Key URLs

| Service | URL |
|---------|-----|
| Frontend UI | http://localhost:5173 |
| Rule Packs Page | http://localhost:5173/rule-packs |
| Upload Page | http://localhost:5173/upload |
| Backend API | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |
| Health Check | http://localhost:8000/health |

---

## 🧪 Test Backend (Optional)

```powershell
# While backend is running
python test_http_bridge.py
```

Should output:
```
# All Tests Passed! ✓
Total rulepacks in database: X
```

---

## 📦 Sample YAML for Testing

Paste this into the "Import YAML" textarea:

```yaml
schema_version: "1.0"
id: "my_test_pack_v1"
doc_type_names:
  - "Test Document"

jurisdiction_allowlist:
  - "United States"
  - "Canada"

liability_cap:
  require_cap: false
  max_cap_amount: null
  max_cap_multiplier: null

contract:
  max_contract_value: null

fraud:
  require_fraud_clause: false
  require_liability_on_other_party: false

prompt: |
  This is a test rule pack created from the React UI.
  Add your custom analysis prompt here.

notes: "Created for testing the React frontend"
```

---

## 🐛 Debug Checklist

If the UI shows no rule packs:

1. **Check backend is running**
   ```powershell
   curl http://localhost:8000/health
   ```
   Should return: `{"status":"healthy",...}`

2. **Check debug panel** (bottom of /rule-packs page)
   - API Base should be `http://localhost:8000`
   - Error should be `none`

3. **Check browser console** (F12)
   - Look for network errors
   - Check if GET /rule-packs/all succeeded

4. **Check backend logs**
   - Should see: `GET /rule-packs/all called`
   - Should see: `GET /rule-packs/all returned X packs`

5. **Check database has packs**
   ```powershell
   python -c "from rulepack_manager import list_all_rulepacks; print(list_all_rulepacks())"
   ```

---

## ✨ Features Working

- ✅ List all rule packs in table
- ✅ Import YAML from textarea
- ✅ Upload YAML from file
- ✅ Publish draft packs
- ✅ Deprecate active packs
- ✅ Delete packs
- ✅ Edit draft packs (via Open button)
- ✅ Loading states
- ✅ Error messages
- ✅ Debug panel

---

## 📚 More Info

See `REACT_FRONTEND_FIX_SUMMARY.md` for:
- Detailed explanation of what was fixed
- Backend/frontend code changes
- JSON response shapes
- Troubleshooting guide