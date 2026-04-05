"""
Tests for instagram/scripts/lib/instagram_scheduler.py

Covers: cookies_valid, get_posting_schedule, and the four Schedule dataclasses.
Playwright / browser automation is NOT tested here.
"""
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "instagram" / "scripts" / "lib"))

from instagram_scheduler import (
    ScheduledPost,
    ScheduledReel,
    ScheduledStory,
    ScheduledCarousel,
    cookies_valid,
    get_posting_schedule,
)


# ---------------------------------------------------------------------------
# cookies_valid
# ---------------------------------------------------------------------------

ESSENTIAL = ["xs", "c_user", "fr"]
FAR_FUTURE = int(time.time()) + 60 * 60 * 24 * 30  # 30 days from now
PAST = int(time.time()) - 1                          # already expired


def _make_cookies(names=None, expires=FAR_FUTURE, include_expires=True):
    """Build a minimal cookies list with the given names and expiry."""
    names = names or ESSENTIAL
    cookies = []
    for name in names:
        cookie = {"name": name, "value": "dummy"}
        if include_expires:
            cookie["expires"] = expires
        cookies.append(cookie)
    return cookies


class TestCookiesValid:
    def test_empty_list_is_invalid(self):
        assert cookies_valid([]) is False

    def test_all_essential_present_and_future_is_valid(self):
        assert cookies_valid(_make_cookies()) is True

    def test_missing_one_essential_is_invalid(self):
        cookies = _make_cookies(names=["xs", "c_user"])  # missing "fr"
        assert cookies_valid(cookies) is False

    def test_missing_all_essentials_is_invalid(self):
        cookies = [{"name": "random", "value": "x", "expires": FAR_FUTURE}]
        assert cookies_valid(cookies) is False

    def test_expired_cookie_is_invalid(self):
        cookies = _make_cookies(expires=PAST)
        assert cookies_valid(cookies) is False

    def test_cookie_without_expires_field_counts_as_valid(self):
        # No "expires" key → treated as session cookie (valid)
        cookies = _make_cookies(include_expires=False)
        assert cookies_valid(cookies) is True

    def test_mixed_expired_and_fresh_is_invalid(self):
        # "xs" and "c_user" are fresh, "fr" is expired
        cookies = [
            {"name": "xs",     "value": "x", "expires": FAR_FUTURE},
            {"name": "c_user", "value": "x", "expires": FAR_FUTURE},
            {"name": "fr",     "value": "x", "expires": PAST},
        ]
        assert cookies_valid(cookies) is False

    def test_extra_non_essential_cookies_do_not_affect_result(self):
        cookies = _make_cookies() + [{"name": "extra", "value": "x", "expires": FAR_FUTURE}]
        assert cookies_valid(cookies) is True


# ---------------------------------------------------------------------------
# get_posting_schedule
# ---------------------------------------------------------------------------

# Pinned reference: Monday 2026-04-06 08:00 local
MONDAY_MORNING = datetime(2026, 4, 6, 8, 0, 0)
# A Sunday afternoon where all daily windows have already passed
SUNDAY_AFTERNOON = datetime(2026, 4, 5, 18, 0, 0)


class TestGetPostingSchedule:
    def test_returns_list(self):
        result = get_posting_schedule(reference_date=MONDAY_MORNING)
        assert isinstance(result, list)

    def test_default_count_is_3(self):
        result = get_posting_schedule()
        assert len(result) == 3

    def test_custom_count_respected(self):
        for count in [1, 3, 5, 7]:
            result = get_posting_schedule(count=count)
            assert len(result) == count

    def test_all_slots_are_datetime_objects(self):
        result = get_posting_schedule(count=3)
        for slot in result:
            assert isinstance(slot, datetime)

    def test_all_slots_in_the_future(self):
        now = datetime.now()
        result = get_posting_schedule(count=7)
        for slot in result:
            assert slot > now, f"Slot {slot} is not in the future"

    def test_slots_are_in_ascending_order(self):
        result = get_posting_schedule(count=5)
        for i in range(len(result) - 1):
            assert result[i] <= result[i + 1]

    def test_no_slot_within_30_minutes_of_now(self):
        now = datetime.now()
        result = get_posting_schedule(count=7)
        for slot in result:
            assert slot >= now + timedelta(minutes=30), (
                f"Slot {slot} is too close to now ({now})"
            )

    def test_slots_only_on_valid_weekdays(self):
        # Valid posting days: Mon=0, Tue=1, Wed=2, Thu=3, Fri=4, Sat=5, Sun=6
        valid_weekdays = {0, 1, 2, 3, 4, 5, 6}  # all — but each slot maps to one day
        result = get_posting_schedule(count=7)
        weekdays = {slot.weekday() for slot in result}
        assert weekdays.issubset(valid_weekdays)

    def test_slots_at_expected_hours(self):
        # All slots should be at 8, 9, or 10 AM
        result = get_posting_schedule(count=7)
        for slot in result:
            assert slot.hour in {8, 9, 10}, f"Unexpected hour {slot.hour} in slot {slot}"

    def test_no_duplicate_slots(self):
        result = get_posting_schedule(count=7)
        assert len(result) == len(set(result))


# ---------------------------------------------------------------------------
# Schedule dataclasses
# ---------------------------------------------------------------------------

class TestScheduledPost:
    def test_basic_construction(self):
        post = ScheduledPost(
            photo_path="/tmp/photo.jpg",
            caption="New bowl.",
            schedule_time=MONDAY_MORNING,
        )
        assert post.photo_path == "/tmp/photo.jpg"
        assert post.caption == "New bowl."
        assert post.schedule_time == MONDAY_MORNING
        assert post.photo_id is None
        assert post.alt_text is None

    def test_optional_fields(self):
        post = ScheduledPost(
            photo_path="/tmp/photo.jpg",
            caption="Bowl.",
            schedule_time=MONDAY_MORNING,
            photo_id="p123",
            alt_text="A handmade bowl.",
        )
        assert post.photo_id == "p123"
        assert post.alt_text == "A handmade bowl."


class TestScheduledReel:
    def test_basic_construction(self):
        reel = ScheduledReel(
            video_path="/tmp/reel.mp4",
            caption="Process video.",
            schedule_time=MONDAY_MORNING,
            duration_seconds=30.5,
        )
        assert reel.video_path == "/tmp/reel.mp4"
        assert reel.duration_seconds == 30.5
        assert reel.aspect_ratio == "vertical"  # default

    def test_custom_aspect_ratio(self):
        reel = ScheduledReel(
            video_path="/tmp/reel.mp4",
            caption="",
            schedule_time=MONDAY_MORNING,
            duration_seconds=15.0,
            aspect_ratio="square",
        )
        assert reel.aspect_ratio == "square"


class TestScheduledStory:
    def test_basic_construction(self):
        story = ScheduledStory(
            media_path="/tmp/story.jpg",
            schedule_time=MONDAY_MORNING,
            media_type="photo",
        )
        assert story.media_type == "photo"
        assert story.poll_question is None
        assert story.poll_options is None

    def test_poll_fields(self):
        story = ScheduledStory(
            media_path="/tmp/story.jpg",
            schedule_time=MONDAY_MORNING,
            media_type="photo",
            poll_question="Favourite glaze?",
            poll_options=["Celadon", "Shino"],
        )
        assert story.poll_question == "Favourite glaze?"
        assert story.poll_options == ["Celadon", "Shino"]


class TestScheduledCarousel:
    def test_basic_construction(self):
        carousel = ScheduledCarousel(
            media_paths=["/tmp/a.jpg", "/tmp/b.jpg"],
            caption="Series.",
            schedule_time=MONDAY_MORNING,
            card_count=2,
        )
        assert len(carousel.media_paths) == 2
        assert carousel.card_count == 2
        assert carousel.carousel_id is None
