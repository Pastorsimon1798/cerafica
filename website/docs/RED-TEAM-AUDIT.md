# Cerafica Website — Red Team Audit Report

**Date**: 2026-03-26
**Scope**: cerafica.com — all 5 HTML pages, CSS, JS, images, SEO, security, accessibility, performance, copywriting, design
**Auditor**: Claude Code (7 parallel audit agents)

---

## Executive Summary

**Overall Assessment: Good foundation, significant performance and SEO gaps**

The site has a strong design identity (dark terminal aesthetic), solid accessibility foundations (skip links, ARIA, reduced-motion support), and proper structured data. However, there are critical performance issues (106MB of images deployed), SEO gaps (canonical URLs with `.html` extensions, no `index.html` → `/` redirect), a potential XSS vulnerability in the checkout page, and missing web design guideline compliance in several areas.

### Top 5 Priority Fixes

| # | Issue | Impact | Effort |
|---|-------|--------|--------|
| 1 | **106MB of unoptimized images deployed** — includes 65MB of backup videos | CRITICAL | Low |
| 2 | **XSS in checkout.html** — `renderError()` injects URL params into innerHTML | HIGH | Low |
| 3 | **Canonical URLs use `.html` extensions** — `cerafica.com/index.html` instead of `cerafica.com/` | HIGH | Low |
| 4 | **No modern image formats** — all JPEG, no WebP/AVIF, no srcset, no responsive images | HIGH | Medium |
| 5 | **Debug screenshots in repo root** — `shop-screenshot.png` (4MB), `video-debug.png` (540KB), `live-video-check.png` (469KB) | MEDIUM | Low |

---

## 1. SEO AUDIT

### Critical

| # | Issue | Location | Fix |
|---|-------|----------|-----|
| S1 | **Canonical URLs include `.html`** — Google may treat `cerafica.com/` and `cerafica.com/index.html` as different pages. All canonicals point to `*.html` variants | All pages `<link rel="canonical">` | Change canonicals to clean URLs: `https://cerafica.com/`, `https://cerafica.com/shop`, etc. Add redirects from `.html` to clean URLs via `_redirects` or server config |
| S2 | **Sitemap uses `.html` extensions** — same issue as S1 | [sitemap.xml](sitemap.xml:4-26) | Update all URLs in sitemap to clean paths without `.html` |
| S3 | **og:url uses `.html` extensions** — social sharing will use ugly URLs | [index.html:12](index.html#L12), [shop.html:12](shop.html#L12), [about.html:12](about.html#L12), [links.html:12](links.html#L12) | Update to clean URLs |
| S4 | **Homepage CTA hardcodes piece count** — `(11 pieces)` in hero will go stale | [index.html:164](index.html#L164) | Dynamically count from products.json, or remove the count |
| S5 | **Links page has NO H1 tag** — jumps from title meta directly to content with no heading hierarchy | [links.html](links.html) | Add `<h1>Cerafica — Quick Links</h1>` in the header section |
| S6 | **Product schema uses PreOrder incorrectly** — unavailable items with `available: false` and `coming_soon: true` show "PreOrder" but should be "OutOfStock" | [shop.html](shop.html) Product JSON-LD | Change availability to `https://schema.org/OutOfStock` for unavailable items |
| S7 | **No individual product pages** — all products on one page, no unique URLs for each piece to rank for their own keywords | [shop.html](shop.html) | Create individual product pages: `/products/pallth-7/` etc. |
| S8 | **Checkout page missing meta description and OG tags** | [checkout.html](stripe/checkout.html) | Add meta description and Open Graph tags |

### High

| # | Issue | Location | Fix |
|---|-------|----------|-----|
| S9 | **Title tag "CLAY / CODE / SEEK / FEEL" on homepage isn't in title** — hero tagline differs from `<title>`, no primary keyword in title | [index.html:23](index.html#L23) | Title: "Handmade Ceramics — Cerafica \| Long Beach, CA" or similar keyword-forward title |
| S10 | **Shop page title "Shop — Cerafica" is generic** — no keywords for what's being sold | [shop.html:23](shop.html#L23) | Title: "Handmade Ceramic Vessels — Shop Cerafica \| Long Beach, CA" |
| S11 | **LocalBusiness priceRange "$85 - $105" is wrong** — actual products range $55-$105 | [index.html:86](index.html#L86) | Update to "$55 - $105" |
| S12 | **links.html shouldn't be in sitemap** — it's a utility/linktree page, not content Google should index | [sitemap.xml:22](sitemap.xml#L22) | Either remove from sitemap or add `<meta name="robots" content="noindex">` |
| S13 | **All og:image values identical** — every page uses same pallth-7.jpg | All pages | Use page-specific images (about page → studio photo, shop → hero product, etc.) |
| S14 | **Sitemap lastmod dates are stale** — shows 2026-03-20 | [sitemap.xml](sitemap.xml) | Update to current date |
| S15 | **Homepage H1 is just brand name** — no keywords for search engines to understand what the page is about | [index.html:161](index.html#L161) | Consider `<h1>Cerafica — Handmade Ceramics, Long Beach CA</h1>` (keep CERAFICA as primary text, add keywords in subtitle) |
| S16 | **No local SEO keywords in headings** — "Long Beach CA" only in descriptions, not H1s | All pages | Add location keywords to page headings |

### Medium

| # | Issue | Location | Fix |
|---|-------|----------|-----|
| S17 | **No `<article>` semantic element** — product cards are `<a>` inside `<div>` | [index.html:181-234](index.html#L181-L234), shop.html | Wrap product cards in `<article>` |
| S18 | **Internal links use `.html` extensions** — creates ugly URLs when shared | All nav links across all pages | Use clean URLs throughout |
| S19 | **No `<link rel="alternate" hreflang="x-default">`** — minor but helpful for international | All pages `<head>` | Add hreflang tag |
| S20 | **No blog/journal section** — no content marketing, no long-tail keyword opportunity | N/A | Consider adding `/journal/` with process posts, techniques, glaze recipes |

### Low

| # | Issue | Location | Fix |
|---|-------|----------|-----|
| S21 | **`changefreq` in sitemap is deprecated** by search engines | [sitemap.xml](sitemap.xml) | Remove changefreq, keep lastmod |
| S22 | **`priority` values in sitemap are mostly ignored** by Google | [sitemap.xml](sitemap.xml) | Optional: remove priorities |

### SEO Scores (per-agent audit)

| Category | Score |
|----------|-------|
| Title Tags | 7/10 |
| Meta Descriptions | 9/10 |
| Heading Structure | 5/10 |
| Canonical Tags | 10/10 |
| Open Graph | 9/10 |
| Structured Data | 10/10 |
| Sitemap | 9/10 |
| Robots.txt | 10/10 |
| URL Structure | 6/10 |
| Image SEO | 4/10 |
| Internal Linking | 8/10 |
| Keyword Targeting | 5/10 |
| Content Quality | 10/10 |
| Mobile SEO | 10/10 |
| Technical SEO | 10/10 |
| **Overall SEO** | **72/100** |

---

## 2. SECURITY AUDIT

### Critical

| # | Issue | Location | Fix |
|---|-------|----------|-----|
| X1 | **XSS via innerHTML in checkout.html `renderError()`** — injects `message` param from URL directly into DOM: `${message \|\| '...'}`. Attacker could craft URL like `checkout.html?message=<img src=x onerror=alert(1)>` | [checkout.html:166](stripe/checkout.html#L166) | Use `textContent` instead of `innerHTML`, or sanitize with DOMPurify. Or just use a fixed error message (the `message` parameter is never actually set by your code) |

### High

| # | Issue | Location | Fix |
|---|-------|----------|-----|
| X2 | **No Subresource Integrity (SRI) on external scripts** — Google Analytics loaded without integrity hash | [index.html:97](index.html#L97), all pages | Add `integrity` and `crossorigin` attributes to gtag script |
| X3 | **No Content Security Policy** — no CSP meta tag or headers | All pages | Add `<meta http-equiv="Content-Security-Policy" ...>` or configure via `_headers` file |
| X4 | **Stripe checkout function URL exposed** in client-side JS — `cerafica-checkout.netlify.app/.netlify/functions/create-checkout` is visible | [checkout-config.js:12](js/checkout-config.js#L12) | Move to server-side or environment variable. Function URL exposure isn't catastrophic (it's a Stripe checkout, not a direct charge) but it's not best practice |
| X5 | **Cart price stored client-side** — prices in localStorage could be manipulated before checkout | [shop.js](js/shop.js) (cart management) | Verify prices server-side in the Netlify function (check products.json server-side, not trust client price) |

### Medium

| # | Issue | Location | Fix |
|---|-------|----------|-----|
| X6 | **No HTTPS enforcement visible** — no `<meta>` upgrade-insecure or HSTS header | All pages | GitHub Pages forces HTTPS, but add `Strict-Transport-Security` via `_headers` |
| X7 | **GA4 tracking present without cookie consent** — may violate GDPR/privacy laws | [index.html:97-103](index.html#L97-L103), all pages | Add cookie consent banner or use consent-mode v2 |

### Low

| # | Issue | Location | Fix |
|---|-------|----------|-----|
| X8 | **Email address exposed in checkout HTML** — `simon@cerafica.com` visible in source | [checkout.html:141](stripe/checkout.html#L141) | Low risk, but could use a contact form instead |

---

## 3. PERFORMANCE AUDIT

### Critical

| # | Issue | Location | Impact | Fix |
|---|-------|----------|--------|-----|
| P1 | **106MB of images in repo** — 22 product images (40MB) + 6 backup videos (65MB) | [images/](images/) | LCP, load time, deploy time | Remove `products-backup/` (65MB of .mp4 files not used by the site). Optimize product images. Add `images/products-backup/` to `.gitignore` |
| P2 | **Largest product image is 3MB** — ignix-5.jpg, pyr-os-8.jpg, nex-un-3.jpg all 2.7-3MB each | [images/products/](images/products/) | LCP, load time | Run through image optimizer (Squoosh, ImageMagick). Target 100-200KB per image with WebP |
| P3 | **No lazy loading on process images** — 4 process images load eagerly | [index.html:249-267](index.html#L249-L267) | LCP | Add `loading="lazy"` to all 4 process `<img>` tags |
| P4 | **All images are JPEG** — no WebP/AVIF format | All images | Load time, bandwidth | Convert to WebP with JPEG fallback using `<picture>` elements |
| P5 | **No srcset/sizes for responsive images** — same 600px wide image served to all devices | All `<img>` tags | Mobile bandwidth | Add `srcset` with multiple sizes and `sizes` attribute |

### High

| # | Issue | Location | Impact | Fix |
|---|-------|----------|--------|-----|
| P6 | **5 render-blocking CSS files** — variables.css, base.css, components.css, animations.css, + page CSS all in `<head>` | All pages | FCP, LCP | Critical CSS inline, rest loaded async. Or combine into single file |
| P7 | **4 render-blocking JS files** — no `defer` attribute on main.js, nav.js, animations.js, checkout-config.js, shop.js | [index.html:304-308](index.html#L304-L308) | FCP | Add `defer` to all script tags |
| P8 | **Font display swap not specified** — Google Fonts URL lacks `&display=swap` | All pages | FOIT/CLS | Add `&display=swap` to Google Fonts URL parameter |
| P9 | **shop.js is 32KB** — large monolithic JS file for shopping cart functionality | [js/shop.js](js/shop.js) (32KB) | Parse time, bandwidth | Consider code splitting or minification |

### Medium

| # | Issue | Location | Impact | Fix |
|---|-------|----------|--------|-----|
| P10 | **Debug screenshots in repo root** — shop-screenshot.png (4MB), video-debug.png (540KB), live-video-check.png (469KB) | [website/](website/) root | Repo size, deploy time | Delete or move to docs/ and gitignore |
| P11 | **No preconnect for fonts.gstatic.com crossorigin** — actually this IS present | — | — | Already handled (preconnect present on all pages) |
| P12 | **No cache-busting on assets** — CSS/JS files have no versioning hash | All `<link>` and `<script>` tags | Cache staleness | Add `?v=hash` or rename files with content hash |

### Low

| # | Issue | Location | Impact | Fix |
|---|-------|----------|--------|-----|
| P13 | **favicon.svg is only 325 bytes** — fine, no issue | — | — | Good, no action needed |
| P14 | **No service worker** — no offline/pwa capability | — | Offline UX | Consider adding service worker for repeat visitors |

---

## 4. ACCESSIBILITY AUDIT (WCAG 2.1 AA)

### Critical

| # | Issue | WCAG | Location | Fix |
|---|-------|------|----------|-----|
| A1 | **No H1 on checkout.html** — starts with H1 but the initial state (loading) renders before content, and the loading H1 "PROCESSING..." replaces real content | [checkout.html:105](stripe/checkout.html#L105) | 1.3.1 | Ensure exactly one H1 in final rendered state per page. Checkout has one, but it's dynamically set — acceptable for SPAs |
| A2 | **Cart item names injected via innerHTML without escaping** — `${item.name}` in cart drawer | [shop.js:138](js/shop.js#L138) | 4.1.2 | Sanitize with `textContent` or escape function |

### High

| # | Issue | WCAG | Location | Fix |
|---|-------|------|----------|-----|
| A3 | **Product card h3 tags are links (a > h3)** — heading inside link is valid but `a` wraps `h3` which is semantically odd | [index.html:181-234](index.html#L181-L234) | 1.3.1 | Consider `<article><a><h3>` or `<a aria-label="..."><h3>` — current structure is technically valid but could be clearer |
| A4 | **Mobile menu toggle has 3 empty spans** — hamburger icon uses empty `<span>` elements, no text alternative | [index.html:136-139](index.html#L136-L139) | 1.1.1 | Add `aria-hidden="true"` to spans (already has aria-label on button — this is acceptable) |
| A5 | **No `<header>` landmark** — nav is not wrapped in `<header>` | [index.html:108](index.html#L108) | 1.3.1 | Wrap `<nav>` in `<header>` |
| A6 | **No `<footer>` landmark** — footer uses `<footer>` tag (good) | [index.html:280](index.html#L280) | — | Already correct |

### Medium

| # | Issue | WCAG | Location | Fix |
|---|-------|------|----------|-----|
| A7 | **Scan line overlay at z-index 9999** — `body::before` pseudo-element for scan lines sits above all content | [base.css:176-189](css/base.css#L176-L189) | 1.4.11 | Ensure pointer-events:none is set (it is). But consider if it affects screen magnifier users. Already handled by reduced-motion media query |
| A8 | **Skip link exists and is functional** — good | [index.html:106](index.html#L106) | 2.4.1 | No fix needed — well implemented with `visually-hidden` class |
| A9 | **No `<main>` landmark on links.html** — uses `<main>` correctly | [links.html:67](links.html#L67) | — | Already correct |
| A10 | **Reduced motion support is excellent** — comprehensive `@media (prefers-reduced-motion: reduce)` with JS check | [animations.css:189-237](css/animations.css#L189-L237), [animations.js:4](js/animations.js#L4) | 2.3.3 | No fix needed — exemplary |

### Good Accessibility Practices Found

- Skip-to-content link present
- `aria-live` region for cart announcements
- `aria-label` on nav, mobile toggle, cart button, Instagram link
- `aria-expanded` on mobile toggle
- `role="navigation"` on nav elements
- `:focus-visible` styling on all interactive elements
- `prefers-reduced-motion` fully supported (CSS + JS)
- `visually-hidden` class properly implemented
- `lang="en"` on all pages
- Good alt text on product images (specific, descriptive)

---

## 5. FRONTEND DESIGN AUDIT

> **Design Audit Note:** The terminal/sci-fi aesthetic is a deliberate, core brand choice. Cerafica's identity is code + clay, computation + craft. JetBrains Mono, HUD decorations, scan lines, and "SYS:ONLINE" footer are the personality. Every recommendation below enhances the existing aesthetic within that framework.

### High Impact

| # | Issue | Location | Fix |
|---|-------|----------|-----|
| D1 | **Sections below the hero are visually flat** — hero has grid lines, corner brackets, and a radial gradient vignette, but every other section is just `#0A0A0A` with a 1px border separator. The contrast between the rich hero and the flat content sections is jarring | [homepage.css:105-110](css/homepage.css#L105-L110), [homepage.css:122-124](css/homepage.css#L122-L124) | Add subtle background variation to alternate sections: a faint radial gradient using `--nebula-purple` or `--nebula-teal` on the featured section, a slightly lighter `--bg-card` tint on the philosophy strip. Not full hero treatment — just enough depth so the page doesn't feel like it goes from cinematic to spreadsheet |
| D2 | **Featured cards hover state is underwhelming** — on hover: `translateY(-2px)`, border brightens, subtle cyan shadow. That's it. The card has HUD corner brackets that barely change opacity (0.3 → 0.6). For the main product showcase, this needs more terminal personality | [components.css:281-327](css/components.css#L281-L327) | On hover: add a cyan border glow (`box-shadow: 0 0 15px rgba(30, 195, 210, 0.2)`), animate the HUD corners to extend (increase box-shadow spread), and add a subtle image scale (`transform: scale(1.03)` on the image, not the card). The current lift is fine but needs to feel more like "activating a system" than "raising a card" |
| D3 | **Process section doesn't match the terminal aesthetic** — horizontal scroll with stock photos in basic cards. No HUD elements, no data readouts, no sense that this is a "pipeline." It's the most generic-looking section on the site | [index.html:248-271](index.html#L248-L271), [homepage.css:209-252](css/homepage.css#L209-L252) | Add HUD-style treatment: corner brackets on each process card, a subtle grid background on the section, small "STEP 01/04" labels in `--fg-muted` above each heading, and a thin horizontal progress line connecting the cards. The temperature data (2,350°F, cone 10) is great — make it look like a terminal readout with a monospace data label |
| D4 | **No loading skeleton for product grid** — the `.shimmer` class and keyframes exist in animations.css but the shop page just shows a spinning circle. The spinner breaks the terminal aesthetic (circles aren't very "HUD") | [shop.html:309-312](shop.html#L309-L312), [animations.css:117-136](css/animations.css#L117-L136) | Replace the spinner with a grid of shimmer skeleton cards that match the product card layout. Use the existing `.shimmer` class on placeholder divs with the same aspect-ratio as real cards. This looks more intentional and matches the aesthetic |

### Medium Impact

| # | Issue | Location | Fix |
|---|-------|----------|-----|
| D5 | **Philosophy strip is visually weak** — a centered paragraph between two 1px borders. It's the only text on the homepage that communicates brand philosophy and it has no presence. Gets lost between the hero and the product grid | [index.html:168-170](index.html#L168-L170), [homepage.css:105-119](css/homepage.css#L105-L119) | Give it a background treatment: either a subtle `--bg-card` fill, a faint radial gradient (like a "spotlight" on the text), or HUD-style bracket decorations. Also consider a slight left-border accent in cyan (3px solid) to draw the eye — fits the terminal aesthetic like a status readout |
| D6 | **Footer mailing list is a bare Google Forms link** — styled as an outline button that opens a new tab. Breaks the flow, feels like a placeholder. The terminal aesthetic deserves a proper inline terminal input | [index.html:293](index.html#L293) | Style it as a terminal input: a text input with a blinking cursor effect and `>` prompt prefix, or at minimum an inline email input + submit button within the footer (even if it still posts to a backend). The CSS for `.footer__email-input` already exists but isn't used in the HTML |
| D7 | **Amber accent color is defined but unused** — `--amber: #FFAA00` is in variables.css but nowhere on the actual site. It's a perfect secondary accent for drawing attention to key elements (sold badges, limited availability, CTAs) without overusing cyan | [variables.css:17](css/variables.css#L17) | Use amber for: sold/unavailable badges (already `badge--sold` uses red, but amber = "warning/caution" fits better for "last one available"), the piece count in the hero CTA, or a subtle amber accent on the hero divider line |
| D8 | **Shop header lacks HUD personality** — just "THE SHOP" label + "AVAILABLE WORK" H1 + piece count. Compared to the hero section's grid treatment, this feels like a plain HTML page | [shop.html:283-289](shop.html#L283-L289), [shop.css:6-17](css/shop.css#L6-L17) | Add a subtle grid or scan-line background to the shop header area, or a thin cyan horizontal rule under the header. The piece count ("Loading pieces...") could use a terminal-style prefix like `> COUNT: 11 pieces` or just style it with a blinking cursor |
| D9 | **Product modal detail grid could be more immersive** — the modal shows image, title, price, description, and a 2-column detail grid. Functional but doesn't feel like a "system scan" of the piece, which would fit the aesthetic | [shop.html:361-403](shop.html#L361-403), [shop.css:255-299](css/shop.css#L255-299) | Add a subtle top border accent in cyan, consider giving the detail labels a slightly different treatment (maybe a faint background on each detail row, alternating like a terminal table). The modal could also have HUD corner brackets like the cards |
| D10 | **No image hover zoom on featured cards** — the shop cards have video-on-hover (great), but the homepage featured cards have zero image interaction. Hovering does nothing to the image itself | [homepage.css:138-151](css/homepage.css#L138-L151) | Add `transform: scale(1.05)` on `.featured__card-image img` with a smooth transition on `.featured__card:hover`. The container already has `overflow: hidden` so it'll clip cleanly |
| D11 | **About page hero is too similar to a plain heading** — just centered text with a faint radial gradient. Lacks the HUD personality that makes the homepage hero memorable | [about.html:177-182](about.html#L177-L182), [about.css:6-24](css/about.css#L6-L24) | Add the same HUD corner brackets treatment from the homepage hero (or a lighter version — just top-left and bottom-right corners). Consider a subtle animated element: a blinking cursor after the subtitle, or a thin horizontal line that "draws" itself across the page |
| D12 | **Card content has no internal padding on featured cards** — the image sits directly against the card background with no content area. The card structure has `.featured__card-image` (the image container) but no `.featured__card-content` wrapper in the HTML — the h3, description, and price are just loose children of the `<a>` tag | [index.html:181-234](index.html#L181-L234), [homepage.css:153-175](css/homepage.css#L153-175) | The CSS defines `.featured__card-content` with `padding: var(--space-md)` but the HTML doesn't use it. Either wrap the text elements in a `<div class="featured__card-content">` or add padding directly to `.featured__card h3`, `.featured__card .card__description`, `.featured__card .card__price`. Currently the text has no breathing room from the card edges |

### Low Impact

| # | Issue | Location | Fix |
|---|-------|----------|-----|
| D13 | **Nav scrolled state could be more distinct** — on scroll, nav gets a solid background + box-shadow. But the transition from transparent to solid can feel abrupt when scrolling fast. A backdrop-blur would feel more "glass HUD" | [components.css:33-36](css/components.css#L33-L36) | Add `backdrop-filter: blur(12px)` and `background-color: rgba(10, 10, 10, 0.85)` to `.nav.scrolled` for a frosted glass effect. More terminal/sci-fi than a flat solid background |
| D14 | **FAQ accordion markers are plain text** — `+` and `-` characters before questions. Functional but could be more styled | [about.css:194-201](css/about.css#L194-L201) | Replace with a small cyan bracket/indicator, or animate the rotation of a chevron. The `+`/`-` works fine for terminal aesthetic though — consider keeping it but adding a cyan color |
| D15 | **Contact section on about page is plain** — just "GET IN TOUCH" heading + email/instagram links. Could use a subtle terminal-style treatment | [about.html:290-299](about.html#L290-299) | Consider framing it as a terminal prompt: `> CONTACT:` label above the links, or a subtle dashed border container that looks like a terminal output block |
| D16 | **Filter pills lack keyboard/active feedback** — hover and active states change color, but there's no pressed/active visual state for touch devices | [components.css:465-485](css/components.css#L465-L485) | Add `transform: scale(0.97)` on `.filter-pill:active` for tactile feedback. Small detail but makes the filter feel more responsive |
| D17 | **Toast notification could be more "terminal"** — currently a solid cyan bar. Works, but a terminal-style notification would be more on-brand | [components.css:397-420](css/components.css#L397-L420) | Consider adding a small prefix like `>` or `SYS:` before the toast text, or giving it a subtle border instead of solid fill. Maybe a left-border accent style instead of full background |

### What's Already Done Right

- **Hero HUD treatment** — grid lines, corner brackets, radial vignette. Best section on the site
- **Card HUD corner brackets** — `box-shadow` approach that survives `overflow: hidden`. Smart
- **Status dot pulse** — the cyan dot next to CERAFICA in the nav. Small but sells the "system online" feel
- **Typewriter effect** — well-timed, uses IntersectionObserver, respects reduced-motion
- **Scan line overlay** — `body::before` with repeating gradient. Subtle enough to not interfere, visible enough to add texture
- **Section header labels** — `[FEATURED WORK]` with bracket pseudo-elements. Great terminal typography
- **Links page HUD corners** — same corner bracket treatment on link buttons. Consistent
- **Color system** — cyan primary accent on dark is clean and distinctive. The design tokens are well-organized
- **Animation discipline** — everything uses `var(--duration-normal)` and `var(--ease-out)`. Consistent easing
- **Reduced-motion support** — disables scan lines, status pulse, card corners, typewriter. Complete

---

## 6. COPYWRITING AUDIT

### High Impact

| # | Issue | Location | Current | Suggested |
|---|-------|----------|---------|-----------|
| C1 | **Homepage title is tagline, not benefit** — "CLAY / CODE / SEEK / FEEL" is poetic but doesn't tell visitors what they can DO | [index.html:23](index.html#L23) | "Cerafica — Ceramics / Code / Clay / Computation" | "Handmade Ceramic Vessels — Cerafica \| Long Beach, CA" |
| C2 | **Zero social proof anywhere on site** — no testimonials, no press mentions, no follower count, no "as featured in," no customer photos. Major conversion killer for e-commerce. | All pages | No testimonials, reviews, or credibility markers anywhere | Add testimonials section, Instagram follower count, sold pieces count, customer photos |
| C3 | **Footer CTA is weak** — "JOIN MAILING LIST" is generic, no value proposition | [index.html:293](index.html#L293) | "JOIN MAILING LIST" | "Get first pick of new pieces" or "Join 50+ collectors" |
| C4 | **Shop page lacks intro copy** — goes straight to product grid, no context | [shop.html](shop.html) | No intro paragraph | Add 1-2 sentence intro: "Each piece is one-of-one. When it's gone, it's gone." |

### Medium Impact

| # | Issue | Location | Current | Suggested |
|---|-------|----------|---------|-----------|
| C5 | **Product descriptions are very short** — 6-8 word fragments, not benefit-driven. Don't tell customers what the piece IS (vessel? bowl? sculptural?) | All product cards | "Chun crystallization and metallic luster" | "Vessel with chun crystallization — 6 inches tall, perfect for dried arrangements or solo display" |
| C6 | **Shop page shipping copy is features-only, not benefits** | [shop.html:318-349](shop.html#L318-L349) | "Free shipping on orders over $100. $8 flat rate." | "Your pottery arrives safe and free — shipping's on us for orders over $100" |
| C7 | **"One of One" is potter jargon, not customer language** | [shop.html:297](shop.html#L297) | "One of One" | "One-of-a-Kind" or "Unique Pieces" |
| C8 | **"Available Work" heading is generic** | [index.html:177](index.html#L177) | "Available Pieces" | "Current Collection" or "One-of-a-Kind Vessels" |
| C9 | **Shop page modal CTA "ADD TO CART" is generic** — misses the one-of-one emotional angle | [shop.html:397](shop.html#L397) | "ADD TO CART" | "CLAIM THIS PIECE" or "SECURE THIS PIECE" |
| C10 | **No urgency/scarcity messaging** — one-of-one nature is never leveraged | All pages | Missing | "Once it's gone, it's gone" or "Each piece is unique. No reproductions." |
| C11 | **Zero questions in copy** — Instagram analysis recommends 80%+ question usage; website has 0% | All pages | No questions | Add: "Looking for something specific?" / "What draws you to handmade pottery?" |
| C12 | **No care instructions visible** — would build purchase confidence | [shop.html](shop.html) | Missing | Add "Caring for Your Piece" section |
| C13 | **No gift messaging** — pottery makes great gifts but no gift option | [shop.html](shop.html) | Missing | Add "Send as a Gift" option with note |
| C14 | **Tone inconsistency** — homepage is poetic/philosophical, shop page is purely transactional | index.html vs shop.html | Jarring disconnect | Bring brand voice into shop: "Getting Your Piece Home" instead of "Shipping" |
| C15 | **No cross-selling in product modal** — no "similar pieces" or "you might also like" | [shop.html](shop.html) | Missing | Add "Similar Pieces" section in product detail modal |
| C16 | **About page brand pillars read like definitions, not personality** | [about.html:214-248](about.html#L214-L248) | "Cross-domain: Work spans ceramics, code, music..." | "I don't stay in one lane. Code informs clay. Music informs form. Data informs glaze." |

### Low Impact

| # | Issue | Location | Current | Suggested |
|---|-------|----------|---------|-----------|
| C17 | **Philosophy text is good** — "Clay teaches emergence. Code teaches possibility." | [index.html:169](index.html#L169) | Good | No change needed |
| C18 | **Process section copy is strong** — specific temperatures, techniques | [index.html:248-271](index.html#L248-L271) | Good | No change needed |
| C19 | **Formatting is excellent** — good whitespace, short paragraphs, clear headers | All pages | Good | No change needed |
| C20 | **Technical specificity is a brand strength** — cone 10, 2,350°F, reduction atmosphere | Process section | Good | Lean into this more — don't dumb it down |

---

## 7. WEB DESIGN GUIDELINES AUDIT (Vercel)

### High Impact

| # | Issue | Rule | Location | Fix |
|---|-------|------|----------|-----|
| W1 | **No explicit `<header>` element** — nav is at top but not in semantic header | Semantic HTML | [index.html:108](index.html#L108) | Wrap nav in `<header>` |
| W2 | **Process section has no `<article>` wrappers** — process items are plain divs | Semantic HTML | [index.html:248-271](index.html#L248-L271) | Wrap in `<article>` |
| W3 | **No loading state for shop page** — products load from JSON but no skeleton/loading UI | Loading States | [shop.html](shop.html) | Add shimmer skeleton (CSS class exists but unused) |
| W4 | **Cart drawer has no focus trap** — when cart drawer is open, Tab can navigate to background | Focus Management | [shop.js](js/shop.js) | Implement focus trap when cart drawer opens |
| W5 | **No error boundary** — if products.json fails, no user-visible error | Error Handling | [shop.js](js/shop.js) | Add try/catch with user-visible error state |

### Medium Impact

| # | Issue | Rule | Location | Fix |
|---|-------|------|----------|-----|
| W6 | **Mobile menu doesn't trap focus** | Keyboard Navigation | [nav.js](js/nav.js) | Add focus trap to mobile menu |
| W7 | **No confirmation on "Add to Cart"** for one-of-one items** | UX Patterns | [shop.js](js/shop.js) | Consider a brief confirmation toast for high-value one-of-one adds |
| W8 | **Toast auto-dismisses after 3s** — might miss for slow readers | UX Patterns | [shop.js:18](js/shop.js#L18) | Increase to 5s or add manual dismiss |

### Low Impact

| # | Issue | Rule | Location | Fix |
|---|-------|------|----------|-----|
| W9 | **Navigation is consistent across pages** | Consistency | All pages | Good — no change needed |
| W10 | **Responsive breakpoints appear adequate** | Responsiveness | CSS files | Good — no change needed |

---

## SUMMARY BY SEVERITY

### Critical (Fix Immediately)
- P1: Remove 65MB backup videos from deployed site
- X1: Fix XSS in checkout.html renderError()

### High (Fix This Week)
- S1-S4: Fix canonical URLs and sitemap (remove .html extensions)
- P2-P5: Optimize images (WebP, lazy loading, srcset)
- P6-P8: Add defer to JS, font-display:swap, reduce render-blocking CSS
- X2-X5: Add SRI, CSP, server-side price validation
- D1-D4: Add section depth, enhance card hover, treat process as HUD, use shimmer loading
- C1-C4: Improve title tags, add social proof, strengthen CTAs
- W1-W5: Add header element, loading states, focus traps

### Medium (Fix Soon)
- S5-S13: SEO refinements (keywords, breadcrumbs, hreflang)
- X6-X7: HTTPS headers, cookie consent
- P10-P12: Remove debug screenshots, add cache-busting
- A3-A7: Accessibility refinements
- C5-C8: Improve product descriptions, add shipping info
- D5-D12: Philosophy strip presence, footer email, use amber accent, shop header HUD, modal treatment, card image zoom, about hero, card padding

### Low (Nice to Have)
- D13-D17: Nav backdrop-blur, FAQ markers, contact section, filter active state, toast style

---

## WHAT'S DONE RIGHT

- Strong, distinctive aesthetic (terminal/sci-fi theme, not generic)
- Comprehensive structured data (Organization, WebSite, LocalBusiness, Person, FAQPage, ItemList with Product)
- Good accessibility foundations (skip link, ARIA, reduced-motion, focus-visible)
- Open Graph + Twitter Cards on all pages
- Clean CSS architecture with design tokens
- Cart system with screen reader announcements
- Toast notifications (no alert() calls)
- Intersection Observer for scroll animations (performance-conscious)
- Product images have specific, descriptive alt text
- `prefers-reduced-motion` supported in both CSS and JS
