// Toast notification function
function showToast(message, type = 'success') {
    const toast = document.getElementById('toast');
    if (!toast) return;

    toast.textContent = `> ${message}`;
    toast.className = 'toast';
    if (type === 'error') {
        toast.classList.add('toast--error');
    }

    // Trigger reflow to enable transition
    void toast.offsetWidth;
    toast.classList.add('show');

    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

// Shop functionality
function initShop() {
    // Only run on shop page
    if (!document.querySelector('.shop__grid')) return;

    // Payment links and product data will be loaded from products.json
    let products = [];
    let STRIPE_LINKS = {};
    let COINBASE_LINKS = {};

    // Cart management — reads from BRAND config if available
    const CART_KEY = (window.BRAND && window.BRAND.cartKey) || 'cerafica_cart';

    function getCart() {
        try {
            const cartJson = localStorage.getItem(CART_KEY);
            return cartJson ? JSON.parse(cartJson) : [];
        } catch (e) {
            console.error('Cart corrupted, resetting:', e);
            localStorage.removeItem(CART_KEY);
            return [];
        }
    }

    function saveCart(cart) {
        try {
            localStorage.setItem(CART_KEY, JSON.stringify(cart));
            updateCartUI();
        } catch (e) {
            console.error('Failed to save cart:', e);
            // Show user-friendly error if cart UI exists
            const cartCount = document.querySelector('.nav__cart-count');
            if (cartCount) {
                cartCount.textContent = '!';
                cartCount.style.color = 'red';
            }
        }
    }

    function addToCart(productId) {
        const product = products.find(p => p.id === productId);
        if (!product) return;

        const cart = getCart();
        const existingItem = cart.find(item => item.id === productId);

        if (existingItem) {
            const limitOne = window.BRAND && window.BRAND.product && window.BRAND.product.limitOneOfOne;
            if (!(limitOne && product.one_of_one)) {
                existingItem.quantity += 1;
            }
        } else {
            cart.push({
                id: product.id,
                name: product.name,
                price: product.price,
                quantity: 1
            });
        }

        saveCart(cart);
    }

    function removeFromCart(productId) {
        let cart = getCart();
        cart = cart.filter(item => item.id !== productId);
        saveCart(cart);
    }

    function updateQuantity(productId, newQuantity) {
        const cart = getCart();
        const item = cart.find(i => i.id === productId);

        if (item) {
            if (newQuantity <= 0) {
                removeFromCart(productId);
                return;
            }
            item.quantity = newQuantity;
            saveCart(cart);
        }
    }

    function getCartTotal() {
        const cart = getCart();
        return cart.reduce((total, item) => total + (item.price * item.quantity), 0);
    }

    function updateCartUI() {
        const cart = getCart();
        const cartItems = document.getElementById('cart-items');
        const cartSubtotal = document.getElementById('cart-subtotal');

        // Update cart count badge
        const totalItems = cart.reduce((sum, item) => sum + item.quantity, 0);
        if (typeof updateCartCount === 'function') {
            updateCartCount(totalItems);
        }

        // Announce cart update to screen readers
        const cartAnnouncement = document.getElementById('cart-announcement');
        if (cartAnnouncement) {
            cartAnnouncement.textContent = totalItems === 1 ? '1 item in cart' : `${totalItems} items in cart`;
        }

        // Render cart items
        if (cartItems) {
            if (cart.length === 0) {
                cartItems.innerHTML = '<p class="cart-drawer__empty">Your cart is empty</p>';
            } else {
                cartItems.innerHTML = cart.map(item => {
                    const product = products.find(p => p.id === item.id);
                    const canChangeQuantity = product && !product.one_of_one;

                    return `
                        <div class="cart-drawer__item" data-product-id="${item.id}">
                            <img src="images/products/${product.image}" class="cart-drawer__item-image" alt="${product.name}">
                            <div class="cart-drawer__item-details">
                                <h4 class="cart-drawer__item-name">${item.name}</h4>
                                <p class="cart-drawer__item-price">${formatPrice(item.price)}</p>
                                ${product.one_of_one ? '<span class="badge badge--amber">Only 1 available</span>' : ''}
                            </div>
                            <div class="cart-drawer__item-controls">
                                ${canChangeQuantity ? `
                                    <div class="cart-drawer__quantity">
                                        <button class="cart-drawer__qty-btn" data-action="decrease">&minus;</button>
                                        <span class="cart-drawer__qty-value">${item.quantity}</span>
                                        <button class="cart-drawer__qty-btn" data-action="increase">+</button>
                                    </div>
                                ` : `
                                    <span class="cart-drawer__qty-fixed">One of one</span>
                                `}
                                <button class="cart-drawer__remove" data-product-id="${item.id}">&times;</button>
                            </div>
                        </div>
                    `;
                }).join('');

                // Add event listeners for quantity controls
                cartItems.querySelectorAll('.cart-drawer__qty-btn').forEach(btn => {
                    btn.addEventListener('click', (e) => {
                        const itemEl = e.target.closest('.cart-drawer__item');
                        const productId = itemEl.dataset.productId;
                        const cart = getCart();
                        const item = cart.find(i => i.id === productId);
                        const action = e.target.dataset.action;

                        if (item) {
                            if (action === 'increase') {
                                updateQuantity(productId, item.quantity + 1);
                            } else if (action === 'decrease') {
                                updateQuantity(productId, item.quantity - 1);
                            }
                        }
                    });
                });

                // Add event listeners for remove buttons
                cartItems.querySelectorAll('.cart-drawer__remove').forEach(btn => {
                    btn.addEventListener('click', (e) => {
                        const productId = e.target.dataset.productId;
                        removeFromCart(productId);
                    });
                });
            }
        }

        // Update subtotal
        if (cartSubtotal) {
            cartSubtotal.textContent = formatPrice(getCartTotal());
        }
    }

    // Color extraction from product descriptions and materials
    const COLOR_KEYWORDS = {
        blue: ['blue', 'cobalt', 'chun', 'ceruleix', 'lazur'],
        red: ['red', 'copper', 'iron-manganese', 'manganese', 'rust', 'ferruginous'],
        green: ['green', 'seafoam'],
        warm: ['amber', 'warm', 'sienna', 'bronze', 'gold'],
        neutral: ['grey', 'gray', 'slate', 'carbon', 'charcoal', 'anthracite', 'black', 'white'],
        metallic: ['metallic', 'copper', 'bronze', 'luster', 'chrome']
    };

    const COLOR_ORDER = ['blue', 'green', 'warm', 'red', 'metallic', 'neutral'];

    function getColorCategory(product) {
        const text = `${product.description} ${product.materials} ${product.name}`.toLowerCase();
        for (const color of COLOR_ORDER) {
            const keywords = COLOR_KEYWORDS[color];
            if (keywords.some(kw => text.includes(kw))) return color;
        }
        return 'neutral';
    }

    // Parse height in cm from dimensions_cm string
    function parseHeightCm(product) {
        const match = product.dimensions_cm.match(/H\s*([\d.]+)/);
        return match ? parseFloat(match[1]) : 0;
    }

    // Parse width in cm from dimensions_cm string
    function parseWidthCm(product) {
        const match = product.dimensions_cm.match(/W\s*([\d.]+)/);
        return match ? parseFloat(match[1]) : 0;
    }

    function getVolume(product) {
        return parseHeightCm(product) * parseWidthCm(product);
    }

    function sortProducts(products, sortBy) {
        const sorted = [...products];
        switch (sortBy) {
            case 'price-asc':
                sorted.sort((a, b) => a.price - b.price);
                break;
            case 'price-desc':
                sorted.sort((a, b) => b.price - a.price);
                break;
            case 'size-asc':
                sorted.sort((a, b) => getVolume(a) - getVolume(b));
                break;
            case 'size-desc':
                sorted.sort((a, b) => getVolume(b) - getVolume(a));
                break;
            case 'color':
                sorted.sort((a, b) => {
                    const catA = COLOR_ORDER.indexOf(getColorCategory(a));
                    const catB = COLOR_ORDER.indexOf(getColorCategory(b));
                    return catA - catB;
                });
                break;
            default:
                break;
        }
        return sorted;
    }

    // Render product cards from data
    function renderProducts(products) {
        const gridInner = document.querySelector('.shop__grid-inner');
        if (!gridInner) return;

        gridInner.innerHTML = products.map(product => {
            const videoHtml = product.has_video ? `
                <video class="shop__card-video" muted loop playsinline preload="none" poster="images/products/${product.image}">
                    <source src="${product.video_src}" type="video/mp4">
                </video>
                <span class="shop__card-play-icon"><svg viewBox="0 0 24 24"><polygon points="5,3 19,12 5,21"/></svg></span>
            ` : '';

            const badges = [];
            if (product.one_of_one) badges.push('<span class="badge badge--cyan">ONE OF ONE</span>');
            if (product.coming_soon) badges.push('<span class="badge badge--muted">COMING SOON</span>');

            const buttonText = product.coming_soon ? 'COMING SOON' : (product.available ? 'ADD TO CART' : 'SOLD');
            const buttonClass = product.available && !product.coming_soon ? 'btn--outline' : 'btn--ghost';
            const disabled = !product.available || product.coming_soon ? 'disabled' : '';
            const buyNowButton = (product.available && !product.coming_soon) ? `
                <button class="btn btn--solid btn--sm shop__card-buy-btn" data-id="${product.id}">BUY NOW</button>
            ` : `
                <button class="btn btn--ghost btn--sm shop__card-buy-btn" data-id="${product.id}" ${disabled}>${buttonText}</button>
            `;

            return `
                <div class="shop__card card fade-in" data-category="vessels ${product.one_of_one ? 'one-of-one' : ''}" data-id="${product.id}" data-name="${product.name}" data-price="${product.price}" ${product.has_video ? `data-video="${product.video_src}"` : ''}>
                    <div class="shop__card-image">
                        <img src="images/products/${product.image}" alt="${product.name} handmade ceramic vessel" width="600" height="750" loading="lazy" onerror="this.src='img/placeholder.svg'; this.alt='Image unavailable';">
                        ${videoHtml}
                        ${badges.join('')}
                    </div>
                    <p class="shop__card-description">${product.description.split(' — ')[0] || product.description.substring(0, 50)}</p>
                    <p class="shop__card-price">${formatPrice(product.price)}</p>
                    <div class="shop__card-actions">
                        <button class="btn ${buttonClass} btn--sm shop__card-btn" data-id="${product.id}" ${disabled}>${buttonText}</button>
                        ${buyNowButton}
                    </div>
                </div>
            `;
        }).join('');

        // Update product count
        const shopHeaderCount = document.querySelector('.shop-header__count');
        if (shopHeaderCount) {
            shopHeaderCount.textContent = `${products.length} pieces`;
        }
    }

    // Initialize shop functionality after products are loaded
    function initShopFunctionality() {
        const shopCards = document.querySelectorAll('.shop__card');
        const filterPills = document.querySelectorAll('.filter-pill');
        const shopHeaderCount = document.querySelector('.shop-header__count');
        const modal = document.getElementById('product-modal');

        // Initialize cart UI on page load
        updateCartUI();

        // Filtering functionality
        function updateFilterCount(category) {
            const visibleCards = Array.from(shopCards).filter(card => {
                if (category === 'all') return true;
                return card.dataset.category.includes(category);
            });

            const totalCards = shopCards.length;
            const visibleCount = visibleCards.length;

            if (shopHeaderCount) {
                if (category === 'all') {
                    shopHeaderCount.textContent = `${totalCards} pieces`;
                } else {
                    shopHeaderCount.textContent = `${visibleCount} of ${totalCards} pieces`;
                }
            }

            // Announce filter results to screen readers
            const filterAnnouncement = document.getElementById('filter-announcement');
            if (filterAnnouncement) {
                filterAnnouncement.textContent = `Showing ${visibleCount} of ${totalCards} pieces`;
            }
        }

        filterPills.forEach(pill => {
            pill.addEventListener('click', () => {
                // Remove active class from all pills
                filterPills.forEach(p => {
                    p.classList.remove('active');
                    p.setAttribute('aria-pressed', 'false');
                });
                // Add active class to clicked pill
                pill.classList.add('active');
                pill.setAttribute('aria-pressed', 'true');

                const category = pill.dataset.category;

                // Filter cards with fade animation
                shopCards.forEach(card => {
                    const matches = category === 'all' || card.dataset.category.includes(category);

                    if (matches) {
                        card.style.opacity = '0';
                        setTimeout(() => {
                            card.style.display = 'block';
                            setTimeout(() => {
                                card.style.opacity = '1';
                            }, 50);
                        }, 200);
                    } else {
                        card.style.opacity = '0';
                        setTimeout(() => {
                            card.style.display = 'none';
                        }, 200);
                    }
                });

                updateFilterCount(category);
            });
        });

        // Video hover-to-play on shop cards
        const isTouchDevice = 'ontouchstart' in window || navigator.maxTouchPoints > 0;

        shopCards.forEach(card => {
            const video = card.querySelector('.shop__card-video');
            const playIcon = card.querySelector('.shop__card-play-icon');
            if (!video) return;

            if (isTouchDevice) {
                // Mobile: tap play icon to toggle video, tap card to open modal
                if (playIcon) {
                    playIcon.style.pointerEvents = 'auto';
                    playIcon.addEventListener('click', (e) => {
                        e.stopPropagation();
                        if (card.classList.contains('video-active')) {
                            video.pause();
                            card.classList.remove('video-active');
                        } else {
                            // Pause all other videos first
                            document.querySelectorAll('.shop__card.video-active').forEach(c => {
                                c.querySelector('.shop__card-video')?.pause();
                                c.classList.remove('video-active');
                            });
                            video.play().catch(() => {});
                            card.classList.add('video-active');
                        }
                    });
                }
            } else {
                // Desktop: hover plays video
                card.addEventListener('mouseenter', () => {
                    video.play().catch(() => {});
                });
                card.addEventListener('mouseleave', () => {
                    video.pause();
                    video.currentTime = 0;
                });
            }
        });

        // Product modal functionality
        // Focus trap for accessibility - keeps keyboard navigation within modal
        let focusTrapHandler = null;

        function trapFocus(element) {
            const focusableElements = element.querySelectorAll(
                'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'
            );
            const firstFocusable = focusableElements[0];
            const lastFocusable = focusableElements[focusableElements.length - 1];

            focusTrapHandler = (e) => {
                if (e.key === 'Tab') {
                    if (e.shiftKey && document.activeElement === firstFocusable) {
                        e.preventDefault();
                        lastFocusable.focus();
                    } else if (!e.shiftKey && document.activeElement === lastFocusable) {
                        e.preventDefault();
                        firstFocusable.focus();
                    }
                }
            };

            element.addEventListener('keydown', focusTrapHandler);
        }

        function removeFocusTrap(element) {
            if (focusTrapHandler) {
                element.removeEventListener('keydown', focusTrapHandler);
                focusTrapHandler = null;
            }
        }

        // Store last focused element for focus return
        let lastFocusedElement = null;

        function openModal(productId) {
            const product = products.find(p => p.id === productId);
            if (!product || !modal) return;

            // Store last focused element for focus return
            lastFocusedElement = document.activeElement;

            // Populate modal with product data
            const modalTitle = document.getElementById('modal-title');
            const modalPrice = modal.querySelector('.modal__price');
            const modalDescription = modal.querySelector('.modal__description');
            const modalDimensions = document.getElementById('modal-dimensions');
            const modalMaterials = document.getElementById('modal-materials');
            const modalFoodSafe = document.getElementById('modal-food-safe');
            const modalCare = document.getElementById('modal-care');
            const modalAvailability = document.getElementById('modal-availability');
            const modalBadgeContainer = document.getElementById('modal-badge-container');
            const modalAddBtn = document.getElementById('modal-add-cart');
            const modalBuyNowBtn = document.getElementById('modal-buy-now');
            const modalCryptoBtn = document.getElementById('modal-pay-crypto');

            // Media: image + optional video
            const modalMediaImage = document.getElementById('modal-media-image');
            const modalMediaVideo = document.getElementById('modal-media-video');

            if (modalMediaImage) {
                // Use product data directly to avoid lazy-loading issues with card image
                if (product.image) {
                    modalMediaImage.style.backgroundImage = `url(images/products/${product.image})`;
                }
                modalMediaImage.style.display = '';
            }

            if (modalMediaVideo) {
                if (product.has_video && product.video_src) {
                    modalMediaVideo.src = product.video_src;
                    modalMediaVideo.classList.remove('modal__media-video-hidden');
                    modalMediaVideo.style.display = '';
                    // Video does not auto-play - user must click to play
                } else {
                    modalMediaVideo.pause();
                    modalMediaVideo.src = '';
                    modalMediaVideo.classList.add('modal__media-video-hidden');
                    modalMediaVideo.style.display = 'none';
                }
            }

            if (modalTitle) modalTitle.textContent = product.name;
            if (modalPrice) modalPrice.textContent = formatPrice(product.price);
            if (modalDescription) modalDescription.textContent = product.description;
            if (modalDimensions) modalDimensions.textContent = product.dimensions;
            if (modalMaterials) modalMaterials.textContent = product.materials;
            if (modalFoodSafe) modalFoodSafe.textContent = product.food_safe ? 'Yes' : 'No';
            if (modalCare) modalCare.textContent = product.care || '';
            if (modalAvailability) modalAvailability.textContent = product.coming_soon ? 'Coming Soon' : (product.available ? 'Available' : 'Sold');

            // Only show food safe row when relevant
            const foodSafeRow = document.getElementById('modal-food-safe-row');
            if (foodSafeRow) {
                foodSafeRow.style.display = product.food_safe ? '' : 'none';
            }

            if (modalBadgeContainer) {
                let badges = '';
                if (product.one_of_one) badges += '<span class="badge badge--cyan">ONE OF ONE</span>';
                if (product.coming_soon) badges += ' <span class="badge badge--muted">COMING SOON</span>';
                modalBadgeContainer.innerHTML = badges;
            }

            if (modalAddBtn) {
                modalAddBtn.dataset.id = product.id;
                if (!product.available || product.coming_soon) {
                    modalAddBtn.disabled = true;
                    modalAddBtn.textContent = product.coming_soon ? 'COMING SOON' : 'SOLD';
                    modalAddBtn.classList.add('btn--ghost');
                    modalAddBtn.classList.remove('btn--solid');
                } else {
                    modalAddBtn.disabled = false;
                    modalAddBtn.textContent = 'ADD TO CART';
                    modalAddBtn.classList.add('btn--solid');
                    modalAddBtn.classList.remove('btn--ghost');
                }
            }

            if (modalBuyNowBtn) {
                modalBuyNowBtn.dataset.id = product.id;
                modalBuyNowBtn.style.display = (product.available && !product.coming_soon) ? '' : 'none';
            }

            if (modalCryptoBtn) {
                modalCryptoBtn.dataset.id = product.id;
                modalCryptoBtn.style.display = (product.available && !product.coming_soon) ? '' : 'none';
            }

            modal.classList.add('active');
            document.body.classList.add('no-scroll');

            // Enable focus trap
            trapFocus(modal);
        }

        function closeModal() {
            if (!modal) return;
            modal.classList.remove('active');
            document.body.classList.remove('no-scroll');

            // Remove focus trap and restore focus
            removeFocusTrap(modal);
            if (lastFocusedElement) {
                lastFocusedElement.focus();
                lastFocusedElement = null;
            }

            // Pause modal video
            const modalMediaVideo = document.getElementById('modal-media-video');
            if (modalMediaVideo) {
                modalMediaVideo.pause();
                modalMediaVideo.src = '';
            }
        }

        // Open modal when clicking on a card (not the buttons)
        shopCards.forEach(card => {
            card.addEventListener('click', (e) => {
                // Don't open modal if clicking a button
                if (e.target.classList.contains('shop__card-btn') || e.target.classList.contains('shop__card-buy-btn')) {
                    return;
                }
                const productId = card.dataset.id;
                openModal(productId);
            });
        });

        // Close modal events
        const modalClose = modal ? modal.querySelector('.modal__close') : null;

        if (modalClose) {
            modalClose.addEventListener('click', closeModal);
        }

        if (modal) {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    closeModal();
                }
            });
        }

        // Escape key closes modal
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && modal.classList.contains('active')) {
                closeModal();
            }
        });

        // Add to cart from modal
        const modalAddBtn = document.getElementById('modal-add-cart');
        if (modalAddBtn) {
            modalAddBtn.addEventListener('click', () => {
                const productId = modalAddBtn.dataset.id;
                addToCart(productId);
                showToast('Added to cart!');
                // Don't close modal - let user continue shopping
            });
        }

        // BUY NOW from modal — redirects to Stripe Payment Link
        const modalBuyNowBtn = document.getElementById('modal-buy-now');
        if (modalBuyNowBtn) {
            modalBuyNowBtn.addEventListener('click', () => {
                const productId = modalBuyNowBtn.dataset.id;
                const stripeUrl = STRIPE_LINKS[productId];
                if (stripeUrl && stripeUrl.length > 0) {
                    window.open(stripeUrl, '_blank');
                } else {
                    showToast('This item is temporarily unavailable for checkout. Please email simon@cerafica.com to purchase.', 'error');
                }
            });
        }

        // PAY WITH CRYPTO from modal — redirects to Coinbase Commerce
        const modalCryptoBtn = document.getElementById('modal-pay-crypto');
        if (modalCryptoBtn) {
            modalCryptoBtn.addEventListener('click', () => {
                const productId = modalCryptoBtn.dataset.id;
                const coinbaseUrl = COINBASE_LINKS[productId];
                if (coinbaseUrl && !coinbaseUrl.includes('YOUR_COINBASE_LINK')) {
                    window.open(coinbaseUrl, '_blank');
                } else {
                    alert('Crypto payment link not configured yet for this product.');
                }
            });
        }

        // Add to cart from shop card
        const cardAddBtns = document.querySelectorAll('.shop__card-btn');
        cardAddBtns.forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const productId = btn.dataset.id;
                addToCart(productId);
                showToast('Added to cart!');
            });
        });

        // BUY NOW from shop card — redirects to Stripe Payment Link
        const cardBuyNowBtns = document.querySelectorAll('.shop__card-buy-btn');
        cardBuyNowBtns.forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const productId = btn.dataset.id;
                const product = products.find(p => p.id === productId);
                if (product && product.coming_soon) return;
                const stripeUrl = STRIPE_LINKS[productId];
                if (stripeUrl && stripeUrl.length > 0) {
                    window.open(stripeUrl, '_blank');
                } else {
                    showToast('This item is temporarily unavailable for checkout. Please email simon@cerafica.com to purchase.', 'error');
                }
            });
        });

        // Checkout button — multi-item checkout via Stripe
        const checkoutBtn = document.getElementById('checkout-btn');
        
        // Get Netlify function URL from config (auto-set during deployment)
        const CHECKOUT_FUNCTION_URL = (typeof CHECKOUT_CONFIG !== 'undefined') 
            ? CHECKOUT_CONFIG.getFunctionUrl()
            : (window.location.hostname === 'localhost' 
                ? 'http://localhost:8888/.netlify/functions/create-checkout'
                : 'https://cerafica-checkout.netlify.app/.netlify/functions/create-checkout');
        
        if (checkoutBtn) {
            checkoutBtn.addEventListener('click', async () => {
                const cart = getCart();
                if (cart.length === 0) return;

                // Show loading state
                const originalText = checkoutBtn.textContent;
                checkoutBtn.textContent = 'PROCESSING...';
                checkoutBtn.disabled = true;

                try {
                    // Single item: direct to Stripe Payment Link (faster, no function call)
                    if (cart.length === 1) {
                        const stripeUrl = STRIPE_LINKS[cart[0].id];
                        if (stripeUrl && stripeUrl.length > 0) {
                            window.open(stripeUrl, '_blank');
                            checkoutBtn.textContent = originalText;
                            checkoutBtn.disabled = false;
                            return;
                        }
                    }

                    // Multi-item: Call Netlify function to create Stripe Checkout Session
                    const response = await fetch(CHECKOUT_FUNCTION_URL, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({ items: cart }),
                    });

                    const data = await response.json();

                    if (!response.ok) {
                        throw new Error(data.error || 'Failed to create checkout');
                    }

                    if (data.url) {
                        // Redirect to Stripe Checkout
                        window.location.href = data.url;
                    } else {
                        throw new Error('No checkout URL received');
                    }

                } catch (error) {
                    console.error('Checkout error:', error);
                    
                    // Show specific error message to user
                    let errorMsg = 'Checkout failed. Please try again.';
                    if (error.message?.includes('Failed to fetch') || error.message?.includes('NetworkError')) {
                        errorMsg = 'Network error. Check connection and try again.';
                    } else if (error.message?.includes('CORS')) {
                        errorMsg = 'Configuration error. Please contact support.';
                    } else if (error.message) {
                        errorMsg = `Checkout error: ${error.message}`;
                    }
                    
                    showToast(errorMsg, 'error');
                    
                    // Only fallback to email after user sees error
                    setTimeout(() => {
                        const goToEmail = confirm('Checkout is not working. Would you like to send an email order instead?');
                        if (goToEmail) {
                            const total = getCartTotal();
                            const itemList = cart.map(item => {
                                const product = products.find(p => p.id === item.id);
                                return `${item.quantity}x ${product.name} — ${formatPrice(product.price)}`;
                            }).join('\n');

                            const emailBody = encodeURIComponent(
                                `Hi Simon,\n\nI'd like to purchase:\n\n${itemList}\n\nTotal: ${formatPrice(total)}\n\nShipping to: [Please enter your shipping address]\n\nPlease send payment link.`
                            );
                            window.location.href = `mailto:simon@cerafica.com?subject=Order Request&body=${emailBody}`;
                        }
                    }, 2000);
                    
                } finally {
                    // Reset button state (if still on page)
                    checkoutBtn.textContent = originalText;
                    checkoutBtn.disabled = false;
                }
            });
        }
    }

    // Load products from JSON
    fetch('data/products.json')
        .then(response => response.json())
        .then(data => {
            products = data.map(p => ({
                ...p,
                dimensions: p.dimensions_in // Use inches for display
            }));

            // Build Stripe links from product data
            STRIPE_LINKS = {};
            COINBASE_LINKS = {};
            products.forEach(p => {
                STRIPE_LINKS[p.id] = p.stripe_payment_link || '';
                COINBASE_LINKS[p.id] = `https://commerce.coinbase.com/checkout/YOUR_COINBASE_LINK_${p.id}`;
            });

            // Filter to available products only
            const availableProducts = products.filter(p => p.available && !p.coming_soon);

            // Sort and render
            let currentSort = 'default';
            let displayedProducts = sortProducts(availableProducts, currentSort);
            renderProducts(displayedProducts);
            initShopFunctionality();

            // Sort control
            const sortSelect = document.getElementById('sort-select');
            if (sortSelect) {
                sortSelect.addEventListener('change', () => {
                    currentSort = sortSelect.value;
                    displayedProducts = sortProducts(availableProducts, currentSort);
                    renderProducts(displayedProducts);
                    initShopFunctionality();
                });
            }
            // Initialize fade-in animations after products are rendered
            if (typeof initAnimations === 'function') {
                initAnimations();
            }
        })
        .catch(error => {
            console.error('Failed to load products:', error);
            const shopHeaderCount = document.querySelector('.shop-header__count');
            if (shopHeaderCount) {
                shopHeaderCount.textContent = 'Error loading products';
            }
        });
}
