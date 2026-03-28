#!/usr/bin/env python3
"""
Analyze Content Performance from Instagram Archive

Generates performance dashboard with:
- Top posts by likes/comments
- Best posting days/times
- Content type performance
- Engagement trends

Usage:
    python analyze-performance.py

Output:
    Creates brand/performance-insights.md
"""

import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent / "lib"))

from instaloader_utils import (
    get_archive_path,
    load_archive,
    get_workspace_root,
)


def get_top_posts(posts: list[dict], metric: str = "likes", n: int = 10) -> list[dict]:
    """Get top posts by a specific metric."""
    sorted_posts = sorted(posts, key=lambda p: p.get(metric, 0), reverse=True)

    top = []
    for post in sorted_posts[:n]:
        top.append({
            "url": post.get("url", ""),
            "shortcode": post.get("shortcode", ""),
            "caption": (post.get("caption", "") or "")[:100],
            "likes": post.get("likes", 0),
            "comments": post.get("comments", 0),
            "engagement": post.get("likes", 0) + post.get("comments", 0),
            "date": post.get("date", ""),
            "is_video": post.get("is_video", False),
            "hashtag_count": len(post.get("hashtags", [])),
            "caption_length": len(post.get("caption", "") or ""),
        })

    return top


def analyze_posting_schedule(posts: list[dict]) -> dict:
    """Analyze best days and times to post."""
    day_stats = defaultdict(lambda: {"posts": 0, "likes": [], "comments": []})
    hour_stats = defaultdict(lambda: {"posts": 0, "likes": [], "comments": []})

    for post in posts:
        date_str = post.get("date", "")
        if not date_str:
            continue

        try:
            dt = datetime.fromisoformat(date_str)
            day_name = dt.strftime("%A")
            hour = dt.hour

            likes = post.get("likes", 0)
            comments = post.get("comments", 0)

            day_stats[day_name]["posts"] += 1
            day_stats[day_name]["likes"].append(likes)
            day_stats[day_name]["comments"].append(comments)

            hour_stats[hour]["posts"] += 1
            hour_stats[hour]["likes"].append(likes)
            hour_stats[hour]["comments"].append(comments)

        except ValueError:
            continue

    # Calculate averages for days
    day_performance = []
    for day, stats in day_stats.items():
        if stats["likes"]:
            avg_engagement = (sum(stats["likes"]) + sum(stats["comments"])) / len(stats["likes"])
            day_performance.append({
                "day": day,
                "posts": stats["posts"],
                "avg_engagement": round(avg_engagement),
            })

    day_performance.sort(key=lambda x: x["avg_engagement"], reverse=True)

    # Calculate averages for hours
    hour_performance = []
    for hour, stats in hour_stats.items():
        if stats["likes"]:
            avg_engagement = (sum(stats["likes"]) + sum(stats["comments"])) / len(stats["likes"])
            hour_performance.append({
                "hour": hour,
                "hour_formatted": f"{hour:02d}:00",
                "posts": stats["posts"],
                "avg_engagement": round(avg_engagement),
            })

    hour_performance.sort(key=lambda x: x["avg_engagement"], reverse=True)

    return {
        "by_day": day_performance,
        "by_hour": hour_performance[:10],  # Top 10 hours
    }


def analyze_content_types(posts: list[dict]) -> dict:
    """Analyze performance by content type."""
    video_stats = {"posts": 0, "likes": [], "comments": []}
    image_stats = {"posts": 0, "likes": [], "comments": []}
    carousel_stats = {"posts": 0, "likes": [], "comments": []}

    for post in posts:
        likes = post.get("likes", 0)
        comments = post.get("comments", 0)
        is_video = post.get("is_video", False)
        media_count = post.get("mediacount", 1)

        if is_video:
            video_stats["posts"] += 1
            video_stats["likes"].append(likes)
            video_stats["comments"].append(comments)
        elif media_count > 1:
            carousel_stats["posts"] += 1
            carousel_stats["likes"].append(likes)
            carousel_stats["comments"].append(comments)
        else:
            image_stats["posts"] += 1
            image_stats["likes"].append(likes)
            image_stats["comments"].append(comments)

    def calc_avg(stats):
        if not stats["likes"]:
            return {"posts": 0, "avg_engagement": 0}
        avg = (sum(stats["likes"]) + sum(stats["comments"])) / len(stats["likes"])
        return {"posts": stats["posts"], "avg_engagement": round(avg)}

    return {
        "video": calc_avg(video_stats),
        "image": calc_avg(image_stats),
        "carousel": calc_avg(carousel_stats),
    }


def analyze_caption_length_performance(posts: list[dict]) -> list[dict]:
    """Analyze performance by caption length."""
    length_stats = defaultdict(lambda: {"posts": 0, "engagement": []})

    for post in posts:
        caption_len = len(post.get("caption", "") or "")
        engagement = post.get("likes", 0) + post.get("comments", 0)

        # Categorize
        if caption_len < 50:
            category = "very_short"
        elif caption_len < 150:
            category = "short"
        elif caption_len < 300:
            category = "medium"
        elif caption_len < 500:
            category = "long"
        else:
            category = "very_long"

        length_stats[category]["posts"] += 1
        length_stats[category]["engagement"].append(engagement)

    results = []
    category_order = ["very_short", "short", "medium", "long", "very_long"]
    category_labels = {
        "very_short": "Very Short (<50)",
        "short": "Short (50-150)",
        "medium": "Medium (150-300)",
        "long": "Long (300-500)",
        "very_long": "Very Long (>500)",
    }

    for category in category_order:
        stats = length_stats[category]
        if stats["engagement"]:
            results.append({
                "category": category_labels[category],
                "posts": stats["posts"],
                "avg_engagement": round(sum(stats["engagement"]) / len(stats["engagement"])),
            })

    return results


def calculate_overall_stats(posts: list[dict]) -> dict:
    """Calculate overall statistics."""
    total_likes = sum(p.get("likes", 0) for p in posts)
    total_comments = sum(p.get("comments", 0) for p in posts)
    total_engagement = total_likes + total_comments

    avg_likes = total_likes / len(posts) if posts else 0
    avg_comments = total_comments / len(posts) if posts else 0

    # Get date range
    dates = [p.get("date", "") for p in posts if p.get("date")]
    if dates:
        min_date = min(dates)[:10]
        max_date = max(dates)[:10]
    else:
        min_date = "Unknown"
        max_date = "Unknown"

    return {
        "total_posts": len(posts),
        "total_likes": total_likes,
        "total_comments": total_comments,
        "total_engagement": total_engagement,
        "avg_likes": round(avg_likes),
        "avg_comments": round(avg_comments),
        "date_range": f"{min_date} to {max_date}",
    }


def generate_performance_insights(
    overall: dict,
    top_by_likes: list[dict],
    top_by_comments: list[dict],
    schedule: dict,
    content_types: dict,
    caption_performance: list[dict],
) -> str:
    """Generate the performance insights markdown."""

    # Find best day and hour
    best_day = schedule["by_day"][0] if schedule["by_day"] else {"day": "N/A", "avg_engagement": 0}
    best_hour = schedule["by_hour"][0] if schedule["by_hour"] else {"hour_formatted": "N/A", "avg_engagement": 0}

    # Find best content type
    best_type = max(
        [("Video", content_types["video"]), ("Image", content_types["image"]), ("Carousel", content_types["carousel"])],
        key=lambda x: x[1]["avg_engagement"],
    )

    md = f"""# Performance Insights Dashboard

> Auto-generated from Instagram archive analysis.
> Last updated: {datetime.now().strftime("%Y-%m-%d %H:%M")}

## Overview

| Metric | Value |
|--------|-------|
| Total Posts | {overall['total_posts']:,} |
| Total Likes | {overall['total_likes']:,} |
| Total Comments | {overall['total_comments']:,} |
| Average Likes/Post | {overall['avg_likes']:,} |
| Average Comments/Post | {overall['avg_comments']:,} |
| Date Range | {overall['date_range']} |

---

## Top 10 Posts by Likes

| # | Post | Likes | Comments | Date |
|---|------|-------|----------|------|
"""

    for i, post in enumerate(top_by_likes, 1):
        caption_preview = post["caption"][:40] + "..." if len(post["caption"]) > 40 else post["caption"]
        md += f"| {i} | [{caption_preview or 'No caption'}]({post['url']}) | {post['likes']:,} | {post['comments']:,} | {post['date'][:10]} |\n"

    md += """
---

## Top 10 Posts by Comments

| # | Post | Comments | Likes | Date |
|---|------|----------|-------|------|
"""

    for i, post in enumerate(top_by_comments, 1):
        caption_preview = post["caption"][:40] + "..." if len(post["caption"]) > 40 else post["caption"]
        md += f"| {i} | [{caption_preview or 'No caption'}]({post['url']}) | {post['comments']:,} | {post['likes']:,} | {post['date'][:10]} |\n"

    md += f"""
---

## Best Times to Post

### Best Days

| Day | Posts | Avg Engagement |
|-----|-------|----------------|
"""

    for day in schedule["by_day"]:
        highlight = "**" if day == best_day else ""
        md += f"| {highlight}{day['day']}{highlight} | {day['posts']} | {day['avg_engagement']:,} |\n"

    md += """
### Best Hours (Top 10)

| Hour | Posts | Avg Engagement |
|------|-------|----------------|
"""

    for hour in schedule["by_hour"]:
        md += f"| {hour['hour_formatted']} | {hour['posts']} | {hour['avg_engagement']:,} |\n"

    md += f"""
**Recommendation:** Post on **{best_day['day']}** around **{best_hour['hour_formatted']}** for best engagement.

---

## Content Type Performance

| Type | Posts | Avg Engagement |
|------|-------|----------------|
| Video | {content_types['video']['posts']} | {content_types['video']['avg_engagement']:,} |
| Image | {content_types['image']['posts']} | {content_types['image']['avg_engagement']:,} |
| Carousel | {content_types['carousel']['posts']} | {content_types['carousel']['avg_engagement']:,} |

**Best performer:** {best_type[0]} ({best_type[1]['avg_engagement']:,} avg engagement)

---

## Caption Length Analysis

| Length | Posts | Avg Engagement |
|--------|-------|----------------|
"""

    for item in caption_performance:
        md += f"| {item['category']} | {item['posts']} | {item['avg_engagement']:,} |\n"

    md += """
---

## Key Insights

"""

    # Generate insights
    insights = []

    if best_day["day"] != "N/A":
        insights.append(f"- **Best posting day:** {best_day['day']} ({best_day['avg_engagement']:,} avg engagement)")

    if best_hour["hour_formatted"] != "N/A":
        insights.append(f"- **Best posting time:** {best_hour['hour_formatted']}")

    if best_type[1]["posts"] > 0:
        insights.append(f"- **Best content format:** {best_type[0]}")

    if caption_performance:
        best_caption_len = max(caption_performance, key=lambda x: x["avg_engagement"])
        insights.append(f"- **Best caption length:** {best_caption_len['category']} characters")

    if top_by_likes:
        top_post = top_by_likes[0]
        insights.append(f"- **Most liked post:** {top_post['likes']:,} likes on {top_post['date'][:10]}")

    md += "\n".join(insights)

    md += """

---

## Action Items

Based on this analysis, consider:

1. [ ] Schedule more posts on your best-performing days
2. [ ] Experiment with more {best_type[0].lower()} content
3. [ ] Test caption lengths around the optimal range
4. [ ] Replicate themes from top-performing posts

---

*This file was generated by `scripts/analyze-performance.py`. Run it weekly to track trends.*
"""

    return md


def main():
    """Main entry point."""
    print("\n" + "=" * 60)
    print("PERFORMANCE ANALYSIS")
    print("=" * 60 + "\n")

    # Load archive
    archive_path = get_archive_path()
    if not archive_path.exists():
        print(f"Error: Archive not found at {archive_path}")
        print("Run `python extract-archive.py` first.")
        sys.exit(1)

    archive = load_archive()
    posts = archive.get("posts", [])

    if not posts:
        print("Error: No posts found in archive.")
        sys.exit(1)

    print(f"Analyzing {len(posts)} posts...\n")

    # Run analyses
    print("1. Calculating overall statistics...")
    overall = calculate_overall_stats(posts)

    print("2. Finding top posts by likes...")
    top_by_likes = get_top_posts(posts, "likes")

    print("3. Finding top posts by comments...")
    top_by_comments = get_top_posts(posts, "comments")

    print("4. Analyzing posting schedule...")
    schedule = analyze_posting_schedule(posts)

    print("5. Analyzing content types...")
    content_types = analyze_content_types(posts)

    print("6. Analyzing caption length performance...")
    caption_performance = analyze_caption_length_performance(posts)

    # Generate output
    print("\n7. Generating performance insights...")
    insights = generate_performance_insights(
        overall, top_by_likes, top_by_comments, schedule, content_types, caption_performance
    )

    # Save to brand-vault
    output_path = get_workspace_root() / "brand" / "performance-insights.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(insights)

    print(f"\n✓ Performance insights saved: {output_path}")

    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total posts: {overall['total_posts']}")
    print(f"Total likes: {overall['total_likes']:,}")
    print(f"Total comments: {overall['total_comments']:,}")
    print(f"Average likes: {overall['avg_likes']:,}")

    if schedule["by_day"]:
        print(f"\nBest day to post: {schedule['by_day'][0]['day']}")

    if schedule["by_hour"]:
        print(f"Best hour to post: {schedule['by_hour'][0]['hour_formatted']}")

    print("\n✓ Analysis complete!")


if __name__ == "__main__":
    main()
