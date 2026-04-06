#!/bin/bash
#
# Setup GitHub Actions + Netlify Integration
# Run this once to configure automatic deployment
#

set -e

# Source shared deployment library
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/shared/deploy-lib.sh"

echo "═══════════════════════════════════════════════════════════"
echo "  GITHUB ACTIONS + NETLIFY SETUP"
echo "═══════════════════════════════════════════════════════════"
echo ""

# Load environment and validate
load_env
validate_stripe_key
check_gh_auth
check_netlify_auth

echo ""
echo "🔐 Checking GitHub authentication..."

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
