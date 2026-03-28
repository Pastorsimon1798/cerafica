# Ceramics Terminology Research

> Research-backed vocabulary from academic and industry sources for accurate AI detection.

## Sources

1. **myartlesson.com** - "Anatomy of a Clay Vessel" (education source)
2. **The Spruce** - "19 Types of Vases" (industry reference)
3. **Gotheborg.com** - "Names of pottery parts and shapes" (historical reference)
4. **Ceramic Arts Network** - Glossary of Pottery Terms

---

## Vessel Anatomy (Education Standard)

From myartlesson.com - standard vocabulary taught in ceramics courses:

| Term | Definition |
|------|------------|
| **Mouth** | Top opening of a round ware such as a bowl, jar or vase |
| **Lip** | The rim or outside edge of the mouth |
| **Neck** | The narrow part of the vessel between the shoulder and lip |
| **Shoulder** | Outward curve of a vase under the neck or mouth |
| **Body** | The main, usually largest part of a vessel, part that holds the vessel's contents |
| **Foot** | The bottom projection of the vessel upon which it stands |
| **Waist** | Decorative inward curve on the body |
| **Handle** | A projection by which a vessel is held or carried |

---

## Vessel Forms (Research-Backed)

### Bud Vase vs Vase (Critical Distinction)

**Bud Vase** (from The Spruce):
> "One of the smallest types of vases, a bud vase is designed to hold a **single flower stem**, such as a bud stem, hence its name."

**Key Characteristics:**
- **Purpose**: Single flower stem (not arrangements)
- **Size**: Smallest vase category
- **Neck**: Typically narrow to hold one stem upright
- **Height**: Usually shorter than standard vases (often under 6-8")
- **Use case**: Nightstand, desk, bookshelf (small spaces)

**Vase** (Standard):
- **Purpose**: Multiple flowers/arrangements
- **Size**: Larger than bud vases
- **Opening**: Wider to accommodate multiple stems
- **Height**: 6"+ typically

### Jar vs Bowl

**Jar** (from Gotheborg):
> "Bowl with constricted lip opening"

**Key Characteristics:**
- Opening is **narrower than the body**
- Often has lid-seating rim (even without lid present)
- Storage-oriented form
- The constriction at the lip is the defining feature

**Bowl**:
> "Low vessel with big opening"

- Opening is **wider than or equal to body width**
- Depth is less than width
- Open, accessible form

### Other Forms (Gotheborg)

| Form | Definition |
|------|------------|
| **Beaker** | Trumpet-shaped vase, no handle/spout |
| **Bottle** | Vase with spheroidal body, long neck, narrow mouth |
| **Pot** | Round, deep vessel; often with handle |
| **Saucer** | Original plate form - always saucer-shaped |
| **Basket** | Bowl with a handle across the top |
| **Effigy** | Pottery with human or animal shape |

---

## Body Profiles (Ceramics Education)

Standard anatomical terms for vessel shapes:

| Profile | Description |
|---------|-------------|
| **Cylindrical** | Straight parallel sides |
| **Spherical** | Ball-shaped |
| **Ovoid** | Egg-shaped |
| **Conical** | Tapering to point |
| **Bell-shaped** | Flared at bottom, narrow at top |
| **Shouldered** | Distinct shoulder where body curves outward |
| **Necked** | Has a narrow neck below rim |
| **Waisted** | Narrow in middle (hourglass) |
| **Bulbous** | Round, swollen body |
| **Elongated** | Stretched tall |
| **Squat** | Short and wide |

---

## Rim/Lip Treatments

| Term | Description |
|------|-------------|
| **Flared** | Widens at rim |
| **Tapered** | Narrows gradually |
| **Rolled** | Thickened rolled rim |
| **Rounded** | Soft rounded edge |
| **Squared** | Sharp 90-degree edge |

---

## Foot/Base Types

| Term | Description |
|------|-------------|
| **Footed** | Has distinct foot ring |
| **Trimmed** | Trimmed foot (done at leather-hard stage) |
| **Flat base** | Sits flat without foot ring |

---

## Detection Guidance for AI

### Bud Vase vs Vase Decision Tree

```
Is opening narrow (holds 1-2 stems)?
├── Yes → Is height < 6-8"?
│   ├── Yes → BUD_VASE
│   └── No → Is body proportionally small?
│       ├── Yes → BUD_VASE
│       └── No → VASE (narrow neck variety)
└── No → VASE
```

### Jar vs Bowl Decision Tree

```
Is the opening narrower than the widest part of the body?
├── Yes → JAR (constricted lip)
└── No → BOWL (open form)
```

---

## Implementation Notes

These definitions should be used in:
1. `VISION_PROMPT_TEMPLATE` - piece_type detection
2. Caption generation - accurate form descriptions
3. Hashtag selection - form-specific tags

---

*Research completed: March 14, 2026*
