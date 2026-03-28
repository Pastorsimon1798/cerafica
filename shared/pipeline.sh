#!/bin/bash
# Cerafica Shared Pipeline
# Processes product videos for both Instagram and Website
#
# Usage:
#   ./shared/pipeline.sh                    # Process all pending
#   ./shared/pipeline.sh <product-name>     # Process single product
#   ./shared/pipeline.sh --sync             # Sync Instagram -> Website
#   ./shared/pipeline.sh --status           # Show sync status

set -e

CERAFICA_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
INSTAGRAM_FRAMED="$CERAFICA_ROOT/output/framed/video"
WEBSITE_PRODUCTS="$CERAFICA_ROOT/website/images/products"
PRODUCTS_JSON="$CERAFICA_ROOT/website/data/products.json"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Sync Instagram framed videos to Website
sync_to_website() {
    log_info "Syncing Instagram videos to Website..."
    
    local synced=0
    local skipped=0
    
    for vid in "$INSTAGRAM_FRAMED"/*.mp4; do
        [ -f "$vid" ] || continue
        
        local name=$(basename "$vid")
        local web_name=$(echo "$name" | tr '[:upper:]' '[:lower:]')
        local web_path="$WEBSITE_PRODUCTS/$web_name"
        
        if [ -f "$web_path" ]; then
            # Compare file sizes
            local ig_size=$(stat -f%z "$vid" 2>/dev/null || stat -c%s "$vid" 2>/dev/null)
            local web_size=$(stat -f%z "$web_path" 2>/dev/null || stat -c%s "$web_path" 2>/dev/null)
            
            if [ "$ig_size" -eq "$web_size" ]; then
                log_warn "SKIP: $web_name (already in sync)"
                ((skipped++))
                continue
            fi
        fi
        
        cp "$vid" "$web_path"
        log_info "SYNC: $name -> $web_name"
        ((synced++))
    done
    
    echo ""
    log_info "Sync complete: $synced synced, $skipped skipped"
}

# Show status of both locations
show_status() {
    echo "=== CERAFICA PIPELINE STATUS ==="
    echo ""
    echo "Instagram framed videos:"
    ls -1 "$INSTAGRAM_FRAMED"/*.mp4 2>/dev/null | wc -l | xargs echo "  Count:"
    
    echo ""
    echo "Website product videos:"
    ls -1 "$WEBSITE_PRODUCTS"/*_rotating.mp4 2>/dev/null | wc -l | xargs echo "  Count:"
    
    echo ""
    echo "Synced products:"
    for vid in "$INSTAGRAM_FRAMED"/*.mp4; do
        [ -f "$vid" ] || continue
        local name=$(basename "$vid" | tr '[:upper:]' '[:lower:]')
        if [ -f "$WEBSITE_PRODUCTS/$name" ]; then
            local ig_res=$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=s=x:p=0 "$vid" 2>/dev/null)
            echo "  ✓ $name ($ig_res)"
        fi
    done
    
    echo ""
    echo "Missing from website:"
    for vid in "$INSTAGRAM_FRAMED"/*.mp4; do
        [ -f "$vid" ] || continue
        local name=$(basename "$vid" | tr '[:upper:]' '[:lower:]')
        if [ ! -f "$WEBSITE_PRODUCTS/$name" ]; then
            echo "  ✗ $name"
        fi
    done
}

# Main
case "${1:-}" in
    --sync)
        sync_to_website
        ;;
    --status)
        show_status
        ;;
    --help|-h|help)
        echo "Cerafica Shared Pipeline"
        echo ""
        echo "Usage:"
        echo "  ./shared/pipeline.sh --sync       Sync Instagram -> Website"
        echo "  ./shared/pipeline.sh --status     Show sync status"
        echo "  ./shared/pipeline.sh --help       Show this help"
        ;;
    *)
        if [ -z "$1" ]; then
            show_status
            echo ""
            echo "Run with --sync to sync videos or --help for options"
        else
            log_error "Unknown option: $1"
            echo "Run with --help for usage"
            exit 1
        fi
        ;;
esac
