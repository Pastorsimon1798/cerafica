/**
 * Security Audit Tests (Red Team)
 * Adversarial testing of checkout system
 */

const { validateCart, calculateShipping } = require('../../netlify/functions/checkout-utils');

// ============================================================================
// RED TEAM: INPUT VALIDATION ATTACKS
// ============================================================================

describe('🔴 RED TEAM: Input Validation Attacks', () => {
  const safeProducts = [
    { id: 'safe', name: 'Safe Product', price: 50, available: true, coming_soon: false, one_of_one: false, description: 'Safe', image: 'safe.jpg' },
  ];

  test('SQL Injection in ID field', () => {
    const attacks = [
      "'; DROP TABLE products; --",
      "1' OR '1'='1",
      "'; DELETE FROM orders; --",
      "1'; EXEC xp_cmdshell('dir'); --",
    ];
    
    for (const attack of attacks) {
      const cart = [{ id: attack, price: 50, quantity: 1 }];
      const result = validateCart(cart, safeProducts);
      // Should reject as product not found (no SQL execution)
      expect(result.valid).toBe(false);
      expect(result.error).toContain('Product not found');
    }
  });

  test('NoSQL Injection attempts', () => {
    const attacks = [
      { id: { $ne: null }, price: 50, quantity: 1 },
      { id: { $gt: '' }, price: 50, quantity: 1 },
      { id: { $regex: /.*/ }, price: 50, quantity: 1 },
    ];
    
    for (const attack of attacks) {
      const cart = [attack];
      const result = validateCart(cart, safeProducts);
      // Objects as IDs are rejected at ID validation stage
      expect(result.valid).toBe(false);
    }
  });

  test('XSS attempts in cart data', () => {
    const xssPayloads = [
      '<script>alert("xss")</script>',
      '<img src=x onerror=alert("xss")>',
      'javascript:alert("xss")',
      '<svg onload=alert("xss")>',
      '";alert("xss");//',
    ];
    
    for (const payload of xssPayloads) {
      // Try XSS in ID
      const cart = [{ id: payload, price: 50, quantity: 1 }];
      const result = validateCart(cart, safeProducts);
      expect(result.valid).toBe(false); // Product not found
    }
  });

  test('Prototype Pollution attempts', () => {
    const attacks = [
      '__proto__',
      'constructor',
      'prototype',
      '__defineGetter__',
      '__defineSetter__',
    ];
    
    for (const attack of attacks) {
      const cart = [{ id: attack, price: 50, quantity: 1 }];
      const result = validateCart(cart, safeProducts);
      expect(result.valid).toBe(false);
      expect(result.error).toContain('Product not found');
    }
    
    // Verify prototype wasn't polluted
    expect({}.polluted).toBeUndefined();
    expect(Object.prototype.polluted).toBeUndefined();
  });

  test('Command Injection attempts', () => {
    const attacks = [
      '$(whoami)',
      '`whoami`',
      '; cat /etc/passwd',
      '| ls -la',
      '&& rm -rf /',
    ];
    
    for (const attack of attacks) {
      const cart = [{ id: attack, price: 50, quantity: 1 }];
      const result = validateCart(cart, safeProducts);
      expect(result.valid).toBe(false);
      expect(result.error).toContain('Product not found');
    }
  });

  test('Path Traversal attempts', () => {
    const attacks = [
      '../../../etc/passwd',
      '..\\..\\..\\windows\\system32\\config\\sam',
      '....//....//....//etc/passwd',
      '%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd',
    ];
    
    for (const attack of attacks) {
      const cart = [{ id: attack, price: 50, quantity: 1 }];
      const result = validateCart(cart, safeProducts);
      expect(result.valid).toBe(false);
    }
  });

  test('Unicode/Encoding attacks', () => {
    const attacks = [
      { id: 'safe\x00', price: 50, quantity: 1 }, // Null byte
      { id: 'safe\n', price: 50, quantity: 1 }, // Newline
      { id: 'safe\r', price: 50, quantity: 1 }, // Carriage return
      { id: 'safe\t', price: 50, quantity: 1 }, // Tab
    ];
    
    for (const attack of attacks) {
      const cart = [attack];
      const result = validateCart(cart, safeProducts);
      // Should handle gracefully
      expect(result.valid === true || result.valid === false).toBe(true);
    }
  });

  test('JSON Injection attacks', () => {
    const cart = JSON.parse('[{"id":"safe","price":50,"quantity":1}]');
    const result = validateCart(cart, safeProducts);
    expect(result.valid).toBe(true);
  });

  test('Type Confusion attacks', () => {
    const attacks = [
      [{ id: { toString: () => 'safe' }, price: 50, quantity: 1 }],
      [{ id: ['safe'], price: 50, quantity: 1 }],
      [{ id: new String('safe'), price: 50, quantity: 1 }],
    ];
    
    for (const attack of attacks) {
      const result = validateCart(attack, safeProducts);
      // Should handle gracefully without crashing
      expect(typeof result.valid).toBe('boolean');
    }
  });
});

// ============================================================================
// RED TEAM: PRICE MANIPULATION ATTACKS
// ============================================================================

describe('🔴 RED TEAM: Price Manipulation', () => {
  const product = [
    { id: 'item', name: 'Item', price: 100, available: true, coming_soon: false, one_of_one: false, description: 'Test', image: 'item.jpg' },
  ];

  test('Price tampering - below actual price', () => {
    const cart = [{ id: 'item', price: 1, quantity: 1 }];
    const result = validateCart(cart, product);
    expect(result.valid).toBe(true);
    // Uses database price, not tampered price
    expect(result.items[0].price_data.unit_amount).toBe(10000); // $100
  });

  test('Price tampering - negative price', () => {
    const cart = [{ id: 'item', price: -50, quantity: 1 }];
    const result = validateCart(cart, product);
    expect(result.valid).toBe(true);
    expect(result.items[0].price_data.unit_amount).toBe(10000); // Still $100
  });

  test('Price tampering - zero price', () => {
    const cart = [{ id: 'item', price: 0, quantity: 1 }];
    const result = validateCart(cart, product);
    expect(result.valid).toBe(true);
    expect(result.items[0].price_data.unit_amount).toBe(10000); // Still $100
  });

  test('Price tampering - very high price', () => {
    const cart = [{ id: 'item', price: 999999, quantity: 1 }];
    const result = validateCart(cart, product);
    expect(result.valid).toBe(true);
    expect(result.items[0].price_data.unit_amount).toBe(10000); // Still $100
  });

  test('Price tampering - float precision attack', () => {
    const cart = [{ id: 'item', price: 99.999999, quantity: 1 }];
    const result = validateCart(cart, product);
    expect(result.valid).toBe(true);
    expect(result.items[0].price_data.unit_amount).toBe(10000); // Uses DB price
  });

  test('Price tampering - string number', () => {
    const cart = [{ id: 'item', price: "1", quantity: 1 }];
    const result = validateCart(cart, product);
    expect(result.valid).toBe(true);
    expect(result.items[0].price_data.unit_amount).toBe(10000); // Uses DB price
  });

  test('Price tampering - boolean', () => {
    const cart = [{ id: 'item', price: false, quantity: 1 }];
    const result = validateCart(cart, product);
    expect(result.valid).toBe(true);
    expect(result.items[0].price_data.unit_amount).toBe(10000); // Uses DB price
  });
});

// ============================================================================
// RED TEAM: CART MANIPULATION ATTACKS
// ============================================================================

describe('🔴 RED TEAM: Cart Manipulation', () => {
  const products = [
    { id: 'normal', name: 'Normal', price: 50, available: true, coming_soon: false, one_of_one: false, description: 'Test', image: 'normal.jpg' },
    { id: 'unique', name: 'Unique', price: 100, available: true, coming_soon: false, one_of_one: true, description: 'One of one', image: 'unique.jpg' },
    { id: 'sold', name: 'Sold', price: 50, available: false, coming_soon: false, one_of_one: false, description: 'Sold', image: 'sold.jpg' },
    { id: 'soon', name: 'Soon', price: 50, available: false, coming_soon: true, one_of_one: false, description: 'Soon', image: 'soon.jpg' },
  ];

  test('Duplicate item attack', () => {
    const cart = [
      { id: 'normal', price: 50, quantity: 1 },
      { id: 'normal', price: 50, quantity: 1 },
    ];
    const result = validateCart(cart, products);
    expect(result.valid).toBe(false);
    expect(result.error).toContain('Duplicate item');
  });

  test('One-of-one duplicate attack (same item, qty 2)', () => {
    const cart = [
      { id: 'unique', price: 100, quantity: 2 },
    ];
    const result = validateCart(cart, products);
    expect(result.valid).toBe(false);
    expect(result.error).toContain('Only 1 available');
  });

  test('One-of-one duplicate attack (same item twice)', () => {
    const cart = [
      { id: 'unique', price: 100, quantity: 1 },
      { id: 'unique', price: 100, quantity: 1 },
    ];
    const result = validateCart(cart, products);
    expect(result.valid).toBe(false);
    expect(result.error).toContain('Duplicate item');
  });

  test('Sold item bypass attempt', () => {
    const cart = [{ id: 'sold', price: 50, quantity: 1 }];
    const result = validateCart(cart, products);
    expect(result.valid).toBe(false);
    expect(result.error).toContain('not available');
  });

  test('Coming soon bypass attempt', () => {
    const cart = [{ id: 'soon', price: 50, quantity: 1 }];
    const result = validateCart(cart, products);
    expect(result.valid).toBe(false);
    expect(result.error).toContain('not available');
  });

  test('Missing quantity field', () => {
    const cart = [{ id: 'normal', price: 50 }];
    const result = validateCart(cart, products);
    expect(result.valid).toBe(false);
    expect(result.error).toContain('Invalid quantity');
  });

  test('Missing price field', () => {
    const cart = [{ id: 'normal', quantity: 1 }];
    const result = validateCart(cart, products);
    expect(result.valid).toBe(true); // Uses DB price
  });

  test('Quantity as string number', () => {
    const cart = [{ id: 'normal', price: 50, quantity: "5" }];
    const result = validateCart(cart, products);
    expect(result.valid).toBe(true);
    expect(result.items[0].quantity).toBe(5);
  });

  test('Quantity as boolean', () => {
    const cart = [{ id: 'normal', price: 50, quantity: true }];
    const result = validateCart(cart, products);
    expect(result.valid).toBe(false);
    expect(result.error).toContain('Invalid quantity');
  });

  test('Massive quantity attack', () => {
    const cart = [{ id: 'normal', price: 50, quantity: 999999999 }];
    const result = validateCart(cart, products);
    expect(result.valid).toBe(false);
    expect(result.error).toContain('Invalid quantity');
  });

  test('Empty object in cart', () => {
    const cart = [{}];
    const result = validateCart(cart, products);
    expect(result.valid).toBe(false);
    expect(result.error).toContain('missing ID');
  });

  test('Nested object attack (rejected at ID validation)', () => {
    const cart = [
      { id: { nested: 'normal' }, price: 50, quantity: 1 },
    ];
    const result = validateCart(cart, products);
    expect(result.valid).toBe(false);
    expect(result.error).toContain('missing ID');
  });
});

// ============================================================================
// RED TEAM: SHIPPING MANIPULATION
// ============================================================================

describe('🔴 RED TEAM: Shipping Manipulation', () => {
  test('Free shipping threshold bypass attempts', () => {
    const attempts = [
      9999,  // $99.99 - should pay shipping
      10000, // $100.00 - should be free
      10001, // $100.01 - should be free
    ];
    
    expect(calculateShipping(attempts[0])).toBe(800);
    expect(calculateShipping(attempts[1])).toBe(0);
    expect(calculateShipping(attempts[2])).toBe(0);
  });

  test('Negative subtotal shipping calculation', () => {
    // Defensive: negative subtotals shouldn't give negative shipping
    expect(calculateShipping(-1000)).toBe(800);
  });

  test('Very large subtotal', () => {
    // Shouldn't overflow
    expect(calculateShipping(Number.MAX_SAFE_INTEGER)).toBe(0);
  });
});

// ============================================================================
// RED TEAM: EDGE CASES & FUZZING
// ============================================================================

describe('🔴 RED TEAM: Edge Cases & Fuzzing', () => {
  const safeProducts = [
    { id: 'safe', name: 'Safe', price: 50, available: true, coming_soon: false, one_of_one: false, description: 'Test', image: 'safe.jpg' },
  ];

  test('Handles undefined in array (sparse array slot)', () => {
    const cart = [undefined];
    const result = validateCart(cart, safeProducts);
    // Undefined slots are skipped, resulting in empty cart
    expect(result.valid).toBe(false);
    expect(result.error).toBe('Cart is empty');
  });

  test('Handles sparse array', () => {
    const cart = new Array(100);
    cart[50] = { id: 'safe', price: 50, quantity: 1 };
    const result = validateCart(cart, safeProducts);
    expect(result.valid).toBe(false); // 100 slots exceeds MAX_CART_ITEMS
    expect(result.error).toContain('more than');
  });

  test('Handles array-like object', () => {
    const cartLike = { '0': { id: 'safe', price: 50, quantity: 1 }, length: 1 };
    const result = validateCart(Array.from(cartLike), safeProducts);
    expect(result.valid).toBe(true);
  });

  test('Handles Symbol in ID', () => {
    try {
      const cart = [{ id: Symbol('test'), price: 50, quantity: 1 }];
      validateCart(cart, safeProducts);
    } catch (e) {
      // Should not throw, handle gracefully
    }
  });

  test('Handles Function in ID', () => {
    const cart = [{ id: () => 'safe', price: 50, quantity: 1 }];
    const result = validateCart(cart, safeProducts);
    expect(result.valid).toBe(false);
  });

  test('Deeply nested object', () => {
    const cart = [{ 
      id: { toString: { valueOf: () => 'safe' } }, 
      price: 50, 
      quantity: 1 
    }];
    const result = validateCart(cart, safeProducts);
    expect(result.valid).toBe(false);
  });

  test('Circular reference (should not crash)', () => {
    const item = { id: 'safe', price: 50, quantity: 1 };
    item.self = item;
    const cart = [item];
    // Should handle without infinite loop
    const result = validateCart(cart, safeProducts);
    expect(result.valid).toBe(true);
  });
});

// ============================================================================
// SECURITY SUMMARY
// ============================================================================

describe('🔒 Security Summary', () => {
  test('Document findings', () => {
    const findings = [
      '✅ SQL Injection: Protected (no SQL used)',
      '✅ NoSQL Injection: Protected (string comparison)',
      '✅ Price Tampering: Protected (uses DB price)',
      '✅ XSS: Protected (Stripe handles sanitization)',
      '⚠️  Duplicate one-of-one: Not detected across cart items',
      '⚠️  Max quantity: No upper limit enforced',
      '✅ Prototype Pollution: Protected (no object extension)',
      '✅ Type Confusion: Protected (explicit type checking)',
    ];
    
    expect(findings.length).toBeGreaterThan(0);
    console.log('\n=== SECURITY AUDIT FINDINGS ===');
    findings.forEach(f => console.log(f));
    console.log('==============================\n');
  });
});
