# Cerafica Email Voice & Templates

> How Cerafica sounds in inboxes — from order confirmations to newsletters to post-purchase follow-ups.
> Version: 1.0.0

---

## 1. Email Philosophy

Cerafica emails are:
- **Direct** — no fluff, no excessive gratitude
- **Systematic** — clear structure, scannable details
- **Warm but not cloying** — friendly without being saccharine
- **Terminal-adjacent** — subtle hints of the brand's code/clay aesthetic

**Every email must answer three questions within 3 seconds:**
1. What is this about?
2. What do I need to know?
3. What should I do next?

---

## 2. Email Design Rules

### Visual Style
- **Background:** `#0A0A0A` or `#111111`
- **Text:** `#E8E8E8` primary, `#BBBBBB` body, `#888888` muted
- **Accent:** `#1EC3D2` for links and CTAs
- **Highlight:** `#FFAA00` for prices, tracking numbers, important alerts
- **Font:** JetBrains Mono (or web-safe monospace fallback)
- **Width:** Max 600px, centered
- **CTA buttons:** Sharp corners, uppercase, cyan background with dark text

### Structure
1. **Header:** Logo + status line
2. **Greeting:** First name if known, otherwise none
3. **Body:** 1-3 short paragraphs max
4. **Details box:** Order info, shipping, tracking
5. **CTA:** One clear action
6. **Footer:** `SYS:ONLINE // CERAFICA v1.0 // LONG BEACH, CA`

---

## 3. Voice Rules for Email

### Do
- Use short paragraphs (2-3 sentences max)
- Lead with the most important information
- Use terminal syntax sparingly (`>`, `//`, `SYS:`)
- Be specific about timelines and next steps
- Include one human detail when relevant

### Don't
- Open with "We hope this email finds you well"
- Over-apologize for delays
- Use more than one exclamation point per email
- Write paragraphs longer than 4 lines
- Include generic sign-offs like "Best regards from the team"

### Signature

```
— Simon
Cerafica // Long Beach, CA
```

No titles. No phone numbers. No social icons in the signature.

---

## 4. Template: Order Confirmation

**Subject:** Your planetary vessel is secured

**Preview:** Order #CERA-1234 — estimated dispatch in 2-3 business days.

```
CERAFICA
SYS:ONLINE // ORDER CONFIRMED

Hi [First Name],

Your order is locked in. Here's what happens next:

[ORDER DETAILS BOX]
Order: #CERA-1234
Item: Pallth-7 — Stoneware Vessel
Price: $125.00
Status: Confirmed

Estimated dispatch: 2-3 business days.

We'll send tracking as soon as your piece is packed and on its way.

[VIEW ORDER STATUS]

— Simon
Cerafica // Long Beach, CA
```

---

## 5. Template: Shipping Notification

**Subject:** Your vessel is on its way

**Preview:** Tracking number inside. Estimated delivery: [date].

```
CERAFICA
SYS:IN_TRANSIT // DISPATCH CONFIRMED

Hi [First Name],

Your piece has left the studio and is headed your way.

[SHIPPING DETAILS BOX]
Carrier: USPS
Tracking: [TRACKING NUMBER — amber highlight]
Estimated delivery: [DATE]

Every piece is double-boxed with plenty of padding. I've shipped 50+ vessels and haven't lost one yet.

[TRACK PACKAGE]

— Simon
Cerafica // Long Beach, CA
```

---

## 6. Template: UGC Request

**Subject:** Show us your piece in the wild

**Preview:** We'd love to see how [Piece Name] looks in its new home.

```
CERAFICA
SYS:REQUEST // USER GENERATED CONTENT

Hi [First Name],

Your [Piece Name] should be settling into its new home by now.

If you're up for it, I'd love to see a photo of it in your space. No staging required — bookshelves, countertops, and messy desks all welcome.

If you share on Instagram, tag @cerafica_design. Or just reply to this email with a photo.

[REPLY WITH PHOTO]

— Simon
Cerafica // Long Beach, CA
```

---

## 7. Template: Waitlist Notification

**Subject:** [Piece Name] is back in stock

**Preview:** You asked. We fired. Limited quantity available now.

```
CERAFICA
SYS:RESTOCK // WAITLIST NOTIFICATION

Hi [First Name],

The wait is over. [Piece Name] is back from the kiln and available now.

This is a small batch — [X] pieces total. Waitlist gets first access for the next 24 hours.

[SHOP NOW]

— Simon
Cerafica // Long Beach, CA
```

---

## 8. Template: Newsletter / New Drop

**Subject:** New kiln opening: [Drop Name]

**Preview:** [X] new pieces now available. Waitlist gets first look.

```
CERAFICA
SYS:BROADCAST // NEW DROP

This week's firing produced [X] new vessels. Each one survived cone 10 reduction and came out with its own personality.

[FEATURED PIECE]
[PALLTH-7 — $125]
Fracture networks catch the light. Each line a fault from ancient bombardment.

[VIEW ALL NEW WORK]

—

Local pickup is always free in Long Beach. Shipping runs $8-25 depending on size.

— Simon
Cerafica // Long Beach, CA
```

---

## 9. Template: Abandoned Cart

**Subject:** Your cart is still waiting

**Preview:** [Piece Name] is holding a spot for you.

```
CERAFICA
SYS:REMINDER // CART RESERVED

Hi [First Name],

You left something behind. [Piece Name] is still available if you want it.

[CART DETAILS BOX]
Item: [Piece Name]
Price: $[XX]

[COMPLETE CHECKOUT]

— Simon
Cerafica // Long Beach, CA
```

---

## 10. Template: Post-Delivery Check-in

**Subject:** Did it arrive in one piece?

**Preview:** Let us know how [Piece Name] looks in its new home.

```
CERAFICA
SYS:CHECK_IN // DELIVERY CONFIRMATION

Hi [First Name],

Just checking in — did [Piece Name] arrive safely?

If anything's off (cracks, wrong piece, glaze not what you expected), reply here and we'll sort it out.

If it arrived intact and you love it, I'd love to see a photo in its new environment. Reply directly to this email.

[REPLY HERE]

— Simon
Cerafica // Long Beach, CA
```

---

## 11. Subject Line Patterns

### Formula
```
[System status] + [What happened]
```

Examples:
- `Your planetary vessel is secured`
- `Your vessel is on its way`
- `New kiln opening: March Drop`
- `[Piece Name] is back in stock`
- `Did it arrive in one piece?`

### Rules
- Keep under 50 characters when possible
- No ALL CAPS words
- One emoji max (preferably none)
- Front-load the benefit or status

---

## 12. Email Footer Standard

```
————————————————————————————————————————————————————

CERAFICA
SYS:ONLINE // CERAFICA v1.0 // LONG BEACH, CA

Questions? Reply to this email.
Unsubscribe: [link]
```

---

*Last updated: 2026-04-14 by Kyanite Bot*
