# StockIQ — Windows PowerShell setup script
# Usage: .\setup.ps1
# Requires: Python 3.11+, Node 20+

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "StockIQ — Project Setup" -ForegroundColor Cyan
Write-Host "========================" -ForegroundColor Cyan
Write-Host ""

# ── Check prerequisites ────────────────────────────────────────────────────────

Write-Host "→ Checking prerequisites..." -ForegroundColor Yellow

try {
    $pyVersion = python --version 2>&1
    Write-Host "  ✓ $pyVersion" -ForegroundColor Green
} catch {
    Write-Host "  ✗ Python not found. Install from https://python.org/downloads" -ForegroundColor Red
    exit 1
}

try {
    $nodeVersion = node --version 2>&1
    Write-Host "  ✓ Node $nodeVersion" -ForegroundColor Green
} catch {
    Write-Host "  ✗ Node.js not found. Install from https://nodejs.org" -ForegroundColor Red
    exit 1
}

try {
    $gitVersion = git --version 2>&1
    Write-Host "  ✓ $gitVersion" -ForegroundColor Green
} catch {
    Write-Host "  ✗ Git not found. Install from https://git-scm.com" -ForegroundColor Red
    exit 1
}

# ── Python virtual environment ─────────────────────────────────────────────────

Write-Host ""
Write-Host "→ Creating Python virtual environment..." -ForegroundColor Yellow

if (Test-Path ".venv") {
    Write-Host "  .venv already exists — skipping creation" -ForegroundColor DarkGray
} else {
    python -m venv .venv
    Write-Host "  ✓ .venv created" -ForegroundColor Green
}

# ── Python dependencies ────────────────────────────────────────────────────────

Write-Host "→ Installing Python dependencies (this may take a minute)..." -ForegroundColor Yellow
.venv\Scripts\pip install --upgrade pip -q
.venv\Scripts\pip install -r requirements.txt -q
Write-Host "  ✓ Python dependencies installed" -ForegroundColor Green

# ── Frontend dependencies ──────────────────────────────────────────────────────

Write-Host "→ Installing frontend dependencies..." -ForegroundColor Yellow
Set-Location frontend
npm install --silent
Set-Location ..
Write-Host "  ✓ Node modules installed" -ForegroundColor Green

# ── Environment file ───────────────────────────────────────────────────────────

Write-Host "→ Setting up .env file..." -ForegroundColor Yellow
if (Test-Path ".env") {
    Write-Host "  .env already exists — skipping" -ForegroundColor DarkGray
} else {
    Copy-Item .env.example .env
    Write-Host "  ✓ .env created from .env.example" -ForegroundColor Green
}

# ── Run tests ──────────────────────────────────────────────────────────────────

Write-Host "→ Running test suite..." -ForegroundColor Yellow
.venv\Scripts\pytest tests\ -q --no-header 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✓ All tests passed" -ForegroundColor Green
} else {
    Write-Host "  ✗ Some tests failed — check output above" -ForegroundColor Red
}

# ── Done ───────────────────────────────────────────────────────────────────────

Write-Host ""
Write-Host "✅ Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  Activate venv:    .venv\Scripts\Activate.ps1"
Write-Host "  Run tests:        pytest tests\"
Write-Host "  FastAPI (API):    uvicorn backend.main:app --reload --port 8000"
Write-Host "  Streamlit (MVP):  streamlit run app\streamlit_app.py"
Write-Host "  React (frontend): cd frontend && npm run dev"
Write-Host "  All via Docker:   docker compose up"
Write-Host ""
