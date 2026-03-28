# Chemical Alias System for Vision Prompt

**Date:** 2026-03-17
**File:** `scripts/lib/caption_generator.py` — `VISION_PROMPT_TEMPLATE`

## Problem

The vision prompt currently says "glaze_type: MUST BE null. Always null. Do NOT write glaze names here." This means all chemical/geological information is lost from the analysis. The planetary series worldbuilding has to reverse-engineer compounds from color names alone.

## Solution

Replace the "never mention glazes" instruction with a **chemical alias table** that maps the 32 studio glazes to their oxide-level chemistry descriptions. The AI can reference these in `hypotheses` and `color_appearance`.

A wrong guess produces a real chemistry description (harmless). A correct guess produces accurate compounds for worldbuilding (useful).

## Changes

### 1. Vision Prompt (`caption_generator.py`)

**Remove:** The `glaze_type: MUST BE null` instruction block.

**Add:** A `GLAZE CHEMISTRY ALIASES` section grouped by oxide chemistry (~700 chars):

| Group | Glazes | Chemical Alias |
|-------|--------|---------------|
| Cobalt blues | Jensen Blue, Aegean Blue | cobalt oxide (0.5-2%) |
| Copper reduction blues | Chun Blue | copper oxide in reduction |
| Iron+cobalt | Blugr | iron + cobalt oxide blend |
| Iron reduction greens | Celadon, Ming Green, Toady, Froggy | iron oxide (1-2%) in reduction |
| Amber celadon | Amber Celadon | iron oxide (3-4%) in reduction |
| High iron browns | Tenmoku, Cosmic Brown | iron oxide (5-10%) |
| Iron+manganese | Long Beach Black, Larry's Grey | iron oxide + manganese dioxide |
| Copper reduction reds | John's Red, Pablo's Red, Iron Red | copper oxide (0.5-1%) in reduction |
| Chrome-tin pinks | Pinky, Raspberry | chrome oxide (0.5%) + tin oxide (12%) |
| Manganese purple | Shocking Purple | manganese dioxide (5-8%) + cobalt |
| Reduction luster | Honey Luster | reduction-sensitive metallic luster |
| Strontium crystal | Strontium Crystal | strontium carbonate + zinc oxide crystals |
| High soda shino | Luster Shino, Malcom's Shino | high-soda feldspar, carbon trapping |
| Opacified whites | Choinard White, Tighty Whitey | tin or zirconium opacified |
| Magnesium crawl | White Crawl | high magnesium, intentional crawling |
| Transparent clears | Lucid Clear, Tom Coleman Clear | transparent silica glass, no colorants |
| Rutile yellow | Mellow Yellow | rutile (5-10%) or iron yellow |
| Undocumented | Angel Eyes, Sun Valley | undocumented studio formulation |

**Instruction to AI:** "In hypotheses, you may reference chemistry aliases from the table above. Describe what the chemistry IS (oxide compounds), not brand names."

### 2. No changes to `generate_planetary_captions.py`

The planetary caption generator already maps colors to compounds. Chemistry aliases from vision analysis will flow naturally into worldbuilding through `color_appearance` and `hypotheses`.

### 3. No changes to `glaze.db`

No cross-referencing. The alias table is self-contained in the vision prompt.

## Budget

Current prompt: 11,901 chars. Alias table: ~700 chars. Target: ~12,600 chars (under 13.5K budget).

## Verification

1. Char count < 13,500
2. Run photo through pipeline — confirm hypotheses now use chemistry language (e.g., "iron oxide with carbon trapping" instead of "Shino")
3. No raw glaze names leak into output
