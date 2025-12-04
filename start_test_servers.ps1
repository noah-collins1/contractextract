# ContractExtract Testing Environment Startup Script
# Starts both HTTP Bridge API and Frontend Dev Server

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "ContractExtract Testing Environment" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if virtual environment is activated
if (-not $env:VIRTUAL_ENV) {
    Write-Host "Activating Python virtual environment..." -ForegroundColor Yellow
    & ".\.venv\Scripts\Activate.ps1"
}

# Initialize database
Write-Host "Initializing database..." -ForegroundColor Yellow
python -c "from infrastructure import init_db; init_db(); print('Database ready')"

Write-Host ""
Write-Host "Starting servers..." -ForegroundColor Green
Write-Host "- HTTP Bridge API: http://localhost:8000" -ForegroundColor White
Write-Host "- Frontend UI: http://localhost:5173" -ForegroundColor White
Write-Host "- API Docs: http://localhost:8000/docs" -ForegroundColor White
Write-Host ""
Write-Host "Press Ctrl+C to stop both servers" -ForegroundColor Yellow
Write-Host ""

# Start HTTP bridge in background
$httpBridge = Start-Process -FilePath "python" -ArgumentList "http_bridge.py" -PassThru -NoNewWindow

# Wait a moment for backend to start
Start-Sleep -Seconds 3

# Start frontend dev server
Push-Location frontend
try {
    npm run dev
} finally {
    Pop-Location
    # Clean up HTTP bridge when frontend stops
    if ($httpBridge -and !$httpBridge.HasExited) {
        Write-Host "`nStopping HTTP Bridge..." -ForegroundColor Yellow
        Stop-Process -Id $httpBridge.Id -Force
    }
}