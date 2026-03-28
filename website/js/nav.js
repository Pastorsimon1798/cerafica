// Navigation functionality
function initNav() {
    const nav = document.querySelector('.nav');
    const mobileToggle = document.querySelector('.nav__mobile-toggle');
    const mobileMenu = document.querySelector('.nav__mobile-menu');
    const cartBtns = document.querySelectorAll('.nav__cart-btn');
    const cartDrawer = document.querySelector('.cart-drawer');
    const cartOverlay = document.getElementById('cart-overlay');
    const cartCloseBtn = document.querySelector('.cart-drawer__close');
    const body = document.body;

    // Scroll behavior: add/remove "scrolled" class
    function handleScroll() {
        if (window.scrollY > 50) {
            nav.classList.add('scrolled');
        } else {
            nav.classList.remove('scrolled');
        }
    }

    window.addEventListener('scroll', debounce(handleScroll));
    handleScroll(); // Check on load

    // Mobile menu toggle
    if (mobileToggle) {
        mobileToggle.addEventListener('click', () => {
            const isActive = mobileMenu.classList.toggle('active');
            mobileToggle.setAttribute('aria-expanded', isActive);

            if (isActive) {
                body.classList.add('no-scroll');
            } else {
                body.classList.remove('no-scroll');
            }
        });

        // Close mobile menu when clicking a nav link
        const mobileLinks = mobileMenu.querySelectorAll('.nav__mobile-menu a');
        mobileLinks.forEach(link => {
            link.addEventListener('click', () => {
                mobileMenu.classList.remove('active');
                mobileToggle.setAttribute('aria-expanded', 'false');
                body.classList.remove('no-scroll');
            });
        });
    }

    // Close mobile menu and cart on Escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            if (mobileMenu && mobileMenu.classList.contains('active')) {
                mobileMenu.classList.remove('active');
                if (mobileToggle) {
                    mobileToggle.setAttribute('aria-expanded', 'false');
                }
                body.classList.remove('no-scroll');
            }
            if (cartDrawer && cartDrawer.classList.contains('active')) {
                closeCart();
            }
        }
    });

    // Cart drawer functionality
    function openCart() {
        cartDrawer.classList.add('active');
        if (cartOverlay) cartOverlay.classList.add('active');
        body.classList.add('no-scroll');
    }

    function closeCart() {
        cartDrawer.classList.remove('active');
        if (cartOverlay) cartOverlay.classList.remove('active');
        body.classList.remove('no-scroll');
    }

    cartBtns.forEach(cartBtn => {
        if (cartBtn) {
            cartBtn.addEventListener('click', openCart);
        }
    });

    if (cartOverlay) {
        cartOverlay.addEventListener('click', closeCart);
    }

    if (cartCloseBtn) {
        cartCloseBtn.addEventListener('click', closeCart);
    }
}

// Update cart count badge (called from shop.js)
function updateCartCount(count) {
    const cartCount = document.querySelector('.nav__cart-count');
    if (cartCount) {
        if (count > 0) {
            cartCount.textContent = count;
            cartCount.style.display = 'flex';
        } else {
            cartCount.style.display = 'none';
        }
    }
}
