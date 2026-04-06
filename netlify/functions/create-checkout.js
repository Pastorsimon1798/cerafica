/**
 * Netlify Function: Create Stripe Checkout Session
 * Handles multi-item cart checkout with dynamic shipping calculation
 */

const stripe = require('stripe')(process.env.STRIPE_SECRET_KEY);
const { calculateShipping, validateCart, calculateSubtotal } = require('./checkout-utils');

// Simple in-memory rate limiter
const rateLimiter = {
  requests: new Map(),
  WINDOW_MS: 60_000,
  MAX_REQUESTS: 10,
  check(ip) {
    const now = Date.now();
    const requests = this.requests.get(ip) || [];
    const recent = requests.filter(t => now - t < this.WINDOW_MS);
    if (recent.length >= this.MAX_REQUESTS) return false;
    recent.push(now);
    this.requests.set(ip, recent);
    // Cleanup old entries periodically
    if (Math.random() < 0.01) {
      for (const [key, vals] of this.requests.entries()) {
        if (vals.every(t => now - t >= this.WINDOW_MS)) this.requests.delete(key);
      }
    }
    return true;
  }
};

exports.handler = async (event, context) => {
  // CORS - validate origin
  const allowedOrigins = [
    'https://cerafica.com',
    'https://cerafica-checkout.netlify.app',
    'http://localhost:8888',
  ];
  const origin = event.headers.origin || event.headers.Origin || '';
  const corsOrigin = allowedOrigins.includes(origin) ? origin : allowedOrigins[0];
  const headers = {
    'Access-Control-Allow-Origin': corsOrigin,
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Max-Age': '86400',
  };

  // Handle preflight request
  if (event.httpMethod === 'OPTIONS') {
    return {
      statusCode: 200,
      headers,
      body: '',
    };
  }

  // Rate limiting
  const clientIp = event.headers['client-ip'] || event.headers['x-forwarded-for'] || 'unknown';
  if (!rateLimiter.check(clientIp)) {
    return {
      statusCode: 429,
      headers,
      body: JSON.stringify({ error: 'Too many requests. Please try again later.' }),
    };
  }

  // Only accept POST requests
  if (event.httpMethod !== 'POST') {
    return {
      statusCode: 405,
      headers,
      body: JSON.stringify({ error: 'Method not allowed' }),
    };
  }

  try {
    // Parse request body with error handling
    let cartItems;
    try {
      const body = JSON.parse(event.body);
      cartItems = body.items;
    } catch (parseError) {
      console.error('JSON parse error:', parseError);
      return {
        statusCode: 400,
        headers,
        body: JSON.stringify({ error: 'Invalid JSON body' }),
      };
    }
    
    // Fetch products from JSON (use same origin for deployed site)
    const domain = process.env.CERAFICA_DOMAIN || 'https://cerafica-checkout.netlify.app';
    if (!domain.startsWith('https://')) {
      throw new Error('Invalid domain configuration');
    }
    let products;
    try {
      const productsResponse = await fetch(`${domain}/data/products.json`);
      if (!productsResponse.ok) {
        throw new Error(`Failed to load product data: ${productsResponse.status}`);
      }
      products = await productsResponse.json();
    } catch (fetchError) {
      console.error('Product fetch error:', fetchError);
      return {
        statusCode: 500,
        headers,
        body: JSON.stringify({ error: 'Failed to load product catalog' }),
      };
    }
    
    // Validate cart
    const validation = validateCart(cartItems, products);
    if (!validation.valid) {
      console.warn('Cart validation failed:', validation.error);
      return {
        statusCode: 400,
        headers,
        body: JSON.stringify({ error: validation.error }),
      };
    }
    
    // Calculate subtotal for shipping
    const subtotal = calculateSubtotal(validation.items);
    const shippingCost = calculateShipping(subtotal);
    
    // Create Stripe Checkout Session
    const session = await stripe.checkout.sessions.create({
      payment_method_types: ['card'],
      line_items: validation.items,
      mode: 'payment',
      success_url: `${domain}/stripe/checkout.html?session_id={CHECKOUT_SESSION_ID}`,
      cancel_url: `${domain}/shop.html?canceled=true`,
      shipping_address_collection: {
        allowed_countries: ['US'],
      },
      shipping_options: [
        {
          shipping_rate_data: {
            type: 'fixed_amount',
            fixed_amount: {
              amount: shippingCost,
              currency: 'usd',
            },
            display_name: shippingCost === 0 ? 'Free Shipping (orders over $100)' : 'Standard Shipping',
            delivery_estimate: {
              minimum: {
                unit: 'business_day',
                value: 5,
              },
              maximum: {
                unit: 'business_day',
                value: 7,
              },
            },
          },
        },
      ],
      // Auto-calculate tax if enabled in Stripe
      automatic_tax: {
        enabled: false, // Set to true if you have Stripe Tax configured
      },
      // Collect phone number for shipping issues
      phone_number_collection: {
        enabled: true,
      },
      // Custom metadata for your records
      metadata: {
        source: 'cerafica-website',
        item_count: cartItems.length.toString(),
      },
    });
    
    console.log('Checkout session created:', session.id, 'Items:', cartItems.length);
    
    return {
      statusCode: 200,
      headers,
      body: JSON.stringify({
        url: session.url,
        sessionId: session.id,
      }),
    };
    
  } catch (error) {
    console.error('Checkout error:', error);

    return {
      statusCode: 500,
      headers,
      body: JSON.stringify({
        error: 'Unable to process checkout. Please try again later.',
      }),
    };
  }
};
