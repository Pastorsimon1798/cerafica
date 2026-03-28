# Multi-Item Checkout Setup Guide

## Overview
This setup enables multi-item Stripe checkout on your GitHub Pages site using Netlify Functions (free tier).

## Prerequisites
- Stripe account with Checkout enabled
- Netlify account (free)
- GitHub repository with your cerafica code

---

## Step 1: Get Your Stripe Secret Key

1. Go to https://dashboard.stripe.com/apikeys
2. Copy your **Secret key** (starts with `sk_live_` or `sk_test_` for testing)
3. Keep this secret! Never commit it to git.

---

## Step 2: Create Netlify Site

### Option A: GitHub Integration (Recommended)
1. Go to https://app.netlify.com
2. Click "Add new site" → "Import an existing project"
3. Select GitHub and authorize Netlify
4. Choose your cerafica repository
5. Configure build settings:
   - **Build command:** (leave empty)
   - **Publish directory:** `website`
6. Click "Deploy site"

### Option B: Manual Deploy
1. Zip your project folder
2. Go to https://app.netlify.com/drop
3. Drag and drop the zip file

---

## Step 3: Configure Environment Variables

1. In Netlify dashboard, go to **Site settings** → **Environment variables**
2. Add these variables:

| Key | Value | Example |
|-----|-------|---------|
| `STRIPE_SECRET_KEY` | Your Stripe secret key | `sk_live_...` |
| `CERAFICA_DOMAIN` | Your custom domain | `https://cerafica.com` |

3. Click **Save**

---

## Step 4: Update Function URL in shop.js

Before deploying, update the function URL in `website/js/shop.js`:

```javascript
// Line ~618 (inside initShop function)
const CHECKOUT_FUNCTION_URL = window.location.hostname === 'localhost' 
    ? 'http://localhost:8888/.netlify/functions/create-checkout'
    : 'https://YOUR-SITE-NAME.netlify.app/.netlify/functions/create-checkout';
```

Replace `YOUR-SITE-NAME` with your actual Netlify site URL (from Step 2).

---

## Step 5: Test Locally (Optional)

Install Netlify CLI:
```bash
npm install -g netlify-cli
```

Run locally:
```bash
netlify dev
```

This will start your site at `http://localhost:8888` with functions working.

---

## Step 6: Deploy

### If using GitHub integration:
1. Commit and push your changes
2. Netlify auto-deploys on every push

### If using manual deploy:
1. Re-zip your project
2. Go to https://app.netlify.com/drop
3. Upload the new zip

---

## Step 7: Update DNS (Keep GitHub Pages)

You have two options:

### Option A: Use Netlify for everything (Simplest)
- Point your domain's DNS to Netlify
- Follow Netlify's custom domain setup
- Disable GitHub Pages

### Option B: Keep GitHub Pages, use Netlify only for functions
- Keep your domain pointing to GitHub Pages
- Use the Netlify subdomain (e.g., `cerafica.netlify.app`) just for functions
- Update `CHECKOUT_FUNCTION_URL` to use the Netlify subdomain
- Users stay on GitHub Pages, only checkout calls go to Netlify

**Recommended:** Option A is simpler. Option B keeps your existing setup but requires two services.

---

## Step 8: Test Checkout Flow

1. Go to your shop page
2. Add 2+ items to cart
3. Click "CHECKOUT"
4. You should be redirected to Stripe's checkout page
5. Complete a test payment (use Stripe test card: `4242 4242 4242 4242`)
6. Verify redirect back to success page
7. Check that cart is cleared

---

## Troubleshooting

### "Failed to create checkout session" error
- Check that `STRIPE_SECRET_KEY` is set correctly in Netlify
- Check browser console for detailed error
- Verify function URL is correct in shop.js

### Function not found (404)
- Ensure `netlify.toml` is in project root
- Check that `netlify/functions/create-checkout.js` exists
- Redeploy site

### CORS errors
- Function includes CORS headers (should work automatically)
- If issues persist, check Netlify function logs

### Checkout redirects but shows error
- Check Stripe Dashboard for failed payments
- Verify products.json is accessible at `/data/products.json`

---

## Stripe Test Cards

Use these for testing:

| Card Number | Scenario |
|-------------|----------|
| `4242 4242 4242 4242` | Success |
| `4000 0000 0000 0002` | Declined |
| `4000 0000 0000 9995` | Insufficient funds |

Any future date, any 3-digit CVC, any ZIP code.

---

## Going Live

1. Switch Stripe keys from test to live:
   - Update `STRIPE_SECRET_KEY` in Netlify to live key (`sk_live_...`)
   - Update product `stripe_payment_link` values to live payment links

2. Test one real purchase with small amount to verify

3. Monitor Stripe Dashboard for orders

---

## Cost

| Service | Cost |
|---------|------|
| Netlify Functions | Free (125,000 requests/month) |
| GitHub Pages | Free (existing) |
| Stripe | 2.9% + 30¢ per transaction |
| **Total Fixed** | **$0** |

---

## Support

If you get stuck:
1. Check Netlify function logs: Site → Functions → create-checkout → Logs
2. Check browser console for frontend errors
3. Email simon@cerafica.com with error details
