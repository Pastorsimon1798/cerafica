#!/usr/bin/env python3
"""
Analyze Hashtag Performance from Instagram Archive

Analyzes hashtag usage and performance:
- Most used hashtags
- Hashtags with highest average engagement
- Hashtag combinations that work
- Unused opportunities

Usage:
    python analyze-hashtags.py

Output:
    Updates shared/hashtag-library.md with optimized sets
"""

import sys
from collections import Counter, defaultdict
from pathlib import Path

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent / "lib"))

from instaloader_utils import (
    get_archive_path,
    load_archive,
    get_workspace_root,
)


def analyze_hashtag_frequency(posts: list[dict]) -> dict:
    """Analyze how often each hashtag is used."""
    all_hashtags = []

    for post in posts:
        hashtags = post.get("hashtags", [])
        all_hashtags.extend(hashtags)

    counter = Counter(all_hashtags)

    return {
        "total_hashtags_used": len(all_hashtags),
        "unique_hashtags": len(counter),
        "frequency": counter.most_common(50),
    }


def analyze_hashtag_performance(posts: list[dict]) -> dict:
    """Analyze which hashtags correlate with high engagement."""
    hashtag_stats = defaultdict(lambda: {"likes": [], "comments": [], "count": 0})

    for post in posts:
        hashtags = post.get("hashtags", [])
        likes = post.get("likes", 0)
        comments = post.get("comments", 0)

        for tag in hashtags:
            hashtag_stats[tag]["likes"].append(likes)
            hashtag_stats[tag]["comments"].append(comments)
            hashtag_stats[tag]["count"] += 1

    # Calculate averages
    performance = []
    for tag, stats in hashtag_stats.items():
        if stats["count"] >= 2:  # Only include hashtags used at least twice
            avg_likes = sum(stats["likes"]) / len(stats["likes"])
            avg_comments = sum(stats["comments"]) / len(stats["comments"])
            avg_engagement = avg_likes + avg_comments

            performance.append({
                "hashtag": tag,
                "count": stats["count"],
                "avg_likes": round(avg_likes),
                "avg_comments": round(avg_comments),
                "avg_engagement": round(avg_engagement),
                "total_engagement": sum(stats["likes"]) + sum(stats["comments"]),
            })

    # Sort by average engagement
    performance.sort(key=lambda x: x["avg_engagement"], reverse=True)

    return {
        "by_engagement": performance[:30],
        "by_frequency": sorted(performance, key=lambda x: x["count"], reverse=True)[:30],
    }


def analyze_hashtag_combinations(posts: list[dict]) -> list[dict]:
    """Analyze which hashtag combinations appear together."""
    combo_stats = defaultdict(lambda: {"count": 0, "total_engagement": 0})

    for post in posts:
        hashtags = post.get("hashtags", [])
        if len(hashtags) < 2:
            continue

        engagement = post.get("likes", 0) + post.get("comments", 0)

        # Create pairs
        for i, tag1 in enumerate(hashtags):
            for tag2 in hashtags[i + 1:]:
                combo = tuple(sorted([tag1, tag2]))
                combo_stats[combo]["count"] += 1
                combo_stats[combo]["total_engagement"] += engagement

    # Calculate averages and format
    combinations = []
    for combo, stats in combo_stats.items():
        if stats["count"] >= 2:  # Only include combinations used multiple times
            combinations.append({
                "hashtags": combo,
                "count": stats["count"],
                "avg_engagement": round(stats["total_engagement"] / stats["count"]),
            })

    combinations.sort(key=lambda x: x["avg_engagement"], reverse=True)
    return combinations[:20]


def calculate_optimal_hashtag_count(posts: list[dict]) -> dict:
    """Analyze the optimal number of hashtags per post."""
    count_performance = defaultdict(lambda: {"likes": [], "comments": []})

    for post in posts:
        hashtag_count = len(post.get("hashtags", []))
        likes = post.get("likes", 0)
        comments = post.get("comments", 0)

        count_performance[hashtag_count]["likes"].append(likes)
        count_performance[hashtag_count]["comments"].append(comments)

    results = []
    for count, stats in count_performance.items():
        if stats["likes"]:
            avg_engagement = (sum(stats["likes"]) + sum(stats["comments"])) / len(stats["likes"])
            results.append({
                "hashtag_count": count,
                "post_count": len(stats["likes"]),
                "avg_engagement": round(avg_engagement),
            })

    results.sort(key=lambda x: x["avg_engagement"], reverse=True)
    return results


def generate_hashtag_library_update(
    frequency: dict,
    performance: dict,
    combinations: list[dict],
    optimal_count: list[dict],
    total_posts: int,
) -> str:
    """Generate the hashtag library markdown update."""

    # Find best performing hashtags
    best_performing = performance["by_engagement"][:15]
    most_used = performance["by_frequency"][:15]

    # Determine optimal hashtag count
    if optimal_count:
        best_count = optimal_count[0]["hashtag_count"]
    else:
        best_count = "N/A"

    md = f"""# Hashtag Library - Optimized for Your Account

> Auto-generated from Instagram archive analysis.
> Last updated based on {total_posts} posts.

## Your Hashtag Strategy

**Optimal hashtag count:** {best_count} hashtags per post (based on your best-performing content)

### How to Use This Library

1. **Core Set (5-7 tags):** Always include these - they're your best performers
2. **Topic Sets (3-5 tags):** Choose based on post content
3. **Discovery Tags (2-3 tags):** Add for reach to new audiences

---

## Your Top Performing Hashtags

These hashtags have the highest average engagement on YOUR posts:

| Hashtag | Uses | Avg Engagement |
|---------|------|----------------|
"""

    for item in best_performing[:15]:
        md += f"| {item['hashtag']} | {item['count']} | {item['avg_engagement']:,} |\n"

    md += """
## Most Frequently Used

These are the hashtags you use most often:

| Hashtag | Uses | Avg Engagement |
|---------|------|----------------|
"""

    for item in most_used[:15]:
        md += f"| {item['hashtag']} | {item['count']} | {item['avg_engagement']:,} |\n"

    md += """
## Best Hashtag Combinations

These hashtag pairs appear together on your highest-engagement posts:

| Combination | Uses | Avg Engagement |
|-------------|------|----------------|
"""

    for combo in combinations[:10]:
        md += f"| {combo['hashtags'][0]} + {combo['hashtags'][1]} | {combo['count']} | {combo['avg_engagement']:,} |\n"

    md += """
## Hashtag Sets by Content Type

### Finished Pieces
```
"""

    # Extract relevant hashtags for finished pieces
    finished_tags = [t["hashtag"] for t in best_performing if any(
        kw in t["hashtag"] for kw in ["ceramic", "pottery", "handmade", "stoneware", "clay", "bowl", "vase", "mug"]
    )][:10]

    for tag in finished_tags:
        md += f"#{tag} "

    md += """
```

### Process/Studio Content
```
"""

    process_tags = [t["hashtag"] for t in best_performing if any(
        kw in t["hashtag"] for kw in ["process", "studio", "wip", "maker", "potter", "wheel", "throwing"]
    )][:10]

    for tag in process_tags:
        md += f"#{tag} "

    md += """
```

### General/Discovery
```
"""

    # Top performing general tags
    general_tags = [t["hashtag"] for t in best_performing if t not in finished_tags and t not in process_tags][:8]

    for tag in general_tags:
        md += f"#{tag} "

    md += """
```

---

## Hashtag Count Analysis

How many hashtags should you use? Here's what YOUR data shows:

| Hashtag Count | Posts | Avg Engagement |
|---------------|-------|----------------|
"""

    for item in optimal_count[:10]:
        md += f"| {item['hashtag_count']} | {item['post_count']} | {item['avg_engagement']:,} |\n"

    md += f"""
## Complete Hashtag List

All unique hashtags you've used ({frequency['unique_hashtags']} total):

"""

    # List all hashtags in columns
    all_tags = [tag for tag, count in frequency["frequency"]]
    cols = 3
    rows = (len(all_tags) + cols - 1) // cols

    md += "| "
    for i, tag in enumerate(all_tags[:30]):
        if i > 0 and i % 10 == 0:
            md += "|\n| "
        md += f"#{tag} "
    md += "|\n"

    md += """
---

*This file was generated by `scripts/analyze-hashtags.py`. Run it periodically to update with new content.*
"""

    return md


def main():
    """Main entry point."""
    print("\n" + "=" * 60)
    print("HASHTAG PERFORMANCE ANALYSIS")
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
    print("1. Analyzing hashtag frequency...")
    frequency = analyze_hashtag_frequency(posts)

    print("2. Analyzing hashtag performance...")
    performance = analyze_hashtag_performance(posts)

    print("3. Analyzing hashtag combinations...")
    combinations = analyze_hashtag_combinations(posts)

    print("4. Analyzing optimal hashtag count...")
    optimal_count = calculate_optimal_hashtag_count(posts)

    # Generate output
    print("\n5. Generating hashtag library update...")
    hashtag_library = generate_hashtag_library_update(
        frequency, performance, combinations, optimal_count, len(posts)
    )

    # Save to shared folder
    output_path = get_workspace_root() / "shared" / "hashtag-library.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(hashtag_library)

    print(f"\n✓ Hashtag library updated: {output_path}")

    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total posts analyzed: {len(posts)}")
    print(f"Total hashtag uses: {frequency['total_hashtags_used']:,}")
    print(f"Unique hashtags: {frequency['unique_hashtags']}")

    if optimal_count:
        print(f"\nOptimal hashtag count: {optimal_count[0]['hashtag_count']} per post")

    if performance["by_engagement"]:
        top = performance["by_engagement"][0]
        print(f"\nBest performing hashtag: #{top['hashtag']}")
        print(f"  - Used {top['count']} times")
        print(f"  - Average engagement: {top['avg_engagement']:,}")

    print("\n✓ Analysis complete!")


if __name__ == "__main__":
    main()
