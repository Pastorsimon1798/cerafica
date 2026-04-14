/**
 * Cerafica Waitlist Integration
 * Injects waitlist capture into the product modal for sold-out / coming-soon pieces.
 * API: POST https://kyanitelabs.tech/api/cerafica/waitlist/join
 */
(function() {
    'use strict';

    const API_BASE = 'https://kyanitelabs.tech/api/cerafica';

    // Create waitlist DOM if it doesn't exist
    function ensureWaitlistUI() {
        if (document.getElementById('modal-waitlist')) return;

        const modalActions = document.querySelector('.modal__actions');
        if (!modalActions) return;

        const waitlistDiv = document.createElement('div');
        waitlistDiv.id = 'modal-waitlist';
        waitlistDiv.className = 'modal__waitlist';
        waitlistDiv.style.display = 'none';
        waitlistDiv.style.marginTop = '1rem';
        waitlistDiv.innerHTML = `
            <p class="modal__waitlist-text" style="margin:0 0 .5rem; font-size:.9rem; color:var(--text-muted);">
                This piece is unavailable. Join the waitlist and be first to know when it returns.
            </p>
            <div class="modal__waitlist-form" style="display:flex; gap:.5rem;">
                <input
                    type="email"
                    class="modal__waitlist-input"
                    placeholder="your@email.com"
                    aria-label="Email for waitlist"
                    style="flex:1; padding:.5rem .75rem; border:1px solid var(--border); background:var(--bg-elevated); color:var(--text); border-radius:4px;"
                >
                <button
                    class="btn btn--ghost modal__waitlist-btn"
                    style="white-space:nowrap;"
                >JOIN WAITLIST</button>
            </div>
            <p class="modal__waitlist-msg" style="margin:.5rem 0 0; font-size:.85rem; min-height:1.2rem;"></p>
        `;
        modalActions.parentNode.insertBefore(waitlistDiv, modalActions.nextSibling);
    }

    // Show/hide waitlist based on product availability
    function syncWaitlist(product) {
        ensureWaitlistUI();
        const waitlist = document.getElementById('modal-waitlist');
        if (!waitlist) return;

        const show = !product.available || product.coming_soon;
        waitlist.style.display = show ? 'block' : 'none';

        if (show) {
            const text = waitlist.querySelector('.modal__waitlist-text');
            if (text) {
                text.textContent = product.coming_soon
                    ? 'This drop is coming soon. Join the waitlist to be notified first.'
                    : 'This piece is sold out. Join the waitlist and be first to know when it returns.';
            }
            // Reset state
            const input = waitlist.querySelector('.modal__waitlist-input');
            const btn = waitlist.querySelector('.modal__waitlist-btn');
            const msg = waitlist.querySelector('.modal__waitlist-msg');
            if (input) input.value = '';
            if (btn) { btn.disabled = false; btn.textContent = 'JOIN WAITLIST'; }
            if (msg) { msg.textContent = ''; msg.style.color = ''; }
            waitlist.dataset.productId = product.id;
            waitlist.dataset.productName = product.name;
        }
    }

    // Submit waitlist entry
    async function submitWaitlist(email, productId, productName) {
        try {
            const res = await fetch(`${API_BASE}/waitlist/join`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, product_id: productId, product_name: productName })
            });
            const data = await res.json();
            return { ok: res.ok, msg: data.ok ? "You're on the list." : (data.error || 'Something went wrong.') };
        } catch (err) {
            return { ok: false, msg: 'Network error. Please try again.' };
        }
    }

    // Hook into the existing openModal function
    function hookModal() {
        if (typeof openModal === 'function' && !window.__ceraficaWaitlistHooked) {
            window.__ceraficaWaitlistHooked = true;
            const original = openModal;
            window.openModal = function(productId) {
                original(productId);
                const product = (typeof products !== 'undefined') ? products.find(p => p.id === productId) : null;
                if (product) syncWaitlist(product);
            };
        }
    }

    // Delegate click for waitlist button
    document.addEventListener('click', (e) => {
        const btn = e.target.closest('.modal__waitlist-btn');
        if (!btn) return;

        const waitlist = document.getElementById('modal-waitlist');
        if (!waitlist) return;

        const input = waitlist.querySelector('.modal__waitlist-input');
        const msg = waitlist.querySelector('.modal__waitlist-msg');
        const email = input ? input.value.trim() : '';

        if (!email || !email.includes('@')) {
            if (msg) { msg.textContent = 'Please enter a valid email.'; msg.style.color = '#ff6b6b'; }
            return;
        }

        btn.disabled = true;
        btn.textContent = 'SAVING...';

        submitWaitlist(email, waitlist.dataset.productId, waitlist.dataset.productName)
            .then(({ ok, msg: text }) => {
                if (msg) {
                    msg.textContent = text;
                    msg.style.color = ok ? '#7ee787' : '#ff6b6b';
                }
                if (ok) {
                    btn.textContent = 'JOINED';
                } else {
                    btn.disabled = false;
                    btn.textContent = 'JOIN WAITLIST';
                }
            });
    });

    // Init on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', hookModal);
    } else {
        hookModal();
    }
    // Also retry in case shop.js loads later
    setTimeout(hookModal, 500);
    setTimeout(hookModal, 1500);
})();
