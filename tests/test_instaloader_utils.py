"""
Tests for instagram/scripts/lib/instaloader_utils.py

Covers: extract_hashtags_from_caption, calculate_engagement_rate,
format_number, post_to_dict (with mocked instaloader.Post).

instaloader.Post requires real HTTP to construct, so we use a MagicMock
that quacks like a Post object.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Stub the instaloader module before importing our utils, so the import
# doesn't fail if instaloader isn't installed.
instaloader_stub = MagicMock()
sys.modules.setdefault("instaloader", instaloader_stub)

sys.path.insert(0, str(Path(__file__).parent.parent / "instagram" / "scripts" / "lib"))

from instaloader_utils import (
    extract_hashtags_from_caption,
    calculate_engagement_rate,
    format_number,
    post_to_dict,
)


# ---------------------------------------------------------------------------
# extract_hashtags_from_caption
# ---------------------------------------------------------------------------

class TestExtractHashtags:
    def test_none_caption_returns_empty(self):
        assert extract_hashtags_from_caption(None) == []

    def test_empty_string_returns_empty(self):
        assert extract_hashtags_from_caption("") == []

    def test_no_hashtags_returns_empty(self):
        assert extract_hashtags_from_caption("Just a plain caption here.") == []

    def test_single_hashtag_extracted(self):
        result = extract_hashtags_from_caption("Beautiful piece. #ceramics")
        assert result == ["#ceramics"]

    def test_multiple_hashtags_extracted(self):
        result = extract_hashtags_from_caption("New work #ceramics #handmade #pottery")
        assert "#ceramics" in result
        assert "#handmade" in result
        assert "#pottery" in result

    def test_hashtag_lowercased(self):
        result = extract_hashtags_from_caption("Check #Ceramics out")
        assert "#ceramics" in result

    def test_trailing_punctuation_stripped(self):
        result = extract_hashtags_from_caption("Loving this #ceramics! and #pottery.")
        assert "#ceramics" in result
        assert "#pottery" in result
        # No trailing punctuation in result
        for tag in result:
            assert tag[-1] not in ".,!?;:"

    def test_lone_hash_not_included(self):
        # "#" alone (length 1 after clean) should be excluded
        result = extract_hashtags_from_caption("# not a tag")
        assert "#" not in result
        assert "# not a tag" not in result

    def test_hashtag_in_middle_of_sentence(self):
        result = extract_hashtags_from_caption("I love #handbuilt work every day")
        assert "#handbuilt" in result

    def test_returns_list_type(self):
        assert isinstance(extract_hashtags_from_caption("hello"), list)


# ---------------------------------------------------------------------------
# calculate_engagement_rate
# ---------------------------------------------------------------------------

class TestCalculateEngagementRate:
    def test_with_followers_returns_percentage(self):
        rate = calculate_engagement_rate(likes=100, comments=10, followers=1000)
        assert rate == pytest.approx(11.0)

    def test_without_followers_returns_raw_sum(self):
        rate = calculate_engagement_rate(likes=50, comments=5)
        assert rate == 55

    def test_followers_none_returns_raw_sum(self):
        rate = calculate_engagement_rate(likes=20, comments=3, followers=None)
        assert rate == 23

    def test_zero_followers_returns_raw_sum(self):
        # followers=0 should not divide by zero
        rate = calculate_engagement_rate(likes=10, comments=2, followers=0)
        assert rate == 12

    def test_zero_likes_and_comments(self):
        rate = calculate_engagement_rate(likes=0, comments=0, followers=500)
        assert rate == 0.0

    def test_high_engagement_rate(self):
        # 500 interactions on 1000 followers = 50%
        rate = calculate_engagement_rate(likes=490, comments=10, followers=1000)
        assert rate == pytest.approx(50.0)


# ---------------------------------------------------------------------------
# format_number
# ---------------------------------------------------------------------------

class TestFormatNumber:
    def test_small_number_no_commas(self):
        assert format_number(999) == "999"

    def test_thousands_has_comma(self):
        assert format_number(1000) == "1,000"

    def test_millions(self):
        assert format_number(1_000_000) == "1,000,000"

    def test_zero(self):
        assert format_number(0) == "0"


# ---------------------------------------------------------------------------
# post_to_dict
# ---------------------------------------------------------------------------

def _make_mock_post(
    shortcode="ABC123",
    mediaid=12345,
    caption="A great piece. #ceramics #handmade",
    date_local=None,
    likes=42,
    comments=7,
    is_video=False,
    video_url=None,
    url="https://example.com/photo.jpg",
    caption_hashtags=None,
    caption_mentions=None,
    location=None,
    typename="GraphImage",
):
    post = MagicMock()
    post.shortcode = shortcode
    post.mediaid = mediaid
    post.caption = caption
    post.date_local = date_local or datetime(2024, 6, 1, 12, 0, 0)
    post.likes = likes
    post.comments = comments
    post.is_video = is_video
    post.video_url = video_url
    post.url = url
    post.caption_hashtags = caption_hashtags or ["ceramics", "handmade"]
    post.caption_mentions = caption_mentions or []
    post.location = location
    post.typename = typename
    return post


class TestPostToDict:
    def test_returns_dict(self):
        post = _make_mock_post()
        result = post_to_dict(post)
        assert isinstance(result, dict)

    def test_shortcode_included(self):
        post = _make_mock_post(shortcode="XYZ999")
        result = post_to_dict(post)
        assert result["shortcode"] == "XYZ999"

    def test_url_constructed_from_shortcode(self):
        post = _make_mock_post(shortcode="XYZ999")
        result = post_to_dict(post)
        assert result["url"] == "https://www.instagram.com/p/XYZ999/"

    def test_caption_included(self):
        post = _make_mock_post(caption="My beautiful bowl.")
        result = post_to_dict(post)
        assert result["caption"] == "My beautiful bowl."

    def test_hashtags_extracted_from_caption(self):
        post = _make_mock_post(caption="Check #ceramics and #pottery")
        result = post_to_dict(post)
        assert "#ceramics" in result["hashtags"]
        assert "#pottery" in result["hashtags"]

    def test_is_video_false_by_default(self):
        post = _make_mock_post(is_video=False)
        result = post_to_dict(post)
        assert result["is_video"] is False
        assert result["video_url"] is None

    def test_is_video_true_includes_video_url(self):
        post = _make_mock_post(is_video=True, video_url="https://example.com/video.mp4")
        result = post_to_dict(post)
        assert result["is_video"] is True
        assert result["video_url"] == "https://example.com/video.mp4"

    def test_likes_and_comments_included(self):
        post = _make_mock_post(likes=100, comments=5)
        result = post_to_dict(post)
        assert result["likes"] == 100
        assert result["comments"] == 5

    def test_date_is_iso_string(self):
        dt = datetime(2024, 3, 15, 9, 0, 0)
        post = _make_mock_post(date_local=dt)
        result = post_to_dict(post)
        assert result["date"] == dt.isoformat()

    def test_mediacount_defaults_to_1_without_attr(self):
        post = _make_mock_post()
        del post.mediacount  # remove attribute to trigger hasattr fallback
        result = post_to_dict(post)
        assert result["mediacount"] == 1
