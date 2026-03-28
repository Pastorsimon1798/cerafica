# Multi-Item Checkout - Quick Start

## You Need Just 2 Things

1. **Your Stripe Secret Key** (from https://dashboard.stripe.com/apikeys)
2. **Run one command**

---

## Deploy (One Command)

```bash
# Set your Stripe key and run the deploy script
export STRIPE_SECRET_KEY="sk_test_..."  # or sk_live_ for production
./deploy-checkout.sh
```

That's it. The script will:
- Install Netlify CLI if needed
- Create/configure your Netlify site
- Set environment variables securely
- Deploy the checkout function
- Update all URLs automatically

---

## Test It

1. Go to your shop page
2. Add 2+ items to cart
3. Click CHECKOUT
4. Use test card: `4242 4242 4242 4242`
5. Any future date, any CVC, any ZIP

---

## Switch to Live Payments

```bash
export STRIPE_SECRET_KEY="sk_live_..."  # Your LIVE key
./deploy-checkout.sh
```

---

## If Something Goes Wrong

**Error: "STRIPE_SECRET_KEY not set"**
```bash
export STRIPE_SECRET_KEY="your_key_here"
./deploy-checkout.sh
```

**Error: "Netlify CLI not found"**
```bash
npm install -g netlify-cli
./deploy-checkout.sh
```

**Checkout button does nothing**
- Check browser console for errors
- Verify the deploy completed successfully
- Email simon@cerafica.com with the error

---

## What This Costs

| Service | Cost |
|---------|------|
| Netlify Functions | **$0** (125K requests/month free) |
| Stripe | Same as before (2.9% + 30¢) |
| **Your total** | **$0 extra** |

---

## Files Changed

The deployment creates/updates:
- `netlify/functions/create-checkout.js` - The checkout function
- `netlify.toml` - Netlify configuration  
- `website/js/checkout-config.js` - Auto-generated config
- `website/js/shop.js` - Updated checkout logic
- `website/stripe/checkout.html` - New success page

---

Done. Your multi-item checkout is live.
