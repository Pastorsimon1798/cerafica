/**
 * Brand Configuration for Website
 *
 * This file centralizes brand-specific values so the website
 * can be customized without modifying shop.js or HTML files.
 *
 * To customize: edit the BRAND object below.
 */

const BRAND = {
    name: "Cerafica",
    tagline: "Postmodern Organic Brutalist ceramics",
    handle: "@cerafica_design",
    domain: "cerafica.com",
    cartKey: "cerafica_cart",

    // Product display
    product: {
        // Domain-specific fields to show on product cards
        // Each entry: { key, label, showOnCard, type }
        domainFields: [
            { key: "food_safe", label: "Food Safe", showOnCard: true, type: "boolean" },
            { key: "one_of_one", label: "One of One", showOnCard: true, type: "boolean" },
            { key: "care", label: "Care", showOnCard: false, type: "string" },
        ],
        // If true, products with one_of_one=true can't have quantity > 1
        limitOneOfOne: true,
    },
};

// Make BRAND available globally
window.BRAND = BRAND;
