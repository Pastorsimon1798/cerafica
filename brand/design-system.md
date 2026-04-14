# Cerafica Design System

> Unified visual language for all Cerafica digital surfaces — website, emails, social templates, and promotional materials.
> Version: 1.0.0

---

## 1. Philosophy

Cerafica's visual identity lives at the intersection of **organic brutality** and **systematic precision**.

- **Dark-first**: The work is the light source. Backgrounds recede.
- **Monospace authority**: Code and clay are equal disciplines. JetBrains Mono signals both.
- **Generous brutality**: Big spacing, sharp edges, no decorative gradients.
- **Planetary minimalism**: Each piece is a world. The UI is the observatory.

---

## 2. Color Tokens

### Core Palette

| Token | Hex | RGB | Usage |
|-------|-----|-----|-------|
| `--bg-primary` | `#0A0A0A` | 10, 10, 10 | Page background, deepest layer |
| `--bg-card` | `#111111` | 17, 17, 17 | Cards, modals, panels |
| `--bg-elevated` | `#151515` | 21, 21, 21 | Hover states, dropdowns, inputs |
| `--bg-hover` | `#1A1A1A` | 26, 26, 26 | Active selection, focus rings |

### Neutral Scale

| Token | Hex | Usage |
|-------|-----|-------|
| `--border-subtle` | `#222222` | Dividers, inactive borders |
| `--border-default` | `#2A2A2A` | Default borders, outlines |
| `--border-hover` | `#3A3A3A` | Hover borders |
| `--fg-muted` | `#888888` | Secondary text, captions, timestamps |
| `--fg-secondary` | `#BBBBBB` | Body text, descriptions |
| `--fg-primary` | `#E8E8E8` | Headlines, primary text, labels |
| `--fg-white` | `#FFFFFF` | Emphasis, active nav, buttons |

### Accent Palette

| Token | Hex | Usage |
|-------|-----|-------|
| `--accent-cyan` | `#1EC3D2` | Primary CTA, links, active states, focus rings |
| `--accent-cyan-dim` | `#0F829B` | Secondary cyan, underlines, decorative |
| `--accent-amber` | `#FFAA00` | Warnings, badges, highlights, price tags |
| `--accent-amber-dim` | `#B37400` | Amber hover, secondary highlights |

### Usage Rules

1. **Never use pure black (`#000000`)** — It crushes shadows and looks like a dead pixel.
2. **Cyan is the only interactive color** — if it's clickable, it glows cyan.
3. **Amber is for attention, not action** — prices, alerts, "sold out", "coming soon".
4. **Text on `#0A0A0A` must be `#BBBBBB` minimum** for readability.
5. **Muted text (c888888`) only on `#0A0A0A` or `#111111`** — never on lighter surfaces.

---

## 3. Typography

### Font Family

```css
font-family: 'JetBrains Mono', 'Fira Code', 'SF Mono', Menlo, Consolas, monospace;
```

- **No serif fonts.**
- **No sans-serif fonts.**
- Monospace is the brand.

##3 Type Scale

| Level | Size | Weight | Line Height | Letter Spacing | Usage |
|-------|------|---------|-------------|----------------|-------|
| Display | `clamp(2.5rem, 6vw, 4.5rem)` | 700 | 1.05 | -0.03em | Hero headlines |
| H1 | `clamp(2rem, 4vw, 3rem)` | 600 | 1.1 | -0.02em | Page titles |
| H2 | `clamp(1.5rem, 3vw, 2.25rem)` | 600 | 1.15 | -0.02em | Section headers |
| H3 | `1.25rem` | 500 | 1.25 | -0.01em | Subsection titles |
| H4 | `1rem` | 500 | 1.3 | 0 | Card titles, labels |
| Body | `1rem` | 400 | 1.6 | 0 | Paragraphs, descriptions |
| Small | `0.875rem` | 400 | 1.5 | 0 | Captions, metadata |
| Tiny | `0.75rem` | 400 | 1.4 | 0.02em | Badges, timestamps, legal |
| Nav Link | `0.9rem` | 500 | 1 | 0.05em | Navigation (uppercase) |
| Button | `0.85rem` | 600 | 1 | 0.08em | Buttons (uppercase) |
| Footer Sys | `0.75rem` | 400 | 1.4 | 0.04em | Terminal-style footer text |

##3 Typography Rules

1. **Headlines are tight and heavy.** Negative letter-spacing is mandatory.
2. **Body text is loose.** 1.6 line-height minimum for readability.
3. **Navigation and buttons are uppercase.** Small caps via `text-transform: uppercase`.
4. **Never underline headlines.** Underlines are for links only.
5. **Terminal syntax in microcopy.** `>`, `//`, `SYS:`, `v1.0` — these are brand punctuation.

---

## 4. Spacing & Layout

### Spacing Scale

| Token | Value | Usage |
|-------|-------|-------|
| `--space-2xs` | 4px | Tight inline gaps, icon padding |
| `--space-xs` | 8px | Button padding-y, small gaps |
| `--space-sm` | 16px | Card internal padding, nav gaps |
| `--space-md` | 24px | Section internal spacing |
| `--space-lg | 32px | Component margins |
| `--space-xl` | 48px | Section breaks |
| `--space-2xl` | 64px | Major section divisions |
| `--space-3xl` | 96px | Hero/page transitions |

### Container

```css
max-width: 1200px;
padding-left: 24px;
padding-right: 24px;
margin: 0 auto;
```

On mobile (`< 640px`), padding reduces to `16px`.

##3 Grid

- **Default**: Single column, centered.
- **Product grids**: CSS Grid, `repeat(auto-fill, minmax(280px, 1fr))`, gap `32px`.
- **Two-column layouts**: `1fr 1frg`on desktop, stack on `< 768px`.

##3 Breakpoints

| Name | Width | Behavior |
|-------|-------|----------|
| Mobile | `< 640px` | Single column, reduced spacing, hamburger nav |
| Tablet | `640px - 1024px` | 2-column grids, full nav may collapse |
| Desktop | `> 1024px` | Full layout, 3-4 column grids, all nav visible |

---

## 5. Components

### Buttons

**Primary Button**
```css
background: var(--accent-cyan);
color: var(--bg-primary);
border: none;
padding: 12px 24px;
font-size: 0.85rem;
font-weight: 600;
text-transform: uppercase;
letter-spacing: 0.08em;
border-radius: 0;
```

**Ghost Button**
```css
background: transparent;
color: var(--fg-primary);
border: 1px solid var(--border-default);
padding: 12px 24px;
/* Same text treatment as primary */
```

**Button States**
- Hover: background lightens 10%, cursor pointer
- Active: scale(0.98)
- Disabled: opacity 0.4, cursor not-allowed
- Focus: 2px solid outline in `--accent-cyan`, offset 2px

### Cards

```css
background: var(--bg-card);
border: 1px solid var(--border-subtle);
padding: 24px;
border-radius: 0;
```

- No border-radius. Sharp corners only.
- Hover: border transitions to `--border-hover`.
- Optional: subtle top border in `--accent-cyan` (`border-top: 2px solid var(--accent-cyan)`).

### Forms / Inputs

```css
background: var(--bg-elevated);
color: var(--fg-primary);
border: 1px solid var(--border-default);
padding: 12px 16px;
font-family: inherit;
font-size: 1rem;
border-radius: 0;
```

- Placeholder color: `--fg-muted`
- Focus border: `--accent-cyan`
- Error border: `--accent-amber`

##3 Links

```css
color: var(--accent-cyan);
text-decoration: none;
```

- Hover: opacity 0.8
- Visited: same color (don't change on dark backgrounds)

### Badges

```css
background: var(--accent-amber);
color: var(--bg-primary);
padding: 4px 8px;
font-size: 0.7rem;
font-weight: 600;
text-transform: uppercase;
letter-spacing: 0.06em;
```

- Used for: `SOLD OUT`, `COMING SOON`, `NEW DROP`, `ONE OF ONE`

### Modal

- Background overlay: `rgba(0, 0, 0, 0.85)`
- Modal surface: `--bg-card`
- Close button: top-right, cyan on hover
- Max-width: 900px on desktop, full-bleed on mobile

---

## 6. Imagery & Media

### Product Photography

- **Background**: Neutral gray/tan or off-white. High contrast with piece.
- **Lighting**: Single side light. Defined shadows. No flat overhead fluorescence.
- **Padding**: 20-25% empty space around piece for framing/compositing.
- **Aspect ratio**: 4:5 portrait preferred. 1:1 square acceptable.

### Video

- Source: 60fpx iPhone video
- Output: 30fps with `--slowdown 1` (never 2)
- Duration: 15-30 seconds for Reels
- Hook: First 2 seconds must show transformation or result

### Icons

- Style: Stroke-based, 2px weight, no fill
- Source: Custom SVG or Feather-style line icons
- Color: inherits `--fg-primary`, hover becomes `--accent-cyan`

---

## 7. Motion & Animation

##3 Principles

1. **Motion reveals hierarchy.**
2. **Fast is friendly.** Durations: 150-300ms.
3. **Easing**: `cubic-bezier(0.4, 0, 0.2, 1` for UI, `cubic-bezier(0, 0, 0.2, 1` for entrances.

#33 Standard Transitions

| Element | Duration | Easing |
|---------|---------|--------|
| Button hover | 150ms | ease-out |
| Link hover | 150ms | ease-out |
| Card border | 200ms | ease |
| Modal open | 250ms | cubic-bezier(0, 0, 0.2, 1) |
| Nav mobile menu | 200ms | ease-in-out |
| Page fade-in | 400ms | ease-out |

#33 Scroll Behavior

- Product cards: fade-up on enter viewport (`translateY(24px)` -> `0`, opacity 0 -> 1)
- Stagger: 80ms between cards
- Threshold: trigger at 15% viewport intersection

---

## 8. Copy Patterns

##3 Navigation Labels

- Links
- Shop
- About
- Journal
- Instagram

Never: Home, Contact Us, Blog, Store.

##3 Button Labels

- ADD TO CART
- BUY NOW
- CHECKOUT
- JOIN WAITLIST
- NOTIFY ME
- VIEW AVAILABLE WORK
- READ ENTRY
- SEND

### System Signatures

Use terminal syntax in footers and microcopy:

```
SYS:ONLINE // CERAFICA v1.0 // LONG BEACH, CA
```

```
> your@email.com [JOIN]
```

```
// kiln opening: cone 10, reduction
```

#33 Error Messages

- Be direct. No apologies.
- Bad: "Oops! Something went wrong."
- Good: "Checkout failed. Please try again."
- Bad: "We're sorry, this item is unavailable."
- Good: "This piece is sold out. Join the waitlist to be first to know."

---

## 9. Responsive Behavior

### Mobile (`< 640px`)

- Nav collapses to hamburger
- Product grid -> 1 column
- Modal -> full-screen
- Footer nav -> stacked
- Hero text -> `clamp(1.75rem, 8vw, 2.5rem)`

### Tablet (`640px - 1024px`)

- Product grid -> 2 columns
- Modal -> 90% width
- Side-by-side layouts may stack

#3# Desktop (`> 1024px`)

- Full horizontal nav
- Product grid -> 3-4 columns
- Modal -> max 900px centered
- Generous whitespace preserved

---

## 10. Do Not Do

- **No rounded corners** on cards, buttons, or images (unless the image itself is a photo).
- **No gradients** as decorative backgrounds.
- **No drop shadows** on cards. Use borders instead.
- **No serif fonts.** Ever.
- **No pastel colors.** The palette is dark, cyan, and amber only.
- **No generic stock photography.** Every image must be of actual Cerafica work.

---

#3 11. File References

- Website CSS: `website/css/variables.css`, `website/css/base.css`, `website/css/components.css`
- Live site: https://cerafica.com
- API/Backend brand usage: `kyanite-landing/app.py` (email templates)

---

*Last updated: 2026-04-14 by Kyanite Bot*
