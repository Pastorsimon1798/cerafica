# Continue: Ceramics Instagram - Test Reels Support

## Where We Left Off

Just implemented Phases 3-5 (Reels, Stories, Carousel support):
- Commit: `324f17e` - Add Reels, Stories, and Carousel support
- Content routing logic: vertical videos <90s → Reels, else → feed post
- New CLI flags: `--reel`, `--story`, `--carousel`, `--post`
- NOT YET TESTED with actual video content

## Next Steps

1. **Test the Reels routing** - Add a vertical video to "To Post" album
   ```bash
   python scripts/auto-post.py --test --no-ai
   ```
   Verify it routes to "reel" instead of "feed_post"

2. **Test the --reel force flag**
   ```bash
   python scripts/auto-post.py --test --reel
   ```

3. **Test with real Meta Business Suite** (live, not dry-run)
   - Requires manual login first time
   - Verify Reels upload flow works

## Quick Verification

```bash
# Check current implementation
python3 -c "
from scripts.lib.photo_export import get_aspect_ratio_category
print('9:16 vertical:', get_aspect_ratio_category(1080, 1920))
print('Horizontal:', get_aspect_ratio_category(1920, 1080))
"

# Test workflow with photo (should route to feed_post)
python scripts/auto-post.py --test --no-ai --count 1
```

## Files Changed

- `scripts/lib/photo_export.py` - MediaType enum, aspect ratio
- `scripts/lib/caption_generator.py` - VideoAnalysis fields, Reels templates
- `scripts/lib/instagram_scheduler.py` - ScheduledReel, ScheduledStory
- `scripts/auto-post.py` - Content routing, CLI flags

## Related

- Research drop created: `workspaces/research-pipeline/inbox/2026-03-12-ai-commit-transparency.md`
- Git architecture concern about workspaces needing own repos
