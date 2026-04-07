# Handoff: Session 2026-03-16

## What Was Fixed

### 1. Regenerate Caption Bug
- **File:** `human-door/pipeline.html`
- **Issue:** `testData` was undefined, should be `allData`
- **Fix:** Lines 2024, 2026 - changed `testData.results` → `allData.results`

### 2. Data Loading Crash
- **File:** `human-door/pipeline.html`
- **Issue:** `winners.reduce is not a function` - server returns object, code expected array
- **Fix:** Line 2109 - changed `winners.reduce(...)` → `winners || {}`

### 3. Empty Vision/Captions in UI
- **File:** `human-door/pipeline.html`
- **Issue:** Model name mismatch - data has `"Kimi K2.5"`, code looked for `"Kimi"`
- **Fix:** Changed `=== 'Kimi'` → `.includes('Kimi')` at lines 1538-1539, 1631-1632, 1811, 1855, 1897

### 4. No Hashtags
- **File:** `human-door/test_data.json`
- **Issue:** Caption objects lacked `hashtags` field
- **Fix:** Ran Python script to generate hashtags for all 15 results using `select_hashtags()`

### 5. Series + Idea Seeds Integration
- **File:** `human-door/pipeline.html`
- **Issue:** Idea seeds weren't incorporated into worldbuilding for photos in series
- **Fix:**
  - `generateWorldbuilding()` now accepts `ideaSeeds` parameter (line 1167)
  - `generateRichCaption()` now accepts `ideaSeeds` parameter (line 1461)
  - All 3 call sites pass seeds: lines 1821, 1867, 1913

### 6. Vision Prompt - Glaze Name Guessing (MAIN FIX)
- **File:** `scripts/lib/caption_generator.py`
- **Issue:** Prompt asked AI to guess specific glaze names like "Tom Coleman Clear over Jensen Blue" - always wrong
- **Fix:** Replaced ~70 lines of glaze-guessing instructions with:
  ```
  - glaze_type: **DO NOT GUESS SPECIFIC GLAZE NAMES.**
    Focus on surface_qualities and color_appearance fields instead.
  ```
- AI now describes WHAT IT SEES using visual taxonomy, not glaze names

### 7. Image Compression Quality
- **File:** `scripts/lib/caption_generator.py`
- **Issue:** Compression dropped to quality=15-25, destroying detail for vision
- **Fix:**
  - Increased `max_size_mb` from 4.0 → 8.0
  - Added `min_quality=50` parameter
  - Won't compress below quality 50 - returns original instead

---

## Current Pipeline

**Model:** Kimi K2.5 only (via Ollama cloud)
**Backend:** `ollama`
**Command to test:** `python3 scripts/auto-post.py --test`

---

## Other Workspaces Found

Glaze chemistry resources available at:
- `/Users/simongonzalezdecruz/Desktop/Workspaces/GlazeLab/`
- `/Users/simongonzalezdecruz/workspaces/glaze-experiments/`
- `/Users/simongonzalezdecruz/workspaces/glaze-experiments/openglaze/`

Key file: `GlazeLab/.claude/skills/ceramic-glaze-re.md` - has systematic visual taxonomy approach (base color, undertones, gloss, translucency, pooling, texture)

---

## To Verify Everything Works

```bash
cd /Users/simongonzalezdecruz/Desktop/Interpreted-Context-Methdology/workspaces/ceramics-instagram
python3 scripts/auto-post.py --test
```

Then refresh http://localhost:8766/pipeline

---

## What's Still TODO

1. **Regenerate test_data.json** with fixed vision prompt (no glaze guessing)
2. **Import glaze taxonomy** from GlazeLab into ceramics-instagram brand-vault
3. **Delete or rename** `ab_test_vision.py` - no longer needed since using Kimi only
