#!/bin/bash
#
# Setup GitHub Actions for Netlify deployment
# One-time setup - run this, then forget about it
#

set -e

echo "═══════════════════════════════════════════════════════════"
echo "  CHECKOUT DEPLOYMENT SETUP"
echo "═══════════════════════════════════════════════════════════"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Load Stripe key from .env
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
fi

if [ -z "$STRIPE_SECRET_KEY" ]; then
    echo -e "${RED}❌ STRIPE_SECRET_KEY not found in .env${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Stripe key loaded${NC}"

# Verify GitHub CLI
gh auth status || (echo "Run: gh auth login" && exit 1)

echo ""
echo "🌐 Creating Netlify site (website folder only)..."

# Create Netlify site with website as publish directory
if [ ! -d ".netlify" ]; then
    # Login if needed
    netlify status || netlify login
    
    # Create site
    netlify sites:create --name "cerafica-checkout" --manual
fi

SITE_ID=$(cat .netlify/state.json 2>/dev/null | grep '"siteId"' | sed 's/.*"siteId":"\([^"]*\)".*/\1/')

if [ -z "$SITE_ID" ]; then
    echo -e "${RED}❌ Could not get site ID${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Netlify site: ${SITE_ID}${NC}"

# Get Netlify token
NETLIFY_TOKEN=$(cat ~/.netlify/config.json 2>/dev/null | grep '"token"' | sed 's/.*"token":"\([^"]*\)".*/\1/' || echo "")

if [ -z "$NETLIFY_TOKEN" ]; then
    echo ""
    echo "Get token from: https://app.netlify.com/user/applications/personal"
    read -p "Paste Netlify token: " NETLIFY_TOKEN
fi

echo ""
echo "📤 Setting GitHub secrets..."

# Set secrets
gh secret set NETLIFY_AUTH_TOKEN -b"${NETLIFY_TOKEN}"
gh secret set NETLIFY_SITE_ID -b"${SITE_ID}"
gh secret set STRIPE_SECRET_KEY -b"${STRIPE_SECRET_KEY}"

echo -e "${GREEN}✓ Secrets configured${NC}"

echo ""
echo "🚀 Pushing to trigger deployment..."
git add -A
git commit -m "Setup multi-item checkout deployment" || true
git push

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  ✓ DONE${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo "   From now on, pushing to GitHub automatically deploys:"
echo "   - Only the website/ folder (not instagram/, tools/, etc.)"
echo "   - The checkout function"
echo "   - Updates to shop.js and checkout-config.js"
echo ""
echo "   Monitor deployments:"
echo "   gh workflow view deploy-checkout"
echo ""
