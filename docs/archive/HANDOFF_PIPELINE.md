# HANDOFF: Two-Stage Vision + Caption Pipeline

## What We're Building

A two-stage A/B pipeline for ceramics Instagram captions:

```
STAGE 1: AUTO-VISION (runs when photos added to "To Post")
    ↓
    Gemini + Kimi both analyze → Store to DB
    ↓
STAGE 2: HUMAN REVIEW (dashboard)
    ↓
    Add idea seeds, mark series, creative direction
    Click "Generate Captions"
    ↓
STAGE 3: CAPTION + WORLDBUILDING (both models compete)
    ↓
    User picks winner
```

## Current State

### ✅ Built

1. **`scripts/auto_vision.py`** - Stage 1 runner
   - Connects to both Gemini (OpenRouter) and Kimi (Ollama)
   - Scans "To Post" album
   - `--watch` mode for continuous monitoring
   - Database initialization

2. **Database schema** - Added to `human-door/feedback.db`:
   - `photos` - tracks what's been analyzed
   - `vision_results` - per-model analysis (piece_type, glaze, colors, etc.)
   - `idea_seeds` - user creative associations
   - `creative_direction` - per-photo guidance
   - `series` / `series_pieces` - worldbuilding groups
   - `caption_results` - per-model captions with winner tracking

3. **Dashboard** - `human-door/pipeline.html`
   - Series section with create/add UI
   - Idea seeds input per photo
   - Worldbuilding display (planet names, captions)
   - A/B vision and caption comparison

### 🔧 Broken / Needs Fixing

1. **Vision result saving** - Error: `'"piece_type"'`
   - Location: `save_vision_result()` in `auto_vision.py` line ~250
   - Issue: PhotoAnalysis object attributes not being accessed correctly
   - The vision API calls work, but parsing/saving fails

2. **API endpoints** - Need to add to `server.py`:
   - `GET /api/pipeline/photos` - list analyzed photos
   - `GET /api/pipeline/vision/{photo_id}` - get vision results
   - `POST /api/pipeline/seeds` - add idea seed
   - `POST /api/pipeline/direction` - add creative direction
   - `POST /api/pipeline/series/add` - add photo to series
   - `POST /api/pipeline/generate` - trigger caption generation
   - `GET /api/pipeline/captions/{photo_id}` - get caption results

3. **Caption generation with series context** - Need to modify:
   - `caption_generator.py` - add `series_context` parameter
   - Pass worldbuilding prompt when piece is in a series

## Series: Glaze Exploration

User created a series called "Glaze Exploration Series":
- Concept: Each vessel is a planet, glaze chemistry = geology
- 3 pieces already tagged: IMG_4759, IMG_4908, IMG_4898
- Worldbuilding should include: atmosphere, breathability, ocean composition, life forms, visitor experience

## Model Configuration

```python
MODEL_A = {
    "backend": "openrouter",
    "vision_model": "google/gemini-3-flash-preview",
    "name": "Gemini"
}

MODEL_B = {
    "backend": "ollama",
    "vision_model": "kimi-k2.5:cloud",
    "name": "Kimi"
}
```

## Files Modified/Created

| File | Purpose |
|------|---------|
| `scripts/auto_vision.py` | Stage 1 auto-runner (NEW) |
| `human-door/server.py` | Added series API endpoints |
| `human-door/pipeline.html` | Unified dashboard with series UI |
| `human-door/feedback.db` | New tables for pipeline |

## Next Steps (in order)

1. Fix `save_vision_result()` in auto_vision.py - PhotoAnalysis attribute access
2. Run `python3 scripts/auto_vision.py` successfully
3. Add pipeline API endpoints to server.py
4. Update dashboard to call new endpoints
5. Add caption generation with series context
6. Test full flow: photo → vision → review → caption

## Key Code Locations

- Vision prompt template: `scripts/lib/caption_generator.py` line ~1094 `VISION_PROMPT_TEMPLATE`
- Caption generation: `scripts/lib/caption_generator.py` `generate_caption_with_ai()`
- Photo export: `scripts/lib/photo_export.py` `get_media_from_album()`, `export_media_by_index()`
- Server: `human-door/server.py`
- Dashboard: `human-door/pipeline.html`

## User's Vision for Worldbuilding

From their idea seed on IMG_4908:
> "The surface of every vessel is like the surface of a planet. We need to come up with a full story about how the visual features are correlated to terrain and geology. The colors, the craters, and also the actual glaze chemistry into the geologic composition. I want to know what life is like. What does it feel like to live there? Do you need a suit? Can you breathe? What are the oceans made of? Where do the crazy colors come from - toxic chemicals? bioluminescence?"

## Resume Prompt

Copy/paste this into a fresh session:

```
Continue the two-stage pipeline work from HANDOFF_PIPELINE.md.

Current issue: auto_vision.py runs but fails saving vision results with error: '"piece_type"'

Fix that first, then run it to verify, then continue with API endpoints.
```
