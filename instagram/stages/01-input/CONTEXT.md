# Stage: Input -- Collect Weekly Assets

Gather new photos/videos + context for the week's content.

## Inputs

| Source | What | Location |
|--------|------|----------|
| User | New photos/videos | Provided directly |
| Previous week | What was posted | `../04-repurposing/output/` |
| Instagram Sync | Auto-extracted posts | `output/weekly-assets-[date].md` |

## Automation Option

**Automatic extraction available:** Run `instagram/scripts/sync-weekly.py` to automatically:
- Pull new Instagram posts since last sync
- Download media to `instagram/data/archive/cerafica_media/`
- Generate `output/weekly-assets-[date].md` with all post details

```bash
cd instagram/scripts
python sync-weekly.py
```

This is ideal if you post directly to Instagram and want the workspace to track your content automatically.

## Process (Manual)

1. Ask user: "What new work have you made this week?"
2. Collect photo/video files (or descriptions if files aren't available)
3. Note status of each piece:
   - Available for sale
   - Already sold
   - Work in progress
   - Process/atmospheric shots
4. Capture any stories/moments from the studio
5. Ask about any specific goals for this week (sales push vs. process content)

## Output

| File | Location |
|------|----------|
| Weekly assets | `output/weekly-assets-[date].md` |

### Output Format

```markdown
# Weekly Assets: [Date]

## New Work
| Piece | Status | Photos | Notes |
|-------|--------|--------|-------|
| [name] | available/sold/wip | [count] | [context] |

## Process/Studio Shots
- [list of assets with descriptions]

## This Week's Focus
- Primary goal: [sales/process/mix]
- Priority pieces: [if any]

## Raw Notes
- [any studio stories, moments, context]
```

## Checkpoint

After asset collection, present the summary and ask:
- "This week, do you want to focus on selling pieces or showing process?"
- Adjust priorities based on answer.

## Next Stage

When complete, continue to `stages/02-planning/CONTEXT.md`
