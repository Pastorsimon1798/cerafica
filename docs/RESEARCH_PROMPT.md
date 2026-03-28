# Research Prompt: Vision AI & Caption Generation for Ceramics Instagram

## Context

You are working on `ceramics-instagram`, an automated Instagram posting system for a ceramic artist. The system needs two AI capabilities:

1. **Vision AI** - Analyze ceramic photos/videos to detect:
   - Piece type (bowl, mug, vase, plate, sculpture, etc.)
   - Clay body color (white stoneware, brown stoneware, porcelain, etc.)
   - Glaze type (matte, glossy, crystalline, speckled, etc.)
   - Glaze colors (primary and secondary)
   - Surface texture (smooth, rough, carved, faceted)
   - Form characteristics (organic, geometric, symmetrical, asymmetrical)
   - Making process indicators (wheel-thrown, hand-built, slip-cast)
   - Firing evidence (reduction, oxidation, wood-fired, raku)
   - Any special features (handles, feet, lids, spouts)
   - Overall aesthetic/mood

2. **Caption Writing AI** - Generate Instagram captions that:
   - Match the artist's voice (warm, authentic, process-focused)
   - Include relevant details from vision analysis
   - Have appropriate hooks for engagement
   - Include strategic hashtags
   - Have CTAs when appropriate

## Research Questions

### Question 1: Best Vision Models (March 2026)

Research and compare the top vision-capable models available via OpenRouter:

**Candidates to investigate:**
- GPT-4 Vision / GPT-4o
- Claude 3.5/4 Sonnet/Opus with vision
- Gemini 2.0 Flash / Pro Vision
- Llama 3.2 Vision
- Qwen2-VL
- Molmo
- Pixtral

**Criteria to evaluate:**
1. **Ceramic detail detection** - Can it identify subtle glaze textures, clay bodies?
2. **Color accuracy** - Can it distinguish between similar earth tones?
3. **Form recognition** - Can it identify pottery forms and their characteristics?
4. **Price** - Cost per image analysis
5. **Speed** - Latency for image analysis
6. **Context window** - Can it handle multiple images (for carousels)?

**Output needed:**
- Ranked list with scores per criteria
- Recommended model for ceramic image analysis
- Fallback model (cheaper option)

### Question 2: Best Caption Generation Models (March 2026)

Research the best text generation models for creative writing:

**Candidates to investigate:**
- GPT-4o / GPT-4o-mini
- Claude 3.5/4 Sonnet
- Gemini 2.0 Flash
- Llama 3.3 70B
- Mistral models
- DeepSeek V3

**Criteria to evaluate:**
1. **Creative writing quality** - Natural, engaging captions
2. **Voice consistency** - Can match a specific brand voice
3. **Instagram optimization** - Understanding of platform conventions
4. **Price** - Cost per generation
5. **Speed** - Latency for caption generation
6. **Instruction following** - Can follow complex voice rules

**Output needed:**
- Ranked list with scores per criteria
- Recommended model for caption generation
- Fallback model (cheaper option)

### Question 3: OpenRouter Configuration

1. How to set up OpenRouter API key in the project
2. Best practices for API key management
3. Rate limits and quotas
4. Cost estimation for the workflow:
   - ~3 photos per week
   - Each photo: 1 vision analysis + 1 caption generation
   - Monthly cost projection

### Question 4: Integration Architecture

Current code structure:
```
scripts/lib/caption_generator.py
├── analyze_photo() - Currently uses basic filename analysis
├── analyze_video() - Currently uses basic filename analysis
└── generate_caption() - Currently uses templates

scripts/lib/photo_export.py
└── get_media_from_album() - Gets media metadata
```

How should we integrate:
1. Where does vision AI call happen? (in analyze_photo or separate function?)
2. How do we pass vision analysis to caption generation?
3. Should we cache vision results to avoid re-analyzing?
4. How do we handle API failures gracefully?

## Current State

The project has:
- `OPENROUTER_API_KEY` environment variable (not set)
- `analyze_photo_basic()` - falls back when AI not available
- `analyze_video_basic()` - falls back when AI not available
- `generate_caption()` - has template fallback

The code already checks for `use_ai=True` but the AI analysis is not implemented.

## Desired Outcome

After research, provide:

1. **Model Recommendations Document:**
   ```markdown
   # AI Model Recommendations for Ceramics Instagram

   ## Vision Analysis
   - **Primary:** [Model] - $X/image
   - **Fallback:** [Model] - $Y/image
   - **Why:** [Reasoning]

   ## Caption Generation
   - **Primary:** [Model] - $X/1K tokens
   - **Fallback:** [Model] - $Y/1K tokens
   - **Why:** [Reasoning]

   ## Estimated Monthly Cost
   - Photos: X/week * $Y = $Z/week
   - Total: $XX/month
   ```

2. **Implementation Plan:**
   - Which files to modify
   - New functions needed
   - Configuration changes
   - Testing approach

3. **OpenRouter Setup Instructions:**
   - How to get API key
   - Where to configure it
   - Environment setup

## Constraints

- Budget-conscious (this is a personal project)
- Prefer models that are good at pottery/ceramic details
- Need both Chinese and English support for future expansion
- Must have good error handling for API failures

## Files to Reference

Read these files to understand current implementation:
- `scripts/lib/caption_generator.py` - Current analysis and generation logic
- `CLAUDE.md` - Project context
- `brand-vault/voice-rules.md` - Voice guidelines for captions
