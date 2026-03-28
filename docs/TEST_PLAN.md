# Comprehensive Test Plan: Reels/Stories/Carousel Support

## Implementation Scope

| Component | File | Purpose |
|-----------|------|---------|
| MediaType enum | photo_export.py:23 | PHOTO, VIDEO, REEL, STORY |
| MediaInfo class | photo_export.py:32 | Media metadata including media_type, aspect_ratio |
| get_aspect_ratio_category() | photo_export.py:53 | Categorize dimensions (vertical_9_16, vertical, square, horizontal) |
| get_media_from_album() | photo_export.py:158 | Get photos AND videos from album |
| export_media_by_index() | photo_export.py:612 | Export photo OR video |
| VideoAnalysis | caption_generator.py:58 | Video analysis with is_reel_suitable field |
| analyze_video_basic() | caption_generator.py:234 | Sets is_reel_suitable based on duration/aspect ratio |
| determine_content_destination() | auto-post.py:102 | Routes content to feed_post/reel/story/carousel |
| ScheduledReel/Story/Carousel | instagram_scheduler.py:34-54 | Dataclasses for scheduling |
| schedule_reel/story/carousel() | instagram_scheduler.py:449+ | Actual Meta Business Suite scheduling |

## Critical Untested Paths

### What I Previously Tested (INADEQUATE):
1. ✅ Aspect ratio categorization (unit test)
2. ⚠️ Photo routing (dry-run only, not actual scheduling)
3. ⚠️ Class imports (shallow - just checked they exist)
4. ⚠️ --reel flag (dry-run only)

### What I Did NOT Test:
1. ❌ Video detection in get_media_from_album()
2. ❌ Video export functionality
3. ❌ Video analysis (is_reel_suitable logic)
4. ❌ Vertical video routing to Reel
5. ❌ Long video (>90s) routing to feed_post
6. ❌ Horizontal video routing
7. ❌ --story flag
8. ❌ --carousel flag
9. ❌ Carousel grouping logic
10. ❌ Story scheduling code path
11. ❌ Carousel scheduling code path
12. ❌ Actual Meta Business Suite interaction (all dry-run)

---

## SMOKE TESTS (Basic Functionality)

### SM-1: Video Detection in Album
**Purpose:** Verify get_media_from_album() detects videos with correct media_type
**Test:** Call get_media_from_album() and check MediaType.VIDEO items exist
**Expected:** Videos have media_type=VIDEO, aspect_ratio set correctly

### SM-2: Video Export
**Purpose:** Verify export_media_by_index() works for video files
**Test:** Export a video by index and check output file exists
**Expected:** Video file exported to temp directory, playable

### SM-3: Video Analysis - Reel Suitable
**Purpose:** Verify analyze_video_basic() sets is_reel_suitable=True for vertical <90s video
**Test:** Analyze 30s vertical video
**Expected:** is_reel_suitable=True, aspect_ratio_category=vertical_9_16

### SM-4: Video Analysis - Not Reel Suitable (Duration)
**Purpose:** Verify analyze_video_basic() sets is_reel_suitable=False for >90s video
**Test:** Analyze 120s video
**Expected:** is_reel_suitable=False, duration_warning set

### SM-5: Video Analysis - Not Reel Suitable (Aspect)
**Purpose:** Verify analyze_video_basic() sets is_reel_suitable=False for horizontal video
**Test:** Analyze horizontal video
**Expected:** is_reel_suitable=False, aspect_ratio_category=horizontal

### SM-6: Content Routing - Vertical Video to Reel
**Purpose:** Verify determine_content_destination() routes vertical <90s video to reel
**Test:** Call with MediaInfo (VIDEO, vertical) + VideoAnalysis (is_reel_suitable=True)
**Expected:** Returns "reel"

### SM-7: Content Routing - Long Video to Feed
**Purpose:** Verify determine_content_destination() routes >90s video to feed_post
**Test:** Call with MediaInfo (VIDEO) + VideoAnalysis (is_reel_suitable=False, duration_warning)
**Expected:** Returns "feed_post"

### SM-8: Content Routing - Photo to Feed
**Purpose:** Verify determine_content_destination() routes photo to feed_post
**Test:** Call with MediaInfo (PHOTO) + PhotoAnalysis
**Expected:** Returns "feed_post"

### SM-9: Force Type Flags
**Purpose:** Verify force_type parameter overrides routing
**Test:** Call with force_type="story"
**Expected:** Returns "story" regardless of media type

### SM-10: Carousel Grouping
**Purpose:** Verify group_media_for_carousel() groups related media
**Test:** Call with multiple MediaInfo items
**Expected:** Returns MediaGroup with multiple items or None if not suitable

---

## END-TO-END TESTS (Full Workflow)

### E2E-1: Video Post End-to-End (Dry-Run)
**Purpose:** Complete workflow with video from album to scheduled post
**Test:** Place video in "To Post" album, run --test with video
**Expected:**
- Video detected and exported
- Video analyzed with correct is_reel_suitable
- Routed to correct destination
- Report generated with video details

### E2E-2: Reel Workflow (Dry-Run)
**Purpose:** Vertical video <90s routes to Reel
**Test:** Place vertical video <90s in album, run --test --no-ai
**Expected:** Routes to "reel" destination

### E2E-3: Story Flag (Dry-Run)
**Purpose:** --story flag forces Story routing
**Test:** Run --test --story
**Expected:** Routes to "story" destination

### E2E-4: Carousel Flag (Dry-Run)
**Purpose:** --carousel flag enables carousel grouping
**Test:** Multiple photos in album, run --test --carousel
**Expected:** Groups photos into carousel

### E2E-5: Multiple Items (Dry-Run)
**Purpose:** Process multiple mixed media types
**Test:** 1 photo + 1 video in album, run --test --count 2
**Expected:** Both processed with correct routing

---

## USER ACCEPTANCE TESTS (Real Workflows)

### UAT-1: Artist Adds Vertical Video
**User Story:** As an artist, I want to add a vertical video of me throwing pottery and have it automatically become a Reel
**Steps:**
1. Add vertical video (<90s) to "To Post" album
2. Run auto-post workflow
**Expected:** Video routes to Reel with appropriate caption

### UAT-2: Artist Adds Long Process Video
**User Story:** As an artist, I want to add a longer process video and have it become a feed post (not Reel)
**Steps:**
1. Add horizontal or >90s video to "To Post" album
2. Run auto-post workflow
**Expected:** Video routes to feed_post with appropriate warning

### UAT-3: Artist Forces Story
**User Story:** As an artist, I want to post a photo as a Story instead of a feed post
**Steps:**
1. Add photo to "To Post" album
2. Run with --story flag
**Expected:** Routes to Story destination

### UAT-4: Artist Creates Carousel
**User Story:** As an artist, I want to group multiple photos into a carousel post
**Steps:**
1. Add multiple related photos to "To Post" album
2. Run with --carousel flag
**Expected:** Photos grouped into carousel with combined caption

---

## INTEGRATION TESTS (Requires Manual Steps)

### INT-1: Live Meta Business Suite - Reel
**Purpose:** Verify schedule_reel() actually works with real Meta
**Manual Steps Required:**
1. Run without --test flag with vertical video
2. Verify browser opens and navigates to Reels section
3. Verify video uploads
4. Verify caption appears
**Blocker:** Requires Meta login and manual verification

### INT-2: Live Meta Business Suite - Story
**Purpose:** Verify schedule_story() actually works
**Manual Steps Required:** Same as INT-1

### INT-3: Live Meta Business Suite - Carousel
**Purpose:** Verify schedule_carousel() actually works
**Manual Steps Required:** Same as INT-1

---

## Test Execution Order

1. **Smoke Tests** (SM-1 to SM-10) - Automated, no external dependencies
2. **End-to-End Tests** (E2E-1 to E2E-5) - Dry-run mode, no live posting
3. **User Acceptance Tests** (UAT-1 to UAT-4) - May require test fixtures
4. **Integration Tests** (INT-1 to INT-3) - Requires manual steps and Meta login

---

## Test Fixtures Needed

For complete testing, I need:
1. Short vertical video (<90s, 9:16) - for Reel routing test
2. Long video (>90s) - for feed_post routing test
3. Horizontal video - for aspect ratio test
4. Multiple photos - for carousel test

Without real video files, I will:
1. Test the code paths with mock data
2. Test the actual code logic
3. Document what requires real media files
