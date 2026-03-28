# Template Extraction Manifest

**Date:** 2026-03-28
**Status:** Ready for extraction
**Purpose:** Defines exactly what goes into the separate "creator-kit" template repo vs. what stays in Cerafica.

## Template Repo Contents

Files and directories that go into the clean template (no ceramics content):

### Framework Code (copy as-is)
```
instagram/
  stages/01-input/CONTEXT.md
  stages/02-planning/CONTEXT.md
  stages/03-content/CONTEXT.md
  stages/04-repurposing/CONTEXT.md
  scripts/auto_vision.py
  scripts/lib/caption_generator.py
  scripts/lib/frame_themes/          # NEW — generic theme system
  scripts/lib/geology_vocabulary.py  # Shim — loads from domain pack
  scripts/analyze-voice.py
  scripts/analyze-performance.py
  scripts/analyze-hashtags.py
  post                               # Bash wrapper
```

### Configuration (copy examples, not filled-in versions)
```
brand.yaml.example                   # NEW — template config
brand/
  identity.md                        # Empty template version
  voice-rules.md                     # Empty template version
  CONTEXT.md
inventory/
  products.json.example              # NEW — generic product schema
```

### Domain Pack Template
```
packs/
  _template/                         # NEW — generic domain pack
    vision_prompt.md
    analysis_schema.yaml
    vocabulary.py
    README.md
```

### Website (needs brand text replaced)
```
website/
  index.html                         # Replace "Cerafica" with {{BRAND_NAME}}
  shop.html                          # Replace "Cerafica" with {{BRAND_NAME}}
  about.html                         # Replace brand-specific content
  links.html                         # Replace brand-specific links
  css/                               # Copy as-is (variables.css = theming)
  js/config.js                       # NEW — brand config for website
  js/shop.js                         # Copy as-is (now reads BRAND config)
  js/main.js                         # Copy as-is
  js/nav.js                          # Copy as-is
  js/animations.js                   # Copy as-is
  data/products.json                 # Symlink to inventory/products.json
```

### Setup & Docs
```
setup/questionnaire.md               # UPDATED — generic version
CLAUDE.md                            # Needs generalized version
CONTEXT.md                           # Needs generalized version
.github/workflows/deploy-pages.yml   # Copy as-is
.env.example                         # Copy as-is
.gitignore                           # Copy as-is
```

### Tools
```
tools/feedback/
  server.py                          # Copy as-is (generic feedback system)
  pipeline.html                      # Copy as-is
```

---

## Cerafica-Only (does NOT go to template)

```
brand.yaml                           # Cerafica's filled-in config
brand/identity.md                    # Cerafica's identity (filled in)
brand/voice-rules.md                 # Cerafica's voice rules (filled in)
brand/performance-insights.md        # Cerafica's performance data
brand/dm-sales-playbook.md           # Generic enough but has Cerafica examples
brand/local-market-analysis.md       # Long Beach specific
brand/PHOTOGRAPHY_GUIDE.md           # References Planetary Frame Generator

packs/ceramics/                      # Ceramics domain pack
  vision_prompt.md
  analysis_schema.yaml
  vocabulary.py

inventory/products.json              # Actual Cerafica products (with Stripe links!)
inventory/available/                 # Product photos
inventory/sold/                      # Sold product photos
inventory/process/                   # Process photos

instagram/scripts/frame_image.py     # References PlanetaryFrameGenerator
instagram/scripts/frame_video.py     # Planetary video framing
instagram/scripts/lib/frame_generator.py  # PlanetaryFrameGenerator class
instagram/scripts/lib/video_frame_generator.py
instagram/scripts/regenerate_worldbuilding.py
instagram/scripts/regenerate_worldbuilding.mjs
instagram/data/                      # Archive data
instagram/posting-packs/             # Generated packs
instagram/reports/                   # Performance reports

ceramics-foundation/                 # Git submodule
output/framed/                       # Generated framed images

website/images/products/             # Product images and videos
docs/                                # Cerafica-specific plans

tools/feedback.db                    # Cerafica's feedback data (SECRETS: none, but private data)
```

---

## Security Checklist

Before extracting to template:
- [ ] No API keys or secrets in any template file
- [ ] No Stripe payment links in products.json.example
- [ ] No personal information (address, email) in template files
- [ ] No product photos or videos
- [ ] .env.example has placeholder values only
- [ ] brand.yaml.example has no real brand data
