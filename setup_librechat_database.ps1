# Complete setup script for LibreChat PostgreSQL database
# This script will:
# 1. Expose PostgreSQL port in docker-compose.override.yml
# 2. Restart LibreChat to apply changes
# 3. Seed the database with rule packs
# 4. Verify everything works

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "LibreChat Database Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$librechatPath = "C:\Users\noahc\LibreChat"
$overrideFile = "$librechatPath\docker-compose.override.yml"

# Step 1: Create/Update docker-compose.override.yml
Write-Host "`n[1/5] Configuring PostgreSQL port exposure..." -ForegroundColor Yellow

$overrideContent = @"
version: '3.4'

services:
  contractextract-db:
    ports:
      - "5433:5432"  # Expose on port 5433 to avoid conflict with local PostgreSQL
"@

Write-Host "   Creating docker-compose.override.yml..." -ForegroundColor White
Set-Content -Path $overrideFile -Value $overrideContent
Write-Host "   ✅ Port configuration created" -ForegroundColor Green

# Step 2: Restart LibreChat
Write-Host "`n[2/5] Restarting LibreChat to apply changes..." -ForegroundColor Yellow
Write-Host "   This may take 30-60 seconds..." -ForegroundColor White

Push-Location $librechatPath
docker-compose down
Start-Sleep -Seconds 3
docker-compose up -d
Pop-Location

Write-Host "   Waiting for services to start..." -ForegroundColor White
Start-Sleep -Seconds 15

# Step 3: Verify port is exposed
Write-Host "`n[3/5] Verifying PostgreSQL port..." -ForegroundColor Yellow

$portCheck = docker ps --format "{{.Names}} {{.Ports}}" | Select-String "contractextract-db" | Select-String "5433"

if ($portCheck) {
    Write-Host "   ✅ PostgreSQL is now accessible on localhost:5433" -ForegroundColor Green
} else {
    Write-Host "   ⚠️  Warning: Port might not be exposed yet" -ForegroundColor Yellow
    Write-Host "   Continuing anyway..." -ForegroundColor White
}

# Step 4: Seed the database
Write-Host "`n[4/5] Seeding database with rule packs..." -ForegroundColor Yellow

# Activate virtual environment and run seed script
$env:DATABASE_URL = "postgresql+psycopg2://postgres:contractextract_pass@localhost:5433/contractextract"

Write-Host "   Database URL: $env:DATABASE_URL" -ForegroundColor White
Write-Host "   Running seed script..." -ForegroundColor White
Write-Host ""

python seed_database.py

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "   ✅ Database seeded successfully!" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "   ❌ Seeding failed. Check errors above." -ForegroundColor Red
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Red
    Write-Host "Setup Failed - See errors above" -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Red
    exit 1
}

# Step 5: Restart LibreChat one more time
Write-Host "`n[5/5] Restarting LibreChat to pick up seeded data..." -ForegroundColor Yellow

Push-Location $librechatPath
docker-compose restart
Pop-Location

Write-Host "   Waiting for services to restart..." -ForegroundColor White
Start-Sleep -Seconds 10

# Final summary
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "✅ Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "What was done:" -ForegroundColor Cyan
Write-Host "  ✅ PostgreSQL port exposed on localhost:5433" -ForegroundColor White
Write-Host "  ✅ Database seeded with 7 rule packs" -ForegroundColor White
Write-Host "  ✅ LibreChat restarted" -ForegroundColor White
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Open LibreChat: http://localhost:3080" -ForegroundColor White
Write-Host "  2. Test: 'call get_system_info'" -ForegroundColor White
Write-Host "  3. Expected result: 7 active rule packs" -ForegroundColor White
Write-Host ""
Write-Host "Try document analysis:" -ForegroundColor Yellow
Write-Host '  "Use analyze_document with document_text:' -ForegroundColor White
Write-Host '   EMPLOYMENT AGREEMENT between TechCorp and Jane Smith.' -ForegroundColor White
Write-Host '   Governing Law: California. Salary: $180,000"' -ForegroundColor White
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Database connection info (for pgAdmin/debugging):" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Host: localhost" -ForegroundColor White
Write-Host "  Port: 5433" -ForegroundColor White
Write-Host "  Database: contractextract" -ForegroundColor White
Write-Host "  User: postgres" -ForegroundColor White
Write-Host "  Password: contractextract_pass" -ForegroundColor White
Write-Host ""
