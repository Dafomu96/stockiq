#!/usr/bin/env bash
# StockIQ — Unix/Mac setup script
# Usage: bash setup.sh
# Requires: Python 3.11+, Node 20+

set -e
BOLD=$(tput bold 2>/dev/null || echo "")
RESET=$(tput sgr0 2>/dev/null || echo "")
GREEN=$(tput setaf 2 2>/dev/null || echo "")
YELLOW=$(tput setaf 3 2>/dev/null || echo "")
RED=$(tput setaf 1 2>/dev/null || echo "")
CYAN=$(tput setaf 6 2>/dev/null || echo "")

echo ""
echo "${BOLD}${CYAN}StockIQ — Project Setup${RESET}"
echo "${CYAN}========================${RESET}"
echo ""

# ── Prerequisites ──────────────────────────────────────────────────────────────

echo "${YELLOW}→ Checking prerequisites...${RESET}"

if ! command -v python3 &>/dev/null; then
    echo "${RED}  ✗ Python 3 not found. Install from https://python.org/downloads${RESET}"
    exit 1
fi
echo "${GREEN}  ✓ $(python3 --version)${RESET}"

if ! command -v node &>/dev/null; then
    echo "${RED}  ✗ Node.js not found. Install from https://nodejs.org${RESET}"
    exit 1
fi
echo "${GREEN}  ✓ Node $(node --version)${RESET}"

if ! command -v git &>/dev/null; then
    echo "${RED}  ✗ Git not found. Install from https://git-scm.com${RESET}"
    exit 1
fi
echo "${GREEN}  ✓ $(git --version)${RESET}"

# ── Virtual environment ────────────────────────────────────────────────────────

echo ""
echo "${YELLOW}→ Creating Python virtual environment...${RESET}"

if [ -d ".venv" ]; then
    echo "  .venv already exists — skipping creation"
else
    python3 -m venv .venv
    echo "${GREEN}  ✓ .venv created${RESET}"
fi

# ── Python dependencies ────────────────────────────────────────────────────────

echo "${YELLOW}→ Installing Python dependencies (this may take a minute)...${RESET}"
.venv/bin/pip install --upgrade pip -q
.venv/bin/pip install -r requirements.txt -q
echo "${GREEN}  ✓ Python dependencies installed${RESET}"

# ── Frontend dependencies ──────────────────────────────────────────────────────

echo "${YELLOW}→ Installing frontend dependencies...${RESET}"
(cd frontend && npm install --silent)
echo "${GREEN}  ✓ Node modules installed${RESET}"

# ── Environment file ───────────────────────────────────────────────────────────

echo "${YELLOW}→ Setting up .env file...${RESET}"
if [ -f ".env" ]; then
    echo "  .env already exists — skipping"
else
    cp .env.example .env
    echo "${GREEN}  ✓ .env created from .env.example${RESET}"
fi

# ── Run tests ──────────────────────────────────────────────────────────────────

echo "${YELLOW}→ Running test suite...${RESET}"
if .venv/bin/pytest tests/ -q --no-header; then
    echo "${GREEN}  ✓ All tests passed${RESET}"
else
    echo "${RED}  ✗ Some tests failed — check output above${RESET}"
fi

# ── Done ───────────────────────────────────────────────────────────────────────

echo ""
echo "${GREEN}${BOLD}✅ Setup complete!${RESET}"
echo ""
echo "${CYAN}Next steps:${RESET}"
echo "  Activate venv:    source .venv/bin/activate"
echo "  Run tests:        pytest tests/"
echo "  FastAPI (API):    uvicorn backend.main:app --reload --port 8000"
echo "  Streamlit (MVP):  streamlit run app/streamlit_app.py"
echo "  React (frontend): cd frontend && npm run dev"
echo "  All via Docker:   docker compose up"
echo ""
