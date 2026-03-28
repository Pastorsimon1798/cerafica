# site-to-stitch Skill Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create a publishable Agent Skill that reverse-engineers existing websites into Stitch MCP for design iteration, improvement analysis, and optional implementation.

**Architecture:** Markdown-based skill following the Agent Skills open standard. No code runtime — pure instruction files (SKILL.md, workflows, references, examples) that teach Claude how to orchestrate CSS analysis, Stitch MCP calls, and headless browser verification.

**Tech Stack:** Agent Skills format (YAML frontmatter + Markdown), Stitch MCP tools, headless browser (gstack/browse), CSS custom property parsing.

---

## File Structure

All files go into a new directory. The skill will be published as a standalone GitHub repo.

```
site-to-stitch/
├── SKILL.md
├── README.md
├── workflows/
│   ├── extract-design-tokens.md
│   ├── capture-and-generate.md
│   ├── analyze-and-rank.md
│   └── implement-and-verify.md
├── references/
│   ├── css-token-patterns.md
│   ├── aesthetic-classification.md
│   ├── stitch-tool-schemas.md
│   └── improvement-techniques.md
└── examples/
    └── design-token-output.md
```

---

### Task 1: Create SKILL.md — Core skill definition

**Files:**
- Create: `site-to-stitch/SKILL.md`

**Step 1: Write SKILL.md with frontmatter and full workflow**

This is the main entry point. It must have:
- YAML frontmatter: `name`, `description`, `allowed-tools`
- Role definition: who the agent is when running this skill
- When to activate (trigger conditions)
- The 6-phase workflow with checkpoint
- Links to all workflow and reference files

**Frontmatter format (match existing stitch-skills exactly):**
```yaml
---
name: site-to-stitch
description: Reverse-engineers existing websites into Stitch MCP for design iteration. Extracts design tokens from CSS, generates improved variants preserving brand identity, ranks improvements by ROI, and optionally implements with before/after verification.
allowed-tools:
  - "StitchMCP"
  - "Read"
  - "Write"
  - "Edit"
  - "Bash"
  - "Glob"
  - "Grep"
---
```

**Body structure:**
1. Role paragraph (2-3 sentences)
2. "When to Use" section (bullet list of trigger phrases)
3. "Prerequisites" section (Stitch MCP, headless browser, CSS files)
4. Workflow overview table (phase → description → primary tool)
5. Phase 1-3 instructions (inline, not separate file)
6. Phase 4 instructions (inline)
7. Checkpoint section with 3 options (Implement / Take over / Export)
8. Phase 5-6 instructions (link to workflow file)
9. References section (links to all reference files)

**Step 2: Verify frontmatter parses**

Check that the YAML frontmatter has exactly the fields: `name`, `description`, `allowed-tools`. No extra fields.

**Step 3: Verify all internal links resolve**

Every `workflows/` and `references/` file linked in SKILL.md must exist by the end of the plan.

---

### Task 2: Create reference files

**Files:**
- Create: `site-to-stitch/references/css-token-patterns.md`
- Create: `site-to-stitch/references/aesthetic-classification.md`
- Create: `site-to-stitch/references/stitch-tool-schemas.md`
- Create: `site-to-stitch/references/improvement-techniques.md`

**Step 1: Write css-token-patterns.md**

Grep patterns for extracting design tokens from CSS. Must cover:
- CSS custom properties (`--variable-name: value`)
- Color values (hex, rgb, hsl, named colors)
- Font families (with fallback chains)
- Spacing scales (px values in custom properties)
- Border radius values
- Transition/animation timing functions
- Box shadow patterns
- Z-index scales

Format each as: pattern string, what it extracts, example match, example CSS.

**Step 2: Write aesthetic-classification.md**

Framework for classifying a site's aesthetic from its CSS tokens. Must cover:
- Color mode detection (dark/light) — check background luminance
- Density classification (minimal/moderate/dense) — count elements per section, spacing scale
- Typography personality (corporate/playful/technical/artistic) — font family choices
- Shape language (sharp/soft/round/mixed) — border radius distribution
- Motion profile (static/subtle/animated/heavy) — transition/animation count
- Output: a 2-3 sentence aesthetic summary string for the Stitch prompt

**Step 3: Write stitch-tool-schemas.md**

Copy the format from `~/.agents/skills/stitch-design/references/tool-schemas.md` and add:
- `create_project` — with title parameter
- `generate_screen_from_text` — with projectId, prompt, deviceType
- `fetch_screen_code` — with projectId, screenId
- `fetch_screen_image` — with projectId, screenId
- `list_screens` — with projectId
- `get_screen` — with projectId, screenId, name

Include the exact JSON format for each call. Note any gotchas (e.g., `list_screens` output can be huge, use `fetch_screen_code` for the HTML).

**Step 4: Write improvement-techniques.md**

Catalog of common CSS improvements found when comparing Stitch output against original sites. Each entry has:
- Technique name
- What it does (1 sentence)
- CSS implementation (3-5 lines)
- Impact rating (Low/Medium/High)
- Effort rating (5min/15min/30min/1hr)
- ROI score (derived)

Must include at minimum:
- Gradient mesh backgrounds
- Image hover effects (scale, grayscale-to-color)
- Card lift + glow shadows
- Backdrop blur navigation
- Scroll-triggered animations
- Marquee/ticker strips
- Micro-interactions (button press scale, cursor glow)
- Typography hierarchy improvements
- Spacing consistency fixes
- Overlay effects (scan lines, noise textures)

**Step 5: Verify all files are referenced from SKILL.md**

Cross-check: every reference file must be linked from SKILL.md's references section.

---

### Task 3: Create workflow files

**Files:**
- Create: `site-to-stitch/workflows/extract-design-tokens.md`
- Create: `site-to-stitch/workflows/capture-and-generate.md`
- Create: `site-to-stitch/workflows/analyze-and-rank.md`
- Create: `site-to-stitch/workflows/implement-and-verify.md`

**Step 1: Write extract-design-tokens.md**

Phase 1 workflow. Steps:
1. Find CSS files — use Glob for `**/*.css`, exclude node_modules/vendor
2. Read CSS files — use Read tool
3. Extract tokens — use Grep with patterns from `references/css-token-patterns.md`
4. Classify aesthetic — use framework from `references/aesthetic-classification.md`
5. Output — write structured design token summary to `.stitch/site-tokens.md`

Include the exact output format for `.stitch/site-tokens.md`:
```markdown
# Design Tokens: [Site Name]

## Colors
| Token | Value | Role |
|-------|-------|------|
| --bg-primary | #0A0A0A | Page background |

## Typography
| Token | Value | Role |
|-------|-------|------|
| --font-mono | JetBrains Mono | All text |

## Spacing
| Token | Value |
|-------|-------|
| --space-md | 16px |

## Aesthetic Summary
[2-3 sentence description for Stitch prompt]
```

**Step 2: Write capture-and-generate.md**

Phase 2-3 workflow. Steps:
1. Determine pages to capture — ask user for URLs, default to homepage
2. Take screenshots — use headless browse (`$B goto <url>` then `$B screenshot --viewport <path>`)
3. Save to `.stitch/before/` directory
4. Create Stitch project — `create_project` with title "[Site Name] Design Review"
5. Build the Stitch prompt — combine:
   - Aesthetic summary from Phase 1
   - Design tokens (colors, fonts, spacing, radii)
   - Current page structure (from screenshots)
   - Improvement suggestions (from `references/improvement-techniques.md`)
6. Generate screen — `generate_screen_from_text` with DESKTOP device type
7. Handle output — if output is too large, read from saved file
8. Save screen ID for later phases

Include the prompt template:
```markdown
[Page description] for [Site Name].

**AESTHETIC:** [Aesthetic summary from Phase 1]

**DESIGN SYSTEM (PRESERVE EXACTLY):**
- Background: [bg color] (#hex)
- Cards/Surfaces: [card color] (#hex)
- Primary Accent: [accent color] (#hex) for [roles]
- Secondary Accent: [secondary color] (#hex) for [roles]
- Text Primary: [fg color] (#hex)
- Text Secondary: [muted color] (#hex)
- Font: [font family] for all text
- Headings: [heading style — uppercase/lowercase/uppercase]
- Border Radius: [radius description]
- Spacing: [spacing scale description]

**PAGE STRUCTURE:**
[Numbered sections matching current site layout]

**IMPROVEMENTS TO EXPLORE:**
[3-5 specific improvements from improvement-techniques.md that fit this aesthetic]
```

**Step 3: Write analyze-and-rank.md**

Phase 4 workflow. Steps:
1. Fetch generated screen code — `fetch_screen_code` with projectId and screenId
2. Parse the generated HTML/CSS for techniques used
3. Compare against original CSS — identify:
   - Techniques in generated code that are NOT in original (new improvements)
   - Techniques in both (already implemented, skip)
   - CSS patterns that are cleaner/different in generated code
4. For each new technique, determine:
   - Impact: High/Medium/Low (visual impact on user)
   - Effort: time estimate based on CSS complexity
   - ROI: Impact / Effort
5. Sort by ROI descending
6. Output — present ranked table to user

Include the output format:
```markdown
## Improvement Analysis

| # | Improvement | Impact | Effort | ROI | Generated CSS Pattern |
|---|---|---|---|---|---|
| 1 | Gradient mesh hero bg | High | 10 min | **High** | `radial-gradient(...)` |
| 2 | Image scale on hover | Medium | 5 min | **High** | `group-hover:scale-110` |
```

**Step 4: Write implement-and-verify.md**

Phase 5-6 workflow. Steps:
1. User selects improvements from the ranked list
2. For each selected improvement:
   a. Read the target CSS file
   b. Apply the change using Edit tool
   c. Verify the CSS is valid (no syntax errors)
   d. Commit atomically: `git add <file> && git commit -m "style: <improvement description>"`
3. Take after-state screenshots — same URLs, same viewport, save to `.stitch/after/`
4. Present before/after comparison — Read both images, show them side by side
5. Flag any regressions (elements that looked worse)

Include rollback instruction: if user is unhappy, `git revert` the commits.

---

### Task 4: Create example file

**Files:**
- Create: `site-to-stitch/examples/design-token-output.md`

**Step 1: Write example design token output**

Use the real Cerafica extraction as the example. This must be a realistic, complete output showing what `.stitch/site-tokens.md` looks like after running Phase 1 on a real site.

Include:
- Complete color table (all custom properties with hex values and roles)
- Typography section (fonts, sizes, weights)
- Spacing section (full scale)
- Border radius section
- Animation/transition section
- Aesthetic summary (the paragraph that would go into the Stitch prompt)

Use real values from Cerafica's `css/variables.css`.

---

### Task 5: Create README.md

**Files:**
- Create: `site-to-stitch/README.md`

**Step 1: Write README.md**

Follow the exact format of existing stitch-skills READMEs:
1. Install command: `npx skills add <repo> --skill site-to-stitch --global`
2. What It Does (4-5 bullet points)
3. Prerequisites (Stitch MCP, headless browser)
4. Example Prompt
5. Skill Structure (file tree)
6. Works With (complementary skills)
7. Learn More link to SKILL.md

---

### Task 6: Final verification

**Step 1: Check all internal links**

For every `[text](path)` link in every .md file, verify the target file exists. No broken links.

**Step 2: Check frontmatter validity**

Run `head -20 site-to-stitch/SKILL.md` and verify YAML parses correctly. Fields: name, description, allowed-tools.

**Step 3: Check no broken references**

Every file referenced in SKILL.md's "References" section must exist. Every workflow file linked from SKILL.md must exist. Every reference file linked from workflow files must exist.

**Step 4: Review for quality**

Read SKILL.md top to bottom. Check:
- Voice matches existing stitch-skills (professional, instructional)
- No placeholders or TODOs
- All examples are concrete
- Checkpoint is clearly documented
- Allowed tools match what's actually used in workflows

**Step 5: Create git repo and initial commit**

```bash
cd site-to-stitch
git init
git add -A
git commit -m "feat: initial site-to-stitch skill"
```
