/**
 * Checkout Utility Functions
 * Extracted for unit testing
 */

// Shipping configuration
const SHIPPING_RATES = {
  FREE_THRESHOLD: 10000, // $100 in cents
  FLAT_RATE: 800,        // $8 in cents
};

/**
 * Calculate shipping cost based on cart total
 * @param {number} subtotal - Cart subtotal in cents
 * @returns {number} Shipping cost in cents
 */
function calculateShipping(subtotal) {
  return subtotal >= SHIPPING_RATES.FREE_THRESHOLD ? 0 : SHIPPING_RATES.FLAT_RATE;
}

/**
 * Validate cart items against product database
 * @param {Array} cartItems - Items from frontend cart
 * @param {Array} products - Products from products.json
 * @returns {Object} { valid: boolean, items: Array, error: string }
 */
function validateCart(cartItems, products) {
  if (!Array.isArray(cartItems) || cartItems.length === 0) {
    return { valid: false, error: 'Cart is empty' };
  }

  const validatedItems = [];
  
  for (const cartItem of cartItems) {
    // Skip undefined slots in sparse arrays
    if (cartItem === undefined) continue;
    
    // Validate cart item structure (null is not allowed)
    if (!cartItem || typeof cartItem !== 'object') {
      return { valid: false, error: 'Invalid cart item' };
    }
    
    // Validate ID exists and is a string/number
    if (!cartItem.id || (typeof cartItem.id !== 'string' && typeof cartItem.id !== 'number')) {
      return { valid: false, error: 'Cart item missing ID' };
    }
    
    // Find product in database
    const product = products.find(p => p.id === cartItem.id);
    
    if (!product) {
      return { valid: false, error: `Product not found: ${cartItem.id}` };
    }
    
    // Check if product is available
    if (!product.available || product.coming_soon) {
      return { valid: false, error: `Product not available: ${product.name}` };
    }
    
    // Validate quantity (must be a positive integer, not boolean)
    const rawQty = cartItem.quantity;
    if (typeof rawQty === 'boolean') {
      return { valid: false, error: `Invalid quantity for ${product.name}` };
    }
    const quantity = Number(rawQty);
    if (!Number.isInteger(quantity) || quantity < 1) {
      return { valid: false, error: `Invalid quantity for ${product.name}` };
    }
    
    // One-of-one items can only have quantity 1
    if (product.one_of_one && quantity > 1) {
      return { valid: false, error: `Only 1 available: ${product.name}` };
    }
    
    // Validate price hasn't been tampered with (log warning but use DB price)
    if (product.price !== cartItem.price) {
      console.warn(`Price mismatch for ${product.name}: expected ${product.price}, got ${cartItem.price}`);
    }
    
    validatedItems.push({
      price_data: {
        currency: 'usd',
        product_data: {
          name: product.name,
          description: product.description.split(' — ')[0].substring(0, 100),
          images: [`https://cerafica.com/images/products/${product.image}`],
        },
        unit_amount: product.price * 100, // Convert to cents
      },
      quantity: quantity,
    });
  }
  
  // Check if we have any valid items after filtering
  if (validatedItems.length === 0) {
    return { valid: false, error: 'Cart is empty' };
  }
  
  return { valid: true, items: validatedItems };
}

/**
 * Calculate subtotal from validated items
 * @param {Array} items - Validated cart items
 * @returns {number} Subtotal in cents
 */
function calculateSubtotal(items) {
  return items.reduce((sum, item) => {
    return sum + (item.price_data.unit_amount * item.quantity);
  }, 0);
}

module.exports = {
  calculateShipping,
  validateCart,
  calculateSubtotal,
  SHIPPING_RATES,
};
