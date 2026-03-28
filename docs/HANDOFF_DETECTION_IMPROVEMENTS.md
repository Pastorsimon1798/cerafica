# Handoff: Detection Improvements (March 14, 2026)

## What Was Done

### 1. Vision Prompt Consolidation ✓
- Created single `VISION_PROMPT_TEMPLATE` at line 1010 in `caption_generator.py`
- Both Ollama and OpenRouter backends now use this single template
- Added research-backed piece type definitions (bud_vase vs vase, jar vs bowl)

### 2. Cloud Model API Fix ✓
- Cloud models (e.g., `kimi-k2.5:cloud`) need `/api/chat` endpoint, not `/api/generate`
- Code now detects `:cloud` suffix and uses correct endpoint
- Local models continue using `/api/generate`

### 3. Research Documentation ✓
- Created `brand-vault/ceramics-terminology-research.md` with official ceramics education terminology
- Sources: myartlesson.com, Ceramic Arts Network, The Spruce

### 4. Prompt Improvements ✓
- Added layered glaze detection (e.g., "Honey Luster over Jensen Blue over Tom Coleman Clear")
- Better bisque vs greenware guidance
- Research-backed piece type definitions

---

## Current Test Results (kimi-k2.5:cloud)

| Photo | piece_type | glaze_type | clay_type | Status |
|-------|------------|------------|-----------|--------|
| IMG_4782 | bowl | Celadon | stoneware | ✓ |
| IMG_4818 | piece (studio) | — | stoneware | Firing: should be bisque, not greenware |
| IMG_4898 | bud_vase | Honey Luster over Jensen Blue | stoneware | Clay: should be death_valley; Missing Tom Coleman Clear |
| IMG_4901 | bowl | Chun Blue over Malcom's Shino | death_valley | Glaze: should match IMG_4898 |

---

## Known Issues (OK for now per user)

1. **Bisque vs Greenware**: AI struggles to distinguish - both look matte/unfired
2. **3-layer glaze combos**: Detects 2 layers but sometimes misses the 3rd
3. **Clay type accuracy**: Sometimes says stoneware when it's death_valley

---

## Key Files

| File | Purpose |
|------|---------|
| `scripts/lib/caption_generator.py` | Main vision + caption logic |
| `brand-vault/ceramics-terminology-research.md` | Research-backed taxonomy |
| `memory/MEMORY.md` | Updated with new architecture notes |

---

## Next Steps (When Ready)

1. **Test with more photos** - Run full test suite with "To Post" album
2. **Video handling** - 4 videos in album fail due to size limits
3. **Posting/scheduling** - Original plan mentioned this as next phase

---

## How to Resume

```
I want to continue the detection improvement work. Read HANDOFF_DETECTION_IMPROVEMENTS.md for context, then we can:
1. Test more photos
2. Work on video handling
3. Move to posting/scheduling features
```
