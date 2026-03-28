# Cerafica — Agent Instructions

This is the Cerafica project instructions file for Kimi Code. It gets auto-loaded at session start to provide context for managing the Cerafica ceramics brand across all channels: Instagram, website, and internal tooling.

## Project Overview

Cerafica is a ceramics brand managed across multiple channels:
- **Instagram** — Content creation, scheduling, and posting
- **Website** — E-commerce site (HTML/CSS/JS)
- **Tools** — Internal feedback and tooling systems

## Folder Map

```
cerafica/
├── brand/           # Brand identity, voice, photography guide
├── inventory/       # Product photos & data (products.json = single source of truth)
├── shared/          # Shared resources
├── output/          # Generated media
├── instagram/       # Instagram operations (scripts, stages, posting-packs)
├── website/         # E-commerce site (HTML/CSS/JS)
├── tools/           # Feedback & tooling
└── docs/            # Plans, research, handoffs
```

## Routing

| Task | Where |
|------|-------|
| Instagram content | instagram/stages/01-input through 04-repurposing |
| Post content | ./instagram/post |
| Website pages | website/ |
| Product data | inventory/products.json |
| Brand identity | brand/identity.md |
| Voice guidelines | brand/voice-rules.md |
| Performance | brand/performance-insights.md |

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

## Direct Action Rule

Before building any script/abstraction:

1. Do the task directly once
2. If repeating, ask: "Is this actually repetitive or imagined?"
3. Only abstract after **3+ real repetitions observed**
4. Default: Just do the work

## Anti-Patterns (NEVER do these)

- Never say "that's a separate issue" without verification
- Never say "this existed before" without checking git history
- Never say "out of scope" without user approval
- Never leave TODO/FIXME comments in committed code
- Never add console.log or debug statements in non-test files
- Never claim work is complete without running verification
- Never skip tests "just this once" — TDD is non-negotiable
- Never over-engineer — three similar lines > premature abstraction
- Never use emojis in code or commit messages unless explicitly asked

## Video Pipeline (CRITICAL)

- **Source videos live in ~/Downloads/** — check there FIRST
- User edits videos in Apple Photos before exporting
- **Source is 60fps iPhone video** — ALWAYS use `--slowdown 1` for 30fps output
- 60fps→30fps = natural slow-mo. NEVER use `--slowdown 2` (makes claymation)
- Pipeline: `frame_video.py --input <path> --planet <name> --slowdown 1`
- Verify: compare duration. If ~40s+ and user says ~10s, it's the WRONG file

## Safety Guardrails

Always confirm before:
- `rm -rf` (destructive deletion)
- `git push --force` or `--force-with-lease`
- `git reset --hard`
- `DROP TABLE` or destructive database operations
- Pushing to main/master without explicit approval
- Deleting branches with unmerged work

## Related Workspaces

| Workspace | Path | Description |
|-----------|------|-------------|
| portfolio | ../creative-portfolio/ | Creative technologist portfolio at dev.cerafica.com |
