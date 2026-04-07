# AI-Powered Instagram Content System for Ceramics

**A Creative Technology Case Study**

---

## The Problem

As a ceramicist running @cerafica_design, I was spending 3.5 hours per week on Instagram content: selecting photos, writing captions, researching hashtags, and scheduling posts. As a solo artist with inventory to sell and a brand to build, this was time I couldn't afford to lose from studio work.

## The Solution

I built an AI-powered content automation system that reduced my weekly Instagram workflow from 3.5 hours to 2 minutes.

### System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     CERAMICS INSTAGRAM AUTOMATION                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌──────────┐    ┌──────────────┐    ┌───────────────┐               │
│   │  PHOTOS  │───▶│  VISION AI   │───▶│   CAPTION     │               │
│   │  (Apple  │    │  PIPELINE    │    │  GENERATION   │               │
│   │  Photos) │    │              │    │               │               │
│   └──────────┘    └──────────────┘    └───────────────┘               │
│                         │                      │                        │
│                         ▼                      ▼                        │
│                  ┌──────────────┐    ┌───────────────┐                 │
│                  │   A/B TEST   │    │    BRAND      │                 │
│                  │   FRAMEWORK  │    │    VAULT      │                 │
│                  └──────────────┘    └───────────────┘                 │
│                         │                      │                        │
│                         ▼                      ▼                        │
│                  ┌──────────────────────────────────┐                  │
│                  │       AUTO-POST ENGINE          │                   │
│                  │    (Meta Business Suite API)    │                   │
│                  └──────────────────────────────────┘                  │
│                              │                                          │
│                              ▼                                          │
│                     ┌────────────────┐                                 │
│                     │   INSTAGRAM    │                                 │
│                     │   @cerafica    │                                 │
│                     └────────────────┘                                 │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Key Components

#### 1. Vision AI Pipeline
Two models analyze each ceramic photo simultaneously:

- **Gemini 3 Flash** (via OpenRouter) - Primary vision analysis
- **Kimi K 2.5** (via Ollama) - Secondary validation

**What they detect:**
- Piece type (bud vase, bowl, cup, sculptural form)
- Glaze type (Shino, celadon, tenmoku, ash, etc.)
- Surface qualities (crackle, gloss, matte, variegation, color pooling)
- Firing state (greenware, bisque, finished)
- Form technique (wheel-thrown, hand-built)

#### 2. A/B Testing Framework

I ran 56+ comparison tests between the two vision models to determine optimal performance:

| Metric | Gemini 3 Flash | Kimi K 2.5 |
|--------|----------------|------------|
| Piece Type Accuracy | **80%** | 20% |
| Glaze Identification | **80%** | 60% |
| Surface Quality Detection | Excellent | **Superior** |
| Caption Engagement | **80%** | 40% |

**Winner:** Gemini 3 Flash became the primary model, with Kimi used for surface quality validation.

#### 3. Caption Generation

The system generates Instagram captions in the brand voice:

- **Hook** - Scroll-stopping first line
- **Body** - Storytelling about the piece, process, or glaze chemistry
- **CTA** - Question to drive engagement

Example output:
> "There is something so honest about raw clay. 🤛
>
> These bud vases are terracotta straight from the bisque fire. No glaze, just the iron speckles showing through where the clay remembers its earth.
>
> Do you prefer the look of unglazed clay or a shiny finish?"

#### 4. Brand Vault

A persistent knowledge base that stores:
- Brand identity and positioning
- Voice patterns extracted from historical captions
- Performance insights (what content performs best)
- Hashtag library (optimized by engagement data)

#### 5. Auto-Posting Engine

Playwright automation that:
- Logs into Meta Business Suite
- Uploads photos with generated captions
- Schedules posts for optimal times (Mon 8AM, Tue 5PM, Fri 8AM)
- Handles the entire workflow autonomously

### Creative Feature: Worldbuilding Series

I extended the system for a creative series called "Glaze Exploration" where each ceramic vessel is treated as a planet:

```
┌─────────────────────────────────────────────────────────────────┐
│                     WORLDBUILDING MODE                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   Glaze Chemistry  ──────▶  Planetary Geology                  │
│   Surface Texture  ──────▶  Terrain Features                   │
│   Color Pooling    ──────▶  Ocean Composition                  │
│   Crackle Pattern  ──────▶  Tectonic Activity                  │
│                                                                 │
│   Output:                                                       │
│   "This vessel-planet has an iron-rich core that bleeds        │
│    through the crust. The atmosphere is barely breathable -    │
│    sulfur compounds give the sky a greenish tint. Oceans       │
│    of copper sulfate create the characteristic blue-green      │
│    pooling in the lowlands..."                                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

This combines my ceramics expertise with generative AI storytelling.

## Technical Stack

| Component | Technology |
|-----------|------------|
| Vision AI | Gemini 3 Flash, Kimi K 2.5 |
| API Layer | OpenRouter, Ollama |
| Automation | Playwright (Python) |
| Data Storage | SQLite, JSON |
| Integration | Apple Photos (AppleScript), Meta Business Suite |
| Hosting | Local (cron-scheduled) |

## Results

- **Time saved:** 3.5 hours/week → 2 minutes/week
- **Output generated:** 115+ AI-generated content pieces
- **A/B tests run:** 56 model comparison tests
- **Vision accuracy:** 80% piece type identification
- **Engagement:** Consistent brand voice across all content

## Code Structure

```
cerafica/
├── scripts/
│   ├── auto_vision.py         # Vision analysis pipeline
│   ├── auto-post.py           # Full automation workflow
│   ├── ab_test_vision.py      # A/B testing framework
│   ├── analyze-voice.py       # Brand voice extraction
│   ├── analyze-performance.py # Engagement analytics
│   └── lib/
│       ├── caption_generator.py   # AI caption generation
│       ├── photo_export.py        # Apple Photos integration
│       └── instagram_scheduler.py # Meta Business automation
├── brand-vault/
│   ├── identity.md            # Brand positioning
│   ├── voice-rules.md         # Extracted voice patterns
│   └── performance-insights.md # Engagement dashboard
├── output/                    # 115+ generated files
└── human-door/                # Dashboard for review
```

## What Makes This Creative Technology

1. **Domain expertise encoded** - The system understands ceramic vocabulary (Shino, celadon, tenmoku, reduction firing)
2. **Multi-model orchestration** - Two AI models work together, each with distinct strengths
3. **Creative direction** - Not just automation, but creative storytelling (worldbuilding series)
4. **Feedback loops** - Performance data feeds back into content strategy
5. **Artist-owned** - Open-source, self-hosted, data stays local

## Lessons Learned

1. **Vision AI is surprisingly good at ceramics** - 80% accuracy on vessel types without domain-specific training
2. **A/B testing reveals model biases** - Kimi sees crackle everywhere; Gemini is more conservative
3. **Brand voice can be extracted** - Analysis of 100+ captions produced usable voice patterns
4. **Human review is still needed** - The system generates drafts; final approval is manual
5. **Creative + technical = powerful** - The worldbuilding feature emerged from combining domain knowledge with AI capabilities

## Source Code

Available on GitHub: [github.com/Pastorsimon1798/cerafica]

---

*Built by Simon Gonzalez de Cruz - Creative Technologist, Ceramicist, Artist*

*@cerafica_design | Long Beach, CA*
