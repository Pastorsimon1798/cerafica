# Photography Guide for Framed Composites

This guide covers best practices for photographing pottery that will be processed through the Planetary Frame Generator (or other frame styles).

---

## Minimum Padding Rule

**Leave 20-25% of frame width as empty space around your piece.**

On 4:5 Instagram format (1080x1350px), that's approximately 216-270px of margin.

**Why?** The frame generator needs room for:
- HUD borders and decorative elements
- Text overlays (planet name, sector, etc.)
- Space atmosphere effects (stars, nebula)
- Soft glow around the piece

### Composition Sweet Spot

```
┌────────────────────────────────┐
│        ↑ 15-20%                │  ← Top margin for HUD header
│    ┌─────────────┐             │
│ ←  │             │  → 20-25%   │  ← Side margins for corner decorations
│20% │   [PIECE]   │             │
│    │   CENTERED  │             │
│    └─────────────┘             │
│        ↓ 15-20%                │  ← Extra bottom for data footer
│   (plus space for text)        │
└────────────────────────────────┘
```

---

## Piece Size in Frame

| Fill Level | Result |
|------------|--------|
| **90%+** | Too tight - no room for HUD, looks cramped |
| **70-80%** | Sweet spot - balanced, room for effects |
| **50-60%** | Good for detailed space backgrounds |
| **<50%** | Piece looks small, too much empty space |

### How to Check

1. Take photo
2. Check if piece touches any edge of frame
3. If touching edges, step back or zoom out
4. Aim for visible background on all four sides

---

## Lighting Tips

### Best: Single Light Source from Side
- Creates defined shadows
- Easier edge detection for frame generator
- Adds depth and dimension

### Avoid: Flat Even Lighting
- Piece blends into background
- No contrast for edge detection
- Looks 2D and uninteresting

### Avoid: Harsh Backlighting
- Creates bright halo around piece
- Confuses background detection
- Causes lens flare

### Lighting Setup Example
```
    [WINDOW/LIGHT]
         ↓
    ─────────────────
    │      ↘        │
    │   ┌─────┐     │
    │   │     │ ▼   │  ← Shadow falls to opposite side
    │   │PIECE│     │
    │   │     │     │
    │   └─────┘     │
    │               │
    ─────────────────
```

---

## Background Tips

### Best Practices
| Background | Result |
|------------|--------|
| Dark piece on light background | High contrast, clean edges |
| Light piece on dark background | High contrast, dramatic |
| Solid color background | Clean, easy compositing |
| Neutral gray/tan | Works with most glazes |

### Avoid
| Background | Problem |
|------------|---------|
| Same color as piece | Piece disappears (white glaze on white wall) |
| Busy patterns | Distracting, harder to separate |
| Reflective surfaces | Glare, confusing highlights |
| Textured backgrounds | Competes with piece texture |

### Why Background Matters

The frame generator will:
1. Blur the original background
2. Composite piece onto space
3. Add soft glow around piece edges

**Better original background = better compositing result**

---

## Distance Guidelines

| Distance | Fill % | Result |
|----------|--------|--------|
| Too close | 90%+ | Cramped, no HUD room |
| Optimal | 60-70% | Balanced, room for effects |
| Too far | <50% | Piece looks small |

### Quick Distance Test
1. Hold camera at typical shooting distance
2. Piece should occupy roughly 2/3 of frame width
3. If piece fills viewfinder edge-to-edge → step back
4. If piece looks tiny in frame → move closer

---

## Aspect Ratio

### Best: Shoot in 4:5 Portrait
- Native Instagram feed format
- No cropping needed
- Full resolution preserved

### Other Ratios
| Input | Frame Generator Handling |
|-------|--------------------------|
| 4:5 portrait | Scale to fit, minimal processing |
| Taller than 4:5 | Scale to fit width, pad top/bottom with space |
| Square (1:1) | Scale to fit height, pad sides with space |
| Landscape | Scale to fit height, generous side stars |

**Tip:** If your camera supports it, set aspect ratio to 4:5 or 3:4.

---

## Quick Checklist

Before shooting, verify:

- [ ] Piece is centered in frame
- [ ] 20-25% empty space on all sides
- [ ] Single light source from side
- [ ] Background contrasts with piece
- [ ] No harsh backlight or glare
- [ ] Camera in portrait orientation
- [ ] Focus locked on piece

---

## Example Shots

### Good Example
- Piece: Brown shino vase
- Background: Off-white wall
- Lighting: Window light from left side
- Fill: ~65% of frame width
- Margins: Visible on all sides

### Bad Example
- Piece: White glazed bowl
- Background: White tabletop
- Lighting: Overhead fluorescent (flat)
- Fill: 90% (touches edges)
- Margins: None visible

---

## After Shooting

1. Review photos in camera
2. Check for edge-to-edge fills (reject these)
3. Verify lighting shows piece form
4. Transfer to Photos app "To Post" album

When ready, the frame generator will process photos automatically with the auto-post pipeline, or manually via:

```bash
python scripts/frame_image.py --test IMG_1234.JPG
```

---

## Technical Notes

### Why These Guidelines?

The Planetary Frame Generator uses PIL (Pillow) for image processing:

1. **Normalization:** Resizes to 1080x1350, fills gaps with space background
2. **Background Blur:** Gaussian blur on original background before compositing
3. **Glow Effect:** Radial gradient around piece using dominant color
4. **HUD Overlay:** Text and decorative elements in margins

Better input photos = better output with less manual intervention.
