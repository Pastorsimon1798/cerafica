/**
 * Unit Tests for Checkout Utility Functions
 * Red Team Testing Pyramid - Base Layer
 */

const { calculateShipping, validateCart, calculateSubtotal, SHIPPING_RATES } = require('../../netlify/functions/checkout-utils');

// Mock product data for testing
const mockProducts = [
  {
    id: '001',
    name: 'Test Product 1',
    price: 60,
    available: true,
    coming_soon: false,
    one_of_one: false,
    description: 'Test description',
    image: 'test1.jpg',
  },
  {
    id: '002',
    name: 'Test Product 2',
    price: 75,
    available: true,
    coming_soon: false,
    one_of_one: true,
    description: 'Unique item',
    image: 'test2.jpg',
  },
  {
    id: '003',
    name: 'Sold Product',
    price: 50,
    available: false,
    coming_soon: false,
    one_of_one: false,
    description: 'Not available',
    image: 'test3.jpg',
  },
  {
    id: '004',
    name: 'Coming Soon Product',
    price: 80,
    available: false,
    coming_soon: true,
    one_of_one: false,
    description: 'Coming soon',
    image: 'test4.jpg',
  },
];

// ============================================================================
// calculateShipping() Tests
// ============================================================================

describe('calculateShipping()', () => {
  test('returns 0 for orders >= $100 (10000 cents)', () => {
    expect(calculateShipping(10000)).toBe(0);
    expect(calculateShipping(15000)).toBe(0);
    expect(calculateShipping(999999)).toBe(0);
  });

  test('returns $8 (800 cents) for orders < $100', () => {
    expect(calculateShipping(0)).toBe(800);
    expect(calculateShipping(100)).toBe(800);
    expect(calculateShipping(9999)).toBe(800);
  });

  test('handles edge case at exactly $100', () => {
    expect(calculateShipping(10000)).toBe(0); // Free shipping at threshold
  });

  test('handles negative subtotals (defensive)', () => {
    expect(calculateShipping(-100)).toBe(800);
  });
});

// ============================================================================
// validateCart() Tests
// ============================================================================

describe('validateCart()', () => {
  test('accepts valid single item', () => {
    const cart = [{ id: '001', price: 60, quantity: 1 }];
    const result = validateCart(cart, mockProducts);
    expect(result.valid).toBe(true);
    expect(result.items).toHaveLength(1);
    expect(result.items[0].quantity).toBe(1);
    expect(result.items[0].price_data.unit_amount).toBe(6000); // 60 * 100 cents
  });

  test('accepts valid multiple items', () => {
    const cart = [
      { id: '001', price: 60, quantity: 1 },
      { id: '002', price: 75, quantity: 1 },
    ];
    const result = validateCart(cart, mockProducts);
    expect(result.valid).toBe(true);
    expect(result.items).toHaveLength(2);
  });

  test('rejects empty cart', () => {
    const result = validateCart([], mockProducts);
    expect(result.valid).toBe(false);
    expect(result.error).toBe('Cart is empty');
  });

  test('rejects null cart', () => {
    const result = validateCart(null, mockProducts);
    expect(result.valid).toBe(false);
    expect(result.error).toBe('Cart is empty');
  });

  test('rejects undefined cart', () => {
    const result = validateCart(undefined, mockProducts);
    expect(result.valid).toBe(false);
    expect(result.error).toBe('Cart is empty');
  });

  test('rejects non-array cart', () => {
    const result = validateCart('hacked', mockProducts);
    expect(result.valid).toBe(false);
    expect(result.error).toBe('Cart is empty');
  });

  test('rejects non-existent product', () => {
    const cart = [{ id: '999', price: 100, quantity: 1 }];
    const result = validateCart(cart, mockProducts);
    expect(result.valid).toBe(false);
    expect(result.error).toContain('Product not found');
  });

  test('rejects unavailable product', () => {
    const cart = [{ id: '003', price: 50, quantity: 1 }];
    const result = validateCart(cart, mockProducts);
    expect(result.valid).toBe(false);
    expect(result.error).toContain('not available');
  });

  test('rejects coming_soon product', () => {
    const cart = [{ id: '004', price: 80, quantity: 1 }];
    const result = validateCart(cart, mockProducts);
    expect(result.valid).toBe(false);
    expect(result.error).toContain('not available');
  });

  test('rejects one-of-one item with quantity > 1', () => {
    const cart = [{ id: '002', price: 75, quantity: 2 }];
    const result = validateCart(cart, mockProducts);
    expect(result.valid).toBe(false);
    expect(result.error).toContain('Only 1 available');
  });

  test('accepts one-of-one item with quantity = 1', () => {
    const cart = [{ id: '002', price: 75, quantity: 1 }];
    const result = validateCart(cart, mockProducts);
    expect(result.valid).toBe(true);
  });

  test('rejects zero quantity', () => {
    const cart = [{ id: '001', price: 60, quantity: 0 }];
    const result = validateCart(cart, mockProducts);
    expect(result.valid).toBe(false);
    expect(result.error).toContain('Invalid quantity');
  });

  test('rejects negative quantity', () => {
    const cart = [{ id: '001', price: 60, quantity: -1 }];
    const result = validateCart(cart, mockProducts);
    expect(result.valid).toBe(false);
    expect(result.error).toContain('Invalid quantity');
  });

  test('rejects fractional quantity', () => {
    const cart = [{ id: '001', price: 60, quantity: 1.5 }];
    const result = validateCart(cart, mockProducts);
    expect(result.valid).toBe(false);
    expect(result.error).toContain('Invalid quantity');
  });

  test('rejects missing ID', () => {
    const cart = [{ price: 60, quantity: 1 }];
    const result = validateCart(cart, mockProducts);
    expect(result.valid).toBe(false);
    expect(result.error).toContain('missing ID');
  });

  test('rejects invalid cart item (null)', () => {
    const cart = [null];
    const result = validateCart(cart, mockProducts);
    expect(result.valid).toBe(false);
    expect(result.error).toContain('Invalid cart item');
  });

  test('rejects invalid cart item (string)', () => {
    const cart = ['hacked'];
    const result = validateCart(cart, mockProducts);
    expect(result.valid).toBe(false);
    expect(result.error).toContain('Invalid cart item');
  });

  test('uses database price over frontend price (price tampering protection)', () => {
    const cart = [{ id: '001', price: 1, quantity: 1 }]; // Trying to pay $1 instead of $60
    const result = validateCart(cart, mockProducts);
    expect(result.valid).toBe(true);
    expect(result.items[0].price_data.unit_amount).toBe(6000); // Still charges $60
  });

  test('handles XSS attempt in product name (sanitization)', () => {
    const maliciousProducts = [
      {
        id: 'xxx',
        name: '<script>alert("xss")</script>',
        price: 10,
        available: true,
        coming_soon: false,
        one_of_one: false,
        description: 'Test',
        image: 'test.jpg',
      },
    ];
    const cart = [{ id: 'xxx', price: 10, quantity: 1 }];
    const result = validateCart(cart, maliciousProducts);
    expect(result.valid).toBe(true);
    // Name should be passed through (Stripe handles sanitization)
    expect(result.items[0].price_data.product_data.name).toBe('<script>alert("xss")</script>');
  });

  test('handles very long description (truncation)', () => {
    const longDescProducts = [
      {
        id: 'long',
        name: 'Test',
        price: 10,
        available: true,
        coming_soon: false,
        one_of_one: false,
        description: 'A'.repeat(1000), // Very long description
        image: 'test.jpg',
      },
    ];
    const cart = [{ id: 'long', price: 10, quantity: 1 }];
    const result = validateCart(cart, longDescProducts);
    expect(result.valid).toBe(true);
    expect(result.items[0].price_data.product_data.description.length).toBeLessThanOrEqual(100);
  });

  test('handles unicode/emojis in product name', () => {
    const emojiProducts = [
      {
        id: 'emoji',
        name: '🏺 Ceramic Vase 🎨',
        price: 50,
        available: true,
        coming_soon: false,
        one_of_one: false,
        description: 'Art',
        image: 'test.jpg',
      },
    ];
    const cart = [{ id: 'emoji', price: 50, quantity: 1 }];
    const result = validateCart(cart, emojiProducts);
    expect(result.valid).toBe(true);
    expect(result.items[0].price_data.product_data.name).toBe('🏺 Ceramic Vase 🎨');
  });

  test('rejects large quantity exceeding max', () => {
    const cart = [{ id: '001', price: 60, quantity: 999999 }];
    const result = validateCart(cart, mockProducts);
    expect(result.valid).toBe(false);
    expect(result.error).toContain('Invalid quantity');
  });
});

// ============================================================================
// calculateSubtotal() Tests
// ============================================================================

describe('calculateSubtotal()', () => {
  test('calculates single item correctly', () => {
    const items = [
      { price_data: { unit_amount: 6000 }, quantity: 1 },
    ];
    expect(calculateSubtotal(items)).toBe(6000);
  });

  test('calculates multiple items correctly', () => {
    const items = [
      { price_data: { unit_amount: 6000 }, quantity: 1 },
      { price_data: { unit_amount: 7500 }, quantity: 1 },
    ];
    expect(calculateSubtotal(items)).toBe(13500);
  });

  test('calculates quantity > 1 correctly', () => {
    const items = [
      { price_data: { unit_amount: 6000 }, quantity: 3 },
    ];
    expect(calculateSubtotal(items)).toBe(18000);
  });

  test('handles empty array', () => {
    expect(calculateSubtotal([])).toBe(0);
  });

  test('handles mixed quantities', () => {
    const items = [
      { price_data: { unit_amount: 6000 }, quantity: 2 },
      { price_data: { unit_amount: 7500 }, quantity: 1 },
      { price_data: { unit_amount: 5000 }, quantity: 3 },
    ];
    expect(calculateSubtotal(items)).toBe(12000 + 7500 + 15000); // 34500
  });
});

// ============================================================================
// Integration: Shipping + Subtotal
// ============================================================================

describe('Shipping + Subtotal Integration', () => {
  test('free shipping for $100+ order', () => {
    const cart = [
      { id: '001', price: 60, quantity: 2 }, // $120
    ];
    const validation = validateCart(cart, mockProducts);
    expect(validation.valid).toBe(true);
    
    const subtotal = calculateSubtotal(validation.items);
    expect(subtotal).toBe(12000); // $120 in cents
    
    const shipping = calculateShipping(subtotal);
    expect(shipping).toBe(0); // Free shipping
  });

  test('paid shipping for <$100 order', () => {
    const cart = [
      { id: '001', price: 60, quantity: 1 }, // $60
    ];
    const validation = validateCart(cart, mockProducts);
    expect(validation.valid).toBe(true);
    
    const subtotal = calculateSubtotal(validation.items);
    expect(subtotal).toBe(6000); // $60 in cents
    
    const shipping = calculateShipping(subtotal);
    expect(shipping).toBe(800); // $8 shipping
  });

  test('exactly $100 threshold', () => {
    // Need to find combination that equals exactly $100
    const customProducts = [
      { id: 'test', name: 'Test', price: 100, available: true, coming_soon: false, one_of_one: false, description: 'Test', image: 'test.jpg' },
    ];
    const cart = [{ id: 'test', price: 100, quantity: 1 }];
    const validation = validateCart(cart, customProducts);
    expect(validation.valid).toBe(true);
    
    const subtotal = calculateSubtotal(validation.items);
    expect(subtotal).toBe(10000); // Exactly $100
    
    const shipping = calculateShipping(subtotal);
    expect(shipping).toBe(0); // Free at exactly $100
  });
});
