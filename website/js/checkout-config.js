/**
 * Checkout Configuration
 * This file is automatically updated by deploy-checkout.sh
 * Do not edit manually - run ./deploy-checkout.sh instead
 */

const CHECKOUT_CONFIG = {
    // Local development
    local: 'http://localhost:8888/.netlify/functions/create-checkout',
    
    // Production - updated automatically during deployment
    production: 'https://cerafica-checkout.netlify.app/.netlify/functions/create-checkout',
    
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
