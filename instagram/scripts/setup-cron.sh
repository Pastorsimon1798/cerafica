#!/bin/bash
# Setup script for Cerafica Instagram automation cron jobs
# Run once to install the full weekly schedule.
#
# Schedule installed:
#   Sunday  8 PM  — weekly orchestrator (sync + captions + website listings)
#   1st of month  — performance analysis
#   Monday  6 AM  — fallback auto-post (if Sunday run had nothing)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
CRON_LOG_DIR="$WORKSPACE_DIR/instagram/logs"

echo "============================================"
echo "Cerafica — Cron Setup"
echo "============================================"
echo ""
echo "Workspace: $WORKSPACE_DIR"
echo ""

# Check script exists
if [ ! -f "$SCRIPT_DIR/weekly-orchestrator.py" ]; then
    echo "ERROR: weekly-orchestrator.py not found at $SCRIPT_DIR"
    exit 1
fi
if [ ! -f "$SCRIPT_DIR/auto-post.py" ]; then
    echo "ERROR: auto-post.py not found"
    exit 1
fi

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: python3 not found"
    exit 1
fi
echo "✓ Python found: $(python3 --version)"

# Resolve venv python
VENV_PYTHON="$SCRIPT_DIR/venv/bin/python"
VENV_PIP="$SCRIPT_DIR/venv/bin/pip"

if [ ! -f "$VENV_PYTHON" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$SCRIPT_DIR/venv"
    "$VENV_PIP" install -r "$SCRIPT_DIR/requirements.txt"
    "$VENV_PYTHON" -m playwright install chromium 2>/dev/null || true
fi
echo "✓ Venv ready: $VENV_PYTHON"

# Make scripts executable
chmod +x "$SCRIPT_DIR/weekly-orchestrator.py" "$SCRIPT_DIR/auto-post.py"
echo "✓ Scripts are executable"

# Create log dir
mkdir -p "$CRON_LOG_DIR"
echo "✓ Log directory: $CRON_LOG_DIR"

# Build cron entries
ORCHESTRATOR_ENTRY="0 20 * * 0 cd $WORKSPACE_DIR && $VENV_PYTHON $SCRIPT_DIR/weekly-orchestrator.py >> $CRON_LOG_DIR/orchestrator.log 2>&1"
ANALYSIS_ENTRY="0 8 1 * * cd $WORKSPACE_DIR && $VENV_PYTHON $SCRIPT_DIR/analyze-performance.py >> $CRON_LOG_DIR/analysis.log 2>&1"
FALLBACK_ENTRY="0 6 * * 1 cd $WORKSPACE_DIR && $VENV_PYTHON $SCRIPT_DIR/auto-post.py >> $CRON_LOG_DIR/cron.log 2>&1"

# Remove any existing cerafica cron entries
CLEAN_CRONTAB=$(crontab -l 2>/dev/null | grep -v "cerafica\|weekly-orchestrator\|auto-post\.py\|analyze-performance" || true)

# Confirm before installing
echo ""
echo "Will install these cron jobs:"
echo ""
echo "  [Sunday 8 PM]     Weekly orchestration (main automation)"
echo "  $ORCHESTRATOR_ENTRY"
echo ""
echo "  [1st of month]    Performance analysis"
echo "  $ANALYSIS_ENTRY"
echo ""
echo "  [Monday 6 AM]     Fallback auto-post"
echo "  $FALLBACK_ENTRY"
echo ""

read -p "Install? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted. Nothing changed."
    exit 0
fi

# Install
(
  echo "$CLEAN_CRONTAB"
  echo "$ORCHESTRATOR_ENTRY"
  echo "$ANALYSIS_ENTRY"
  echo "$FALLBACK_ENTRY"
) | grep -v '^$' | crontab -

echo ""
echo "✓ Cron jobs installed"
echo ""
echo "To verify:  crontab -l"
echo "To test:    $VENV_PYTHON $SCRIPT_DIR/weekly-orchestrator.py --dry-run"
echo "To status:  $VENV_PYTHON $SCRIPT_DIR/weekly-orchestrator.py --status"
echo ""
echo "============================================"
echo "Setup complete!"
echo "============================================"
