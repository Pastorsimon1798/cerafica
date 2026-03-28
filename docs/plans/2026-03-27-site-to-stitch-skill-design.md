# site-to-stitch Skill Design

**Date:** 2026-03-27
**Status:** Approved
**Repo:** New standalone skill (publishable to npm/GitHub)

## Problem

Every existing Stitch skill starts from zero: idea → Stitch → code. None handle the most common real-world scenario: you already have a website and want to use Stitch to explore design improvements without losing your existing aesthetic.

## Solution

`site-to-stitch` reverse-engineers an existing website's design system from its CSS, generates improved variants in Stitch that preserve the brand identity, extracts actionable improvements ranked by ROI, and optionally implements them with visual verification.

## Workflow

### Phase 1-3: Extract & Generate (always runs)

1. **Scan CSS files** for custom properties (colors, fonts, spacing, radii, transitions, shadows)
2. **Classify the aesthetic** (dark/light, minimal/dense, playful/corporate, etc.)
3. **Screenshot live pages** via headless browse as before-state reference
4. **Create Stitch project** with the design system baked into the generation prompt
5. **Generate a screen** from text that matches the existing aesthetic + suggests improvements

### Phase 4: Analyze (always runs, automatic)

6. **Fetch the generated HTML/CSS** from Stitch
7. **Diff against original CSS** to identify concrete improvement techniques
8. **Rank improvements by ROI** (impact vs implementation effort)

### Checkpoint: User decides

Present options:
- **A) Implement** — proceed to Phase 5-6 with selected improvements
- **B) Take over** — Stitch project is ready, user works in Stitch web UI or via manual prompts
- **C) Export** — save extracted design tokens as DESIGN.md for use with other stitch-skills

### Phase 5-6: Implement & Verify (opt-in)

9. **User picks improvements** from the ranked list
10. **Implement selected improvements** in the real CSS files
11. **Take after-state screenshots** via headless browse
12. **Present before/after comparison**

## File Structure

```
site-to-stitch/
├── SKILL.md                              # Core skill definition (frontmatter + workflow)
├── README.md                              # Install & usage
├── workflows/
│   ├── extract-design-tokens.md           # Phase 1: CSS analysis patterns
│   ├── capture-and-generate.md            # Phase 2-3: Screenshots + Stitch generation
│   ├── analyze-and-rank.md                # Phase 4: Diff + ROI ranking
│   └── implement-and-verify.md            # Phase 5-6: Apply CSS + before/after
├── references/
│   ├── css-token-patterns.md              # Regex/grep patterns for extracting design tokens
│   ├── aesthetic-classification.md        # Framework for classifying site aesthetics
│   ├── stitch-tool-schemas.md             # Stitch MCP tool call formats
│   └── improvement-techniques.md          # Common CSS improvement patterns with ROI estimates
└── examples/
    └── design-token-output.md             # Example extracted tokens (from Cerafica)
```

## Allowed Tools

```yaml
allowed-tools:
  - "StitchMCP"     # All Stitch MCP tools
  - "Read"          # Read CSS/HTML files
  - "Write"         # Write design tokens, improvements doc
  - "Edit"          # Apply CSS improvements
  - "Bash"          # Run browse for screenshots, git for commits
  - "Glob"          # Find CSS files
  - "Grep"          # Search for CSS patterns
```

## Unique Value Proposition

1. **Only skill that goes code → Stitch → better code** (all others go idea → Stitch → code)
2. **Automatic aesthetic classification** from CSS patterns
3. **ROI-ranked improvements** so users know what's worth implementing
4. **Checkpoint workflow** — get value even if you stop after analysis
5. **Works on any site** with CSS files, framework-agnostic

## Complementary Skills

This skill integrates with the existing stitch-skills ecosystem:
- **design-md** — can consume the DESIGN.md this skill optionally exports
- **enhance-prompt** — used internally to improve the Stitch generation prompt
- **stitch-design** — user can switch to this after the checkpoint for manual Stitch work
