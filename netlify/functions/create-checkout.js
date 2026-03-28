/**
 * Netlify Function: Create Stripe Checkout Session
 * Handles multi-item cart checkout with dynamic shipping calculation
 */

const stripe = require('stripe')(process.env.STRIPE_SECRET_KEY);
const { calculateShipping, validateCart, calculateSubtotal } = require('./checkout-utils');

exports.handler = async (event, context) => {
  // Enable CORS
  const headers = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
  };

  // Handle preflight request
  if (event.httpMethod === 'OPTIONS') {
    return {
      statusCode: 200,
      headers,
      body: '',
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
        error: 'Failed to create checkout session',
        details: error.message,
      }),
    };
  }
};
