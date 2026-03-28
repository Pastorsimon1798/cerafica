#!/bin/bash
#
# Setup GitHub Actions + Netlify Integration
# Run this once to configure automatic deployment
#

set -e

echo "═══════════════════════════════════════════════════════════"
echo "  GITHUB ACTIONS + NETLIFY SETUP"
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

# Check for gh CLI
if ! command -v gh &> /dev/null; then
    echo -e "${YELLOW}⚠️  GitHub CLI not found${NC}"
    echo "   Install: https://cli.github.com/"
    exit 1
fi

# Check for netlify CLI
if ! command -v netlify &> /dev/null; then
    echo -e "${YELLOW}⚠️  Netlify CLI not found${NC}"
    echo "   Run: npm install -g netlify-cli@20"
    exit 1
fi

echo ""
echo "🔐 Checking GitHub authentication..."
gh auth status || (echo "Run: gh auth login" && exit 1)

echo ""
echo "🌐 Creating Netlify site..."

# Create Netlify site if not exists
if [ ! -f ".netlify/state.json" ]; then
    netlify sites:create --name "cerafica-checkout-$(date +%s)" --manual
fi

SITE_ID=$(cat .netlify/state.json | grep -o '"siteId":"[^"]*"' | cut -d'"' -f4)

echo -e "${GREEN}✓ Netlify site created: ${SITE_ID}${NC}"

# Get Netlify personal access token
echo ""
echo "🔑 Getting Netlify token..."
NETLIFY_TOKEN=$(cat ~/.netlify/config.json 2>/dev/null | grep -o '"token":"[^"]*"' | cut -d'"' -f4 || echo "")

if [ -z "$NETLIFY_TOKEN" ]; then
    echo -e "${YELLOW}⚠️  Netlify token not found${NC}"
    echo "   Get token from: https://app.netlify.com/user/applications/personal"
    read -p "   Paste token: " NETLIFY_TOKEN
fi

echo ""
echo "📤 Setting GitHub secrets..."

# Set GitHub secrets
gh secret set NETLIFY_AUTH_TOKEN --body "$NETLIFY_TOKEN"
gh secret set NETLIFY_SITE_ID --body "$SITE_ID"
gh secret set STRIPE_SECRET_KEY --body "$STRIPE_SECRET_KEY"

echo -e "${GREEN}✓ Secrets set${NC}"

echo ""
echo "🚀 Triggering first deployment..."
git add .
git commit -m "Setup multi-item checkout with GitHub Actions" || true
git push

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  ✓ SETUP COMPLETE${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo "   From now on, every push to GitHub will:"
echo "   1. Deploy your site to Netlify"
echo "   2. Deploy the checkout function"
echo "   3. Update all configurations automatically"
echo ""
echo "   Check deployment status:"
echo "   https://github.com/$(gh repo view --json nameWithOwner -q .nameWithOwner)/actions"
echo ""
