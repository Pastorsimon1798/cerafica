#!/bin/bash
# Overnight batch: process all spinning pottery videos
# Videos: IMG_4950 (Ignix-5), IMG_4951 (Cromix-0), IMG_4952 (Ceruleix-2)
#
# Usage: bash scripts/batch_overnight.sh 2>&1 | tee /tmp/batch_overnight.log

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKSPACE="$(dirname "$SCRIPT_DIR")"
LOG="/tmp/batch_overnight.log"

echo "============================================"
echo "Overnight Batch - $(date)"
echo "============================================"
echo ""

RUNS=(
    "$HOME/Downloads/IMG_4950.mov Ignix-5"
    "$HOME/Downloads/IMG_4951.mov Cromix-0"
    "$HOME/Downloads/IMG_4952.mov Ceruleix-2"
)

TOTAL=${#RUNS[@}
SUCCESS=0
FAIL=0

for i in "${!RUNS[@]}"; do
    ENTRY=(${RUNS[$i]})
    VIDEO="${ENTRY[0]}"
    PLANET="${ENTRY[1]}"
    NUM=$((i + 1))

    echo "--------------------------------------------"
    echo "[$NUM/$TOTAL] $(basename "$VIDEO") → $PLANET"
    echo "  Started: $(date)"
    echo "--------------------------------------------"

    if [ ! -f "$VIDEO" ]; then
        echo "  SKIP: $VIDEO not found"
        FAIL=$((FAIL + 1))
        echo ""
        continue
    fi

    if python3 "$SCRIPT_DIR/frame_video.py" \
        --input "$VIDEO" \
        --planet "$PLANET" \
        --mask-interval 3; then
        echo "  Finished: $(date)"
        SUCCESS=$((SUCCESS + 1))
    else
        echo "  FAILED: $(date)"
        FAIL=$((FAIL + 1))
    fi
    echo ""
done

echo "============================================"
echo "Batch complete - $(date)"
echo "  Success: $SUCCESS"
echo "  Failed:  $FAIL"
echo "============================================"

# Notify when done (macOS)
osascript -e "display notification \"Batch done: $SUCCESS ok, $FAIL failed\" with title \"Video Pipeline\""
