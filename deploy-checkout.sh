#!/bin/bash
#
# Cerafica Multi-Item Checkout Deployment Script
# Automates Netlify setup and deployment
#

set -e

# Source shared deployment library
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/shared/deploy-lib.sh"

echo "═══════════════════════════════════════════════════════════"
echo "  CERAFICA MULTI-ITEM CHECKOUT DEPLOYMENT"
echo "═══════════════════════════════════════════════════════════"
echo ""

# Check prerequisites
echo "📋 Checking prerequisites..."

# Check for Node.js
if ! command -v node &> /dev/null; then
    log_error "Node.js is required but not installed. Install from: https://nodejs.org/"
    exit 1
fi

# Load environment and validate
load_env
validate_stripe_key
check_netlify_auth

echo -e "${GREEN}✓ Prerequisites met${NC}"
echo ""

# Check if already linked to Netlify
if [ -d ".netlify" ]; then
    echo "🌐 Site already linked to Netlify"
else
    echo "🌐 Setting up Netlify site..."
    echo ""
    echo "   You'll need to:"
    echo "   1. Authorize Netlify CLI (opens browser)"
    echo "   2. Choose 'Create & configure a new site'"
    echo "   3. Select your team"
    echo "   4. Enter a site name (e.g., 'cerafica-checkout')"
    echo ""
    
    netlify init
    
    echo ""
    echo -e "${GREEN}✓ Netlify site created${NC}"
fi

echo ""
echo "🔐 Setting environment variables..."

# Get site info
SITE_URL=$(netlify site:info --json 2>/dev/null | grep -o '"url":"[^"]*"' | cut -d'"' -f4 || echo "")

if [ -z "$SITE_URL" ]; then
    echo -e "${RED}❌ Could not get site URL. Please run 'netlify init' first.${NC}"
    exit 1
fi

# Set environment variables
netlify env:set STRIPE_SECRET_KEY "$STRIPE_SECRET_KEY"
netlify env:set CERAFICA_DOMAIN "https://cerafica.com"

echo -e "${GREEN}✓ Environment variables set${NC}"
echo ""

# Update checkout-config.js with correct function URL
SITE_NAME=$(echo "$SITE_URL" | sed 's|https://||' | sed 's|.netlify.app||')
FUNCTION_URL="https://${SITE_NAME}.netlify.app/.netlify/functions/create-checkout"

echo "📝 Updating checkout configuration..."
echo "   Function URL: $FUNCTION_URL"

# Update the config file
cat > website/js/checkout-config.js << EOF
/**
 * Checkout Configuration
 * This file is automatically updated by deploy-checkout.sh
 * Do not edit manually - run ./deploy-checkout.sh instead
 */

const CHECKOUT_CONFIG = {
    // Local development
    local: 'http://localhost:8888/.netlify/functions/create-checkout',
    
    // Production - updated automatically during deployment
    production: '$FUNCTION_URL',
    
    // Get the correct URL based on environment
    getFunctionUrl: function() {
        const isLocal = window.location.hostname === 'localhost' || 
                       window.location.hostname === '127.0.0.1';
        return isLocal ? this.local : this.production;
    }
};

// Make available globally
if (typeof window !== 'undefined') {
    window.CHECKOUT_CONFIG = CHECKOUT_CONFIG;
}
EOF

echo -e "${GREEN}✓ Configuration updated${NC}"
echo ""

# Deploy
echo "🚀 Deploying to Netlify..."
netlify deploy --prod --message="Multi-item checkout deployment"

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  ✓ DEPLOYMENT COMPLETE${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo "   Your checkout function is live at:"
echo "   $FUNCTION_URL"
echo ""
echo "   Next steps:"
echo "   1. Test the checkout: Add 2+ items to cart and click checkout"
echo "   2. Use Stripe test card: 4242 4242 4242 4242"
echo "   3. When ready for production, switch to live Stripe keys:"
echo "      netlify env:set STRIPE_SECRET_KEY sk_live_YOUR_LIVE_KEY"
echo ""
echo "   To test locally: npm run dev"
echo ""
