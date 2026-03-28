# Test Report: Reels/Stories/Carousel Support
**Date:** 2026-03-13
**Commit Tested:** 324f17e

---

## Summary

**OVERALL STATUS: ❌ FAILED**

The implementation has critical bugs that prevent Stories and Carousel features from working. Only Photos and Reels routing works correctly, and even Reels may not schedule correctly in live mode.

---

## Test Results

### ✅ PASSED: Smoke Tests (SM-1 to SM-10)

| Test | Description | Result |
|------|-------------|--------|
| SM-1 | Video detection in album | ✅ PASS |
| SM-2 | Video file detection (is_video_file) | ✅ PASS |
| SM-3 | Video analysis - Reel suitable (<90s vertical) | ✅ PASS |
| SM-4 | Video analysis - Not suitable (duration >90s) | ✅ PASS |
| SM-5 | Video analysis - Not suitable (horizontal) | ✅ PASS |
| SM-6 | Content routing - Vertical video to Reel | ✅ PASS |
| SM-7 | Content routing - Long video to feed_post | ✅ PASS |
| SM-8 | Content routing - Photo to feed_post | ✅ PASS |
| SM-9 | Force type flags (--reel, --story, --carousel) | ✅ PASS (routing) |
| SM-10 | Carousel grouping logic | ✅ PASS |

### ⚠️ PARTIAL: End-to-End Tests (E2E-1 to E2E-5)

| Test | Description | Result |
|------|-------------|--------|
| E2E-1 | Video post end-to-end (dry-run) | ✅ PASS |
| E2E-2 | Reel workflow (dry-run) | ✅ PASS |
| E2E-3 | Story flag (dry-run) | ⚠️ PARTIAL - Routes correctly but won't schedule |
| E2E-4 | Carousel flag (dry-run) | ❌ FAIL - Flag ignored |
| E2E-5 | Multiple items (dry-run) | ✅ PASS |

---

## 🐛 CRITICAL BUGS FOUND

### BUG #1: Carousel Feature Not Implemented
**Location:** `scripts/auto-post.py` line 214-484 (run_workflow function)
**Severity:** CRITICAL

**Description:**
The `enable_carousel` parameter is accepted by `run_workflow()` but never used. The carousel grouping function `group_media_for_carousel()` exists but is never called.

**Evidence:**
```python
# Parameter is accepted but never used:
def run_workflow(
    ...
    enable_carousel: bool = False  # Line 219
) -> dict:

# No code anywhere in the function checks enable_carousel
# No call to group_media_for_carousel()
# No use of ScheduledCarousel
```

**Impact:** `--carousel` flag does nothing.

---

### BUG #2: Story Scheduling Not Implemented
**Location:** `scripts/auto-post.py` lines 419-435
**Severity:** CRITICAL

**Description:**
The scheduling code only has two branches: "reel" and everything else (feed_post). Stories are routed correctly but fall through to the default feed_post scheduling.

**Evidence:**
```python
# Line 419-435 - Only handles reel and default
if destination == "reel":
    reel = ScheduledReel(...)
    success = scheduler.schedule_reel(reel, dry_run=False)
else:
    # Everything else becomes a feed post
    scheduled_post = ScheduledPost(...)
    success = scheduler.schedule_post(scheduled_post, dry_run=False)

# MISSING:
# if destination == "story":
#     story = ScheduledStory(...)
#     success = scheduler.schedule_story(story, dry_run=False)
```

**Impact:** `--story` flag routes correctly but scheduling will post as feed_post.

---

### BUG #3: Carousel Scheduling Not Implemented
**Location:** `scripts/auto-post.py` lines 419-435
**Severity:** CRITICAL

**Description:**
Same as Bug #2 - no handling for `destination == "carousel"`.

**Impact:** Carousels can never be scheduled.

---

## ⚠️ UNTESTED AREAS (Require Manual Testing)

### Live Meta Business Suite Integration
- **INT-1:** `schedule_reel()` with real Meta - NOT TESTED
- **INT-2:** `schedule_story()` with real Meta - NOT TESTED
- **INT-3:** `schedule_carousel()` with real Meta - NOT TESTED

**Reason:** Requires browser authentication and manual verification.

### Real Video Processing
- Video export from Photos album (no test videos available)
- Video analysis with ffprobe (ffprobe returns empty dict for non-existent files)

---

## Files Affected

| File | Issue |
|------|-------|
| `scripts/auto-post.py:219` | `enable_carousel` parameter unused |
| `scripts/auto-post.py:419-435` | Missing story/carousel scheduling branches |
| `scripts/auto-post.py:138-174` | `group_media_for_carousel()` defined but never called |

---

## Correct Implementation Required

To fix these bugs, the scheduling section in `run_workflow()` needs:

```python
# Step 6: Schedule posts
for post in posts_to_schedule:
    destination = post["media_type"]

    if destination == "reel":
        reel = ScheduledReel(...)
        success = scheduler.schedule_reel(reel, dry_run=False)
    elif destination == "story":
        story = ScheduledStory(...)
        success = scheduler.schedule_story(story, dry_run=False)
    elif destination == "carousel":
        carousel = ScheduledCarousel(...)
        success = scheduler.schedule_carousel(carousel, dry_run=False)
    else:
        # Default: feed post
        scheduled_post = ScheduledPost(...)
        success = scheduler.schedule_post(scheduled_post, dry_run=False)
```

And carousel grouping needs to be called:

```python
# After getting media from album
if enable_carousel and len(media_items) >= 2:
    carousel_group = group_media_for_carousel(media_items)
    if carousel_group:
        # Process as carousel instead of individual posts
        ...
```

---

## Verification Checklist (From Plan)

- [x] Aspect ratio detection returns correct categories
- [x] Photo content routes to `feed_post`
- [x] All MediaType/Scheduled* classes import without errors
- [x] `--reel` flag forces Reel routing
- [ ] **`--story` flag actually schedules Stories** ❌ BROKEN
- [ ] **`--carousel` flag works end-to-end** ❌ NOT IMPLEMENTED
- [ ] Live Meta Business Suite upload works ⏸️ REQUIRES MANUAL TEST

---

## Recommendation

**DO NOT USE THIS FEATURE IN PRODUCTION**

The Stories and Carousel features are incomplete and will not work as expected. Only basic photo posts and Reel routing function correctly. Fix the bugs above before using these features.
