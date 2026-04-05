#!/usr/bin/env bash
#
# extract-creator-kit.sh — Extract the generic Creator-kit template from Cerafica
#
# Usage:
#   ./extract-creator-kit.sh [TARGET_DIR]
#
# Defaults to ../creator-kit if no target is given.
# The target directory will be initialized as a fresh git repo.
#
set -euo pipefail

TARGET="${1:-../creator-kit}"

if [ -d "$TARGET/.git" ]; then
  echo "Error: $TARGET already has a .git directory."
  echo "Remove it first or choose a different target."
  exit 1
fi

CERAFICA="$(cd "$(dirname "$0")" && pwd)"
echo "Source:  $CERAFICA"
echo "Target:  $TARGET"
echo ""

mkdir -p "$TARGET"

# ─── Helper ──────────────────────────────────────────────────────────────────

copy_file() {
  local src="$1" dst="$2"
  mkdir -p "$(dirname "$TARGET/$dst")"
  cp "$CERAFICA/$src" "$TARGET/$dst"
}

copy_dir() {
  local src="$1" dst="${2:-$1}"
  mkdir -p "$TARGET/$dst"
  cp -r "$CERAFICA/$src/." "$TARGET/$dst/"
}

touch_gitkeep() {
  mkdir -p "$TARGET/$1"
  touch "$TARGET/$1/.gitkeep"
}

# ─── Framework code ─────────────────────────────────────────────────────────

echo "Copying framework code..."

# Instagram pipeline scripts
copy_file instagram/scripts/auto_vision.py          instagram/scripts/auto_vision.py
copy_file instagram/scripts/analyze-voice.py         instagram/scripts/analyze-voice.py
copy_file instagram/scripts/analyze-performance.py   instagram/scripts/analyze-performance.py
copy_file instagram/scripts/analyze-hashtags.py      instagram/scripts/analyze-hashtags.py
copy_file instagram/post                             instagram/post

# Core library
copy_file instagram/scripts/lib/caption_generator.py    instagram/scripts/lib/caption_generator.py
copy_file instagram/scripts/lib/data_loader.py          instagram/scripts/lib/data_loader.py
copy_file instagram/scripts/lib/geology_vocabulary.py   instagram/scripts/lib/geology_vocabulary.py
copy_file instagram/scripts/lib/instagram_scheduler.py  instagram/scripts/lib/instagram_scheduler.py
copy_file instagram/scripts/lib/instaloader_utils.py    instagram/scripts/lib/instaloader_utils.py
copy_file instagram/scripts/lib/photo_export.py         instagram/scripts/lib/photo_export.py
copy_file instagram/scripts/lib/sound_design.py         instagram/scripts/lib/sound_design.py

# Frame themes
copy_dir instagram/scripts/lib/frame_themes

# Pipeline stage context docs
copy_file instagram/stages/01-input/CONTEXT.md              instagram/stages/01-input/CONTEXT.md
copy_file instagram/stages/02-planning/CONTEXT.md            instagram/stages/02-planning/CONTEXT.md
copy_file instagram/stages/03-content/CONTEXT.md             instagram/stages/03-content/CONTEXT.md
copy_file instagram/stages/04-repurposing/CONTEXT.md         instagram/stages/04-repurposing/CONTEXT.md

# Stage reference docs
copy_dir instagram/stages/02-planning/references
copy_dir instagram/stages/03-content/references
copy_dir instagram/stages/04-repurposing/references

# ─── Configuration templates ────────────────────────────────────────────────

echo "Copying configuration templates..."

copy_file brand.yaml.example                brand.yaml.example
copy_file inventory/products.json.example   inventory/products.json.example

# ─── Domain pack template ───────────────────────────────────────────────────

echo "Copying domain pack template..."
copy_dir packs/_template

# ─── Website ────────────────────────────────────────────────────────────────

echo "Copying website..."

for f in index.html shop.html about.html links.html; do
  copy_file "website/$f" "website/$f"
done

copy_dir website/css
copy_dir website/js

# Symlink products.json → inventory example
mkdir -p "$TARGET/website/data"
ln -sf ../../inventory/products.json.example "$TARGET/website/data/products.json"

# ─── Infra / setup ──────────────────────────────────────────────────────────

echo "Copying infra files..."

copy_file .github/workflows/deploy-pages.yml  .github/workflows/deploy-pages.yml
copy_file setup/questionnaire.md               setup/questionnaire.md

# ─── Tools ───────────────────────────────────────────────────────────────────

echo "Copying tools..."
copy_file tools/feedback/server.py       tools/feedback/server.py
copy_file tools/feedback/pipeline.html   tools/feedback/pipeline.html

# ─── Shared resources ───────────────────────────────────────────────────────

echo "Copying shared resources..."
copy_file shared/hashtag-library.md  shared/hashtag-library.md

# ─── Empty directories ──────────────────────────────────────────────────────

touch_gitkeep instagram/data
touch_gitkeep instagram/posting-packs
touch_gitkeep instagram/reports
touch_gitkeep instagram/logs
touch_gitkeep docs/plans
touch_gitkeep output/framed
touch_gitkeep website/images/products
touch_gitkeep website/img

# ─── Generated files (brand templates, docs) ────────────────────────────────

echo "Generating template files..."

mkdir -p "$TARGET/brand"

# Brand identity template
cat > "$TARGET/brand/identity.md" << 'BRAND_EOF'
# Brand Identity

## Who We Are
<!-- Describe your brand in 2-3 sentences -->

## Aesthetic
<!-- What does your visual style look like? Colors, textures, mood. -->

## Goals
1. Sell existing inventory
2. Build authentic audience
3. Establish presence for future work
BRAND_EOF

# Brand voice template
cat > "$TARGET/brand/voice-rules.md" << 'VOICE_EOF'
# Voice Rules

## Tone
<!-- How does your brand sound? (e.g., warm, professional, playful, expert) -->

## Do
- Be authentic
- Share your process
- Use your natural voice

## Don't
- Sound corporate
- Over-polish everything
- Fake enthusiasm
VOICE_EOF

# .env.example (no real keys)
cat > "$TARGET/.env.example" << 'ENV_EOF'
# Stripe Configuration
# Get your secret key from: https://dashboard.stripe.com/apikeys
# IMPORTANT: Never commit the real .env file to git!
STRIPE_SECRET_KEY=sk_test_...

# Your website domain
SITE_DOMAIN=https://yourdomain.com

# Optional: Stripe Webhook Secret
# STRIPE_WEBHOOK_SECRET=whsec_...

# Optional: OpenRouter API Key (for AI caption generation fallback)
# OPENROUTER_API_KEY=sk-or-...
ENV_EOF

# .gitignore
cat > "$TARGET/.gitignore" << 'GIT_EOF'
# Environment variables (contains API keys)
.env

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
.venv/

# macOS
.DS_Store

# IDE
.idea/
.vscode/
*.swp
*.swo

# Instagram reports (generated)
instagram/reports/

# Shared framed output (generated media)
output/framed/

# Database files
*.db
*.sqlite
*.sqlite3

# Browser sessions (contains auth cookies)
instagram/data/browser_session/

# Playwright MCP logs
.playwright-mcp/

# Claude Code state
.claude/

# Photo assets (track READMEs only)
inventory/available/*
!inventory/available/README.md
inventory/process/*
!inventory/process/README.md
inventory/sold/*
!inventory/sold/README.md

# Instagram test exports
instagram/test_export/
instagram/ab_test_photos/
instagram/vision_exports/

# Instagram logs
instagram/logs/

# Instagram archive media
instagram/data/archive/media/

# Product video backups (duplicates, not needed)
website/images/products-backup/

# Source videos (large, keep locally only)
instagram/source/
instagram/stages/01-input/output/*.MOV
instagram/stages/01-input/output/*.mov

# Script output (generated videos, duplicates of website)
instagram/scripts/output/

# Debug screenshots
website/shop-screenshot.png
website/images/Screenshot*

# Local Netlify folder
.netlify
node_modules/
.gstack/
GIT_EOF

# CLAUDE.md — generic workspace guide
cat > "$TARGET/CLAUDE.md" << 'CLAUDE_EOF'
# Creator Kit — Master Workspace

Manage your brand across all channels: Instagram, website, and internal tooling.

## Getting Started

1. Copy `brand.yaml.example` → `brand.yaml` and fill in your details
2. Copy `inventory/products.json.example` → `inventory/products.json`
3. Choose or create a domain pack in `packs/`
4. Fill in `brand/identity.md` and `brand/voice-rules.md`
5. Update `website/js/config.js` with your brand info
6. Run the Instagram pipeline stages in order

## Folder Map

```
├── brand.yaml.example           # Copy to brand.yaml, fill in your details
├── brand/                       # Brand identity and voice
├── inventory/                   # Product photos and data
├── packs/                       # Domain packs (product-type knowledge)
│   └── _template/               # Starting point for new domains
├── instagram/                   # Instagram content pipeline
│   ├── scripts/                 # Python scripts + lib/
│   └── stages/                  # 01-input → 04-repurposing
├── website/                     # E-commerce site
├── tools/                       # Feedback pipeline
└── setup/                       # Onboarding questionnaire
```

## Instagram Pipeline

| Stage | Purpose |
|-------|---------|
| `instagram/stages/01-input` | Gather photos and videos |
| `instagram/stages/02-planning` | Create content calendar |
| `instagram/stages/03-content` | Write captions |
| `instagram/stages/04-repurposing` | Stories and reels ideas |

## Status

Type `status` to see pipeline completion across all stages.

## Domain Packs

Domain packs teach the pipeline about your product type. See `packs/_template/README.md`.

Each pack contains:
- `vision_prompt.md` — How AI analyzes your product photos
- `analysis_schema.yaml` — Domain-specific data fields
- `vocabulary.py` — Descriptive language for your product type
CLAUDE_EOF

# README.md
cat > "$TARGET/README.md" << 'README_EOF'
# Creator Kit

A generalized content pipeline for creators and sellers. Manage your Instagram content, e-commerce website, and brand — all from one workspace powered by Claude Code.

## What It Does

- **4-stage Instagram pipeline**: Input → Planning → Content → Repurposing
- **AI-powered photo analysis**: Vision model analyzes your product photos
- **Caption generation**: Writing model creates on-brand captions
- **E-commerce website**: Ready-to-deploy shop with Stripe checkout
- **Domain packs**: Pluggable product-type knowledge (ceramics, jewelry, vintage, etc.)

## Quick Start

```bash
# 1. Configure your brand
cp brand.yaml.example brand.yaml
# Edit brand.yaml with your details

# 2. Set up your domain pack (or use the template)
cp -r packs/_template packs/your-domain

# 3. Add your products
cp inventory/products.json.example inventory/products.json

# 4. Run the pipeline
# Follow instagram/stages/01-input/CONTEXT.md to start
```

## Architecture

```
Framework (generic pipeline code)
    ↓ reads
Configuration (brand.yaml)
    ↓ loads
Domain Pack (product-type knowledge)
```

## Requirements

- Python 3.9+
- Claude Code CLI
- Optional: Stripe account (for e-commerce)
- Optional: OpenRouter API key (for AI features)
README_EOF

# ─── Scrub personal data ────────────────────────────────────────────────────

echo "Scrubbing personal data..."

# Replace any Cerafica-specific references in copied framework files
# Order matters: specific patterns before general ones
find "$TARGET" -type f \( -name "*.py" -o -name "*.js" -o -name "*.html" -o -name "*.md" -o -name "*.yaml" -o -name "*.css" \) | while read -r file; do
  [[ "$file" == *".git/"* ]] && continue

  sed -i \
    -e 's/simon@cerafica\.com/your@email.com/g' \
    -e 's/simon@[^ "]*\.com/your@email.com/g' \
    -e 's/cerafica-checkout\.netlify\.app/your-checkout-url.netlify.app/g' \
    -e 's/cerafica\.etsy\.com/yourshop.etsy.com/g' \
    -e 's/cerafica\.com/yourdomain.com/g' \
    -e 's/@cerafica_design/@yourbrand/g' \
    -e 's/@clayonfirst/@yourbrand/g' \
    -e 's/cerafica_cart/creator_cart/g' \
    -e 's/cerafica_media/media/g' \
    -e 's/cerafica_archive/archive/g' \
    -e 's/CERAFICA-[0-9]*/BRAND-001/g' \
    -e 's/CERAFICA/YOUR BRAND/g' \
    -e 's/Cerafica/Your Brand/g' \
    -e 's/cerafica/your-brand/g' \
    -e 's/LONG BEACH, CA/YOUR CITY/g' \
    -e 's/Long Beach, CA/Your City/g' \
    -e 's/LONG BEACH/YOUR CITY/g' \
    -e 's/Long Beach/Your City/g' \
    -e 's/mailto:simon@[^"]*"/mailto:your@email.com"/g' \
    -e 's/email simon@[^ <]*/email your@email.com/g' \
    "$file"
done

# Extra: replace the about.html brand etymology paragraph with a placeholder
if [ -f "$TARGET/website/about.html" ]; then
  sed -i \
    -e 's/Cerámica + Gráfica + Facere + Calculare\.[^<]*/Your brand story goes here./g' \
    -e 's/Four words, four roots\.[^<]*//g' \
    "$TARGET/website/about.html"
fi

# Extra: clean caption_generator.py brand etymology extraction
if [ -f "$TARGET/instagram/scripts/lib/caption_generator.py" ]; then
  sed -i \
    -e 's/Extract CERAFICA etymology/Extract brand etymology/g' \
    -e "s/CERAFICA = /BRAND = /g" \
    "$TARGET/instagram/scripts/lib/caption_generator.py"
fi

# ─── Verify clean ───────────────────────────────────────────────────────────

echo ""
echo "Running security scan..."
LEAKS=$(grep -ri "cerafica\|@clayonfirst\|simon@\|pastorsimon" "$TARGET" \
  --include="*.py" --include="*.js" --include="*.html" --include="*.md" \
  --include="*.yaml" --include="*.css" --include="*.json" 2>/dev/null || true)

if [ -n "$LEAKS" ]; then
  echo "WARNING: Found potential personal data leaks:"
  echo "$LEAKS"
  echo ""
  echo "Review and fix before publishing."
else
  echo "Clean — no personal data found."
fi

# ─── Init git ────────────────────────────────────────────────────────────────

echo ""
echo "Initializing git repo..."
cd "$TARGET"
git init -b main
git add -A
git -c commit.gpgsign=false commit -m "Initial creator-kit: generalized Instagram content pipeline

Extracted from a working ceramics pipeline into a product-agnostic
framework for any creator/seller. Includes 4-stage Instagram pipeline,
domain pack system, frame themes, brand.yaml config, and e-commerce
website template."

echo ""
echo "═══════════════════════════════════════════════════"
echo "  Creator Kit extracted to: $TARGET"
echo "═══════════════════════════════════════════════════"
echo ""
echo "Next steps:"
echo "  cd $TARGET"
echo "  git remote add origin https://github.com/YOU/Creator-kit.git"
echo "  git push -u origin main"
echo ""
