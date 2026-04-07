# Copy This Prompt for New Chat

```
I need you to research and recommend AI models for a ceramics Instagram automation project.

## What I Need

1. **Vision AI Research** - Find the best model (via OpenRouter) for analyzing ceramic pottery photos. Must detect: piece type, clay body, glaze type/colors, surface texture, form characteristics, and firing evidence.

2. **Caption Writing Research** - Find the best model (via OpenRouter) for writing Instagram captions in a specific brand voice.

3. **OpenRouter Setup** - How to configure API keys and estimate costs.

## Context

Working directory: `/Users/simongonzalezdecruz/Desktop/Interpreted-Context-Methdology/workspaces/ceramics-instagram`

The project has bug-fixed code ready, but the AI analysis features are not implemented. Currently falls back to basic filename-based analysis.

## Start By

1. Read `output/RESEARCH_PROMPT.md` for full research requirements
2. Read `scripts/lib/caption_generator.py` to see current implementation
3. Read `brand-vault/voice-rules.md` for voice guidelines

## Deliverables

1. Ranked model recommendations for vision and text
2. OpenRouter setup instructions
3. Implementation plan with code changes needed
4. Cost estimates (~3 posts/week)

The date is March 13, 2026 - research the latest models available.
```

## Files Created for You

| File | Purpose |
|------|---------|
| `output/RESEARCH_PROMPT.md` | Full research requirements |
| `output/TEST_REPORT.md` | Bug testing results (for reference) |
| `output/TEST_PLAN.md` | Original test plan |

## Summary of This Session

**Bugs Fixed: 7**
- Carousel grouping now works
- Story scheduling branch added
- Video detection fixed (was detecting as photos)
- Multiple smaller fixes

**Tests Passing:**
- `--story` flag ✅
- `--reel` flag ✅
- `--carousel` flag ✅
- Video detection ✅

**Still Needs:**
- Vision AI integration (research required)
- OpenRouter API key setup
- Caption generation with real AI
