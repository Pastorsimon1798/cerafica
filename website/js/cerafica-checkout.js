/**
 * Cerafica Unified Checkout Integration (Kyanite API)
 *
 * This script optionally overrides the existing checkout flow to use the
 * Kyanite-hosted API instead of the Netlify function.
 *
 * To enable: set window.CERAFICA_API_BASE = 'https://kyanitelabs.tech/api/cerafica'
 * before loading this script, or edit the constant below.
 *
 * If the API is not configured (no Stripe key), the script falls back to
 * the original Netlify behavior silently.
 */
(function() {
    'use strict';

    const API_BASE = window.CERAFICA_API_BASE || 'https://kyanitelabs.tech/api/cerafica';
    const HEALTH_URL = `${API_BASE}/health`;
    const CHECKOUT_URL = `${API_BASE}/checkout`;

    let apiAvailable = false;

    // Quick health check on load
    async function checkApi() {
        try {
            const res = await fetch(HEALTH_URL, { method: 'GET' });
            const data = await res.json();
            apiAvailable = res.ok && data.stripe_configured === true;
            if (apiAvailable) {
                console.log('[CeraficaCheckout] Kyanite API active');
                overrideCheckoutButtons();
            } else {
                console.log('[CeraficaCheckout] Kyanite API unavailable or Stripe not configured — keeping Netlify fallback');
            }
        } catch (err) {
            console.log('[CeraficaCheckout] Kyanite API unreachable — keeping Netlify fallback');
        }
    }

    // Override cart checkout button
    function overrideCheckoutButtons() {
        const checkoutBtn = document.getElementById('checkout-btn');
        if (!checkoutBtn || checkoutBtn.dataset.ceraficaHooked) return;
        checkoutBtn.dataset.ceraficaHooked = 'true';

        checkoutBtn.addEventListener('click', async (e) => {
            e.preventDefault();
            e.stopPropagation();

            const cart = (typeof getCart === 'function') ? getCart() : [];
            if (!cart || cart.length === 0) {
                if (typeof showToast === 'function') showToast('Your cart is empty', 'error');
                return;
            }

            const originalText = checkoutBtn.textContent;
            checkoutBtn.textContent = 'PROCESSING...';
            checkoutBtn.disabled = true;

            try {
                const res = await fetch(CHECKOUT_URL, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ items: cart })
                });
                const data = await res.json();

                if (res.ok && data.session_url) {
                    window.location.href = data.session_url;
                } else {
                    throw new Error(data.error || 'Checkout failed');
                }
            } catch (err) {
                console.error('[CeraficaCheckout]', err);
                if (typeof showToast === 'function') showToast(err.message || 'Checkout failed. Please try again.', 'error');
                checkoutBtn.textContent = originalText;
                checkoutBtn.disabled = false;
            }
        }, true); // use capture to run before the original handler
    }

    // Start
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', checkApi);
    } else {
        checkApi();
    }
})();
