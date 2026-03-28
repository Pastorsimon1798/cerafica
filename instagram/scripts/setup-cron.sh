#!/bin/bash
# Setup script for Instagram Auto-Post cron job
# Run this once to set up Monday 6 AM automation

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_DIR="$(dirname "$SCRIPT_DIR")"
AUTO_POST_SCRIPT="$SCRIPT_DIR/auto-post.py"
CRON_LOG="$WORKSPACE_DIR/logs/cron.log"

echo "============================================"
echo "Instagram Auto-Post - Cron Setup"
echo "============================================"
echo ""
echo "Workspace: $WORKSPACE_DIR"
echo "Script: $AUTO_POST_SCRIPT"
echo "Log file: $CRON_LOG"
echo ""

# Check script exists
if [ ! -f "$AUTO_POST_SCRIPT" ]; then
    echo "ERROR: auto-post.py not found"
    exit 1
fi

# Make script executable
chmod +x "$AUTO_POST_SCRIPT"
echo "✓ Script is executable"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: python3 not found"
    exit 1
fi
echo "✓ Python found: $(python3 --version)"

# Check required packages
echo ""
echo "Checking dependencies..."

VENV_PYTHON="$SCRIPT_DIR/venv/bin/python"
VENV_PIP="$SCRIPT_DIR/venv/bin/pip"

# Check if venv exists
if [ ! -f "$VENV_PYTHON" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$SCRIPT_DIR/venv"
    source "$SCRIPT_DIR/venv/bin/activate"
    pip install -r "$SCRIPT_DIR/requirements.txt"
    playwright install chromium
fi

# Check dependencies in venv
$VENV_PYTHON -c "import playwright" 2>/dev/null || {
    echo "⚠️  Playwright not installed in venv"
    echo "   Installing..."
    $VENV_PIP install playwright
    $VENV_PYTHON -m playwright install chromium
    echo "✓ Playwright installed"
}

$VENV_PYTHON -c "import anthropic" 2>/dev/null || {
    echo "⚠️  Anthropic SDK not installed (optional for AI analysis)"
    echo "   Install with: $VENV_PIP install anthropic"
}

echo "✓ Dependencies checked"

# Create cron entry (using venv)
VENV_PYTHON="$SCRIPT_DIR/venv/bin/python"
CRON_ENTRY="0 6 * * 1 cd $WORKSPACE_DIR && $VENV_PYTHON $AUTO_POST_SCRIPT >> $CRON_LOG 2>&1"

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "auto-post.py"; then
    echo ""
    echo "⚠️  Cron job already exists"
    echo "   Current entry:"
    crontab -l | grep "auto-post.py"
    echo ""
    read -p "Replace existing entry? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted"
        exit 0
    fi
    # Remove existing entry
    crontab -l | grep -v "auto-post.py" | crontab -
fi

# Add new cron entry
(crontab -l 2>/dev/null; echo "$CRON_ENTRY") | crontab -

echo ""
echo "✓ Cron job added"
echo ""
echo "Schedule: Every Monday at 6:00 AM"
echo "Command: $CRON_ENTRY"
echo ""
echo "To verify: crontab -l"
echo "To test: $VENV_PYTHON $AUTO_POST_SCRIPT --test"
echo "To check status: $VENV_PYTHON $AUTO_POST_SCRIPT --status"
echo ""
echo "============================================"
echo "Setup complete!"
echo "============================================"
