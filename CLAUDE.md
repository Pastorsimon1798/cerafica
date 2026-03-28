# Cerafica — Master Workspace

Manage the Cerafica ceramics brand across all channels: Instagram, website, and internal tooling.

## gstack

Use the `/browse` skill from gstack for all web browsing tasks. Never use `mcp__claude-in-chrome__*` tools.

Available skills:
/office-hours, /plan-ceo-review, /plan-eng-review, /plan-design-review, /design-consultation, /review, /ship, /land-and-deploy, /canary, /benchmark, /browse, /qa, /qa-only, /design-review, /setup-browser-cookies, /setup-deploy, /retro, /investigate, /document-release, /codex, /cso, /autoplan, /careful, /freeze, /guard, /unfreeze, /gstack-upgrade

If gstack skills aren't working, run: `cd .claude/skills/gstack && ./setup` to build the binary and register skills.

## Folder Map

```
cerafica/
├── CLAUDE.md                    # Master routing table (you are here)
├── CONTEXT.md                   # Top-level task router
├── .gitignore / .env / .env.example
├── .github/workflows/           # deploy-pages.yml
├── ceramics-foundation/         # Git submodule (legacy content)
│
├── brand/                       # SHARED — brand identity
│   ├── identity.md              # Who you are, aesthetic, goals
│   ├── voice-rules.md           # How you sound
│   ├── performance-insights.md  # Engagement dashboard
│   ├── dm-sales-playbook.md     # DM automation & sales
│   ├── local-market-analysis.md # Competitors & opportunities
│   ├── PHOTOGRAPHY_GUIDE.md     # Photo guidelines
│   └── CONTEXT.md               # Brand vault routing
│
├── inventory/                   # SHARED — product photos & data
│   ├── available/               # Photos of available pieces
│   ├── sold/                    # Photos of sold pieces
│   ├── process/                 # Process photos
│   └── products.json            # Single source of truth
│
├── shared/                      # SHARED resources
│   └── hashtag-library.md
│
├── output/                      # SHARED — generated media
│   └── framed/                  # Sci-fi framed images
│
├── instagram/                   # CHANNEL — Instagram operations
│   ├── scripts/                 # All Python scripts + lib/
│   ├── stages/                  # 01-input through 04-repurposing
│   ├── data/                    # Archive, sync data
│   ├── posting-packs/           # Generated posting packs
│   ├── reports/                 # Reports & results JSON
│   ├── logs/                    # Auto-post logs
│   └── post                     # Bash wrapper script
│
├── website/                     # CHANNEL — e-commerce site
│   ├── index.html, shop.html, about.html, links.html
│   ├── stripe/checkout.html
│   ├── css/, js/, images/, img/
│   ├── data/products.json       # → symlink to ../../inventory/products.json
│   └── CNAME, robots.txt, sitemap.xml
│
├── tools/                       # INTERNAL — feedback & tooling
│   ├── feedback/                # server.py, pipeline.html
│   └── feedback.db
│
├── docs/                        # Plans, research, handoffs
│   ├── plans/
│   └── screenshots/
│
├── setup/                       # Onboarding
│   └── questionnaire.md
│
└── tests/                       # Python tests
```

## Triggers

| Keyword | Action |
|---------|--------|
| `setup` | Run onboarding -- configure brand identity and voice |
| `status` | Show pipeline completion for all Instagram stages |

### How `status` works

Scan `instagram/stages/*/output/` folders. For each stage, if the output folder contains files (other than .gitkeep), the stage is COMPLETE. Otherwise PENDING. Render:

```
Pipeline Status: Instagram

  [01-input]  -->  [02-planning]  -->  [03-content]  -->  [04-repurposing]
     STATUS          STATUS              STATUS              STATUS
```

## Routing

| Task | Go To |
|------|-------|
| Set up brand identity | `setup/questionnaire.md` |
| **Instagram** | |
| Collect this week's assets | `instagram/stages/01-input/CONTEXT.md` |
| Plan weekly content | `instagram/stages/02-planning/CONTEXT.md` |
| Write captions | `instagram/stages/03-content/CONTEXT.md` |
| Create stories/reels | `instagram/stages/04-repurposing/CONTEXT.md` |
| Post content | `./instagram/post` |
| Extract Instagram archive | `instagram/scripts/extract-archive.py` |
| Sync weekly posts | `instagram/scripts/sync-weekly.py` |
| Analyze voice patterns | `instagram/scripts/analyze-voice.py` |
| Optimize hashtags | `instagram/scripts/analyze-hashtags.py` |
| Generate insights | `instagram/scripts/analyze-performance.py` |
| **Brand** | |
| Review brand identity | `brand/identity.md` |
| Check voice guidelines | `brand/voice-rules.md` |
| See performance insights | `brand/performance-insights.md` |
| Set up DM sales | `brand/dm-sales-playbook.md` |
| Local market research | `brand/local-market-analysis.md` |
| **Website** | |
| Edit website pages | `website/` |
| Update product data | `inventory/products.json` |
| **Tools** | |
| Feedback pipeline | `tools/feedback/` |

## Weekly Workflow

1. **Monday/Tuesday**: Run `instagram/stages/01-input` to gather new photos/videos
2. **Tuesday**: Run `instagram/stages/02-planning` to create content calendar
3. **Wednesday**: Run `instagram/stages/03-content` to write all captions
4. **Thursday**: Run `instagram/stages/04-repurposing` for stories/reels ideas
5. **Post throughout week** using `./instagram/post`

## Goals

1. **Sell existing inventory** -- DM-based sales with clear CTAs
2. **Build audience authentically** -- artist voice, behind-the-scenes
3. **Future commissions** -- establish presence for later commission work

## Ownership Protocol

> **Own the whole system. No artificial boundaries.**

- **All bugs are your responsibility** - No issue is "separate" or "out of scope" without approval
- **Verify before assuming** - Never say "this existed before" without checking
- **Fix before declaring done** - A bug found during testing MUST be fixed before claiming completion
- **Test end-to-end** - "Done" means the system works, not just that code was written

**Red Flags (self-catch):**
- "That's a separate issue" → NO IT ISN'T
- "This existed before my changes" → DID YOU VERIFY?
- "Out of scope" → WHOSE SCOPE? MINE.
- "Someone else's problem" → WHO? NO ONE? THEN MINE.

## Related Workspaces

| Workspace | Path | Description |
|-----------|------|-------------|
| portfolio | `../creative-portfolio/` | Creative technologist portfolio at dev.cerafica.com |

## Direct Action Rule

Before building any script/abstraction:

1. Do the task directly once
2. If repeating, ask: "Is this actually repetitive or imagined?"
3. Only abstract after **3+ real repetitions observed**
4. Default: Just do the work
