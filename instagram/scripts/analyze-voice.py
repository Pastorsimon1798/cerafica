#!/usr/bin/env python3
"""
Analyze Voice Patterns from Instagram Archive

Analyzes captions to identify voice patterns:
- Caption length patterns
- Emoji usage
- Sentence structure
- Tone markers
- Top performing captions (by engagement)

Usage:
    python analyze-voice.py

Output:
    Updates brand/voice-rules.md with real examples
"""

import re
import sys
from collections import Counter
from pathlib import Path

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent / "lib"))

from instaloader_utils import (
    get_archive_path,
    load_archive,
    get_workspace_root,
)


def analyze_caption_length(posts: list[dict]) -> dict:
    """Analyze caption length patterns."""
    lengths = [len(p.get("caption", "") or "") for p in posts]
    if not lengths:
        return {"average": 0, "min": 0, "max": 0, "distribution": {}}

    avg = sum(lengths) / len(lengths)
    min_len = min(lengths)
    max_len = max(lengths)

    # Categorize lengths
    categories = {
        "very_short": 0,  # < 50 chars
        "short": 0,       # 50-150 chars
        "medium": 0,      # 150-300 chars
        "long": 0,        # 300-500 chars
        "very_long": 0,   # > 500 chars
    }

    for length in lengths:
        if length < 50:
            categories["very_short"] += 1
        elif length < 150:
            categories["short"] += 1
        elif length < 300:
            categories["medium"] += 1
        elif length < 500:
            categories["long"] += 1
        else:
            categories["very_long"] += 1

    return {
        "average": round(avg),
        "min": min_len,
        "max": max_len,
        "distribution": categories,
    }


def analyze_emoji_usage(posts: list[dict]) -> dict:
    """Analyze emoji usage patterns."""
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "]+",
        flags=re.UNICODE,
    )

    all_emojis = []
    posts_with_emojis = 0

    for post in posts:
        caption = post.get("caption", "") or ""
        emojis = emoji_pattern.findall(caption)
        if emojis:
            posts_with_emojis += 1
            all_emojis.extend(emojis)

    emoji_counter = Counter(all_emojis)

    return {
        "total_emojis_used": len(all_emojis),
        "posts_with_emojis": posts_with_emojis,
        "emoji_percentage": round(posts_with_emojis / len(posts) * 100) if posts else 0,
        "top_emojis": emoji_counter.most_common(10),
        "unique_emojis": len(emoji_counter),
    }


def analyze_sentence_structure(posts: list[dict]) -> dict:
    """Analyze sentence structure patterns."""
    sentence_counts = []
    question_marks = 0
    exclamation_marks = 0
    multi_sentence = 0

    for post in posts:
        caption = post.get("caption", "") or ""
        if not caption:
            continue

        # Count sentences (rough approximation)
        sentences = [s.strip() for s in caption.replace("!", ".").replace("?", ".").split(".") if s.strip()]
        sentence_counts.append(len(sentences))

        if "?" in caption:
            question_marks += 1
        if "!" in caption:
            exclamation_marks += 1
        if len(sentences) > 2:
            multi_sentence += 1

    avg_sentences = sum(sentence_counts) / len(sentence_counts) if sentence_counts else 0

    return {
        "average_sentences": round(avg_sentences, 1),
        "posts_with_questions": question_marks,
        "posts_with_exclamations": exclamation_marks,
        "multi_sentence_posts": multi_sentence,
        "question_percentage": round(question_marks / len(posts) * 100) if posts else 0,
        "exclamation_percentage": round(exclamation_marks / len(posts) * 100) if posts else 0,
    }


def get_top_performing_captions(posts: list[dict], n: int = 10) -> list[dict]:
    """Get top performing captions by engagement."""
    # Sort by engagement (likes + comments)
    sorted_posts = sorted(
        posts,
        key=lambda p: p.get("likes", 0) + p.get("comments", 0),
        reverse=True,
    )

    top_posts = []
    for post in sorted_posts[:n]:
        caption = post.get("caption", "") or ""
        top_posts.append({
            "caption": caption,
            "caption_length": len(caption),
            "likes": post.get("likes", 0),
            "comments": post.get("comments", 0),
            "engagement": post.get("likes", 0) + post.get("comments", 0),
            "url": post.get("url", ""),
            "date": post.get("date", "")[:10],
        })

    return top_posts


def get_low_performing_captions(posts: list[dict], n: int = 5) -> list[dict]:
    """Get lower performing captions for comparison."""
    sorted_posts = sorted(
        posts,
        key=lambda p: p.get("likes", 0) + p.get("comments", 0),
    )

    low_posts = []
    for post in sorted_posts[:n]:
        caption = post.get("caption", "") or ""
        low_posts.append({
            "caption": caption,
            "caption_length": len(caption),
            "likes": post.get("likes", 0),
            "comments": post.get("comments", 0),
            "engagement": post.get("likes", 0) + post.get("comments", 0),
            "url": post.get("url", ""),
            "date": post.get("date", "")[:10],
        })

    return low_posts


def generate_voice_rules_update(analysis: dict, top_captions: list[dict], low_captions: list[dict]) -> str:
    """Generate the voice rules markdown update."""

    md = """# Voice Rules - Analyzed from Your Content

> Auto-generated from Instagram archive analysis.
> Last updated: {date}

## Your Voice at a Glance

Based on analysis of {total_posts} posts:

| Metric | Value |
|--------|-------|
| Average caption length | {avg_length} characters |
| Posts with emojis | {emoji_pct}% |
| Average sentences per post | {avg_sentences} |
| Posts with questions | {question_pct}% |
| Posts with exclamations | {exclamation_pct}% |

## Caption Length Guidelines

Your caption style analysis:

| Length | Count | Percentage |
|--------|-------|------------|
| Very short (<50 chars) | {very_short} | {very_short_pct}% |
| Short (50-150 chars) | {short} | {short_pct}% |
| Medium (150-300 chars) | {medium} | {medium_pct}% |
| Long (300-500 chars) | {long} | {long_pct}% |
| Very long (>500 chars) | {very_long} | {very_long_pct}% |

**Recommendation:** Your best-performing posts tend to be {best_length}.

## Emoji Usage

You use emojis in {emoji_pct}% of your posts.

**Top emojis you use:**
{emoji_list}

## Top Performing Captions (High Engagement)

These captions resonated most with your audience:

""".format(
        date=analysis.get("date", "Unknown"),
        total_posts=analysis.get("total_posts", 0),
        avg_length=analysis["length"]["average"],
        emoji_pct=analysis["emoji"]["emoji_percentage"],
        avg_sentences=analysis["sentence"]["average_sentences"],
        question_pct=analysis["sentence"]["question_percentage"],
        exclamation_pct=analysis["sentence"]["exclamation_percentage"],
        very_short=analysis["length"]["distribution"]["very_short"],
        short=analysis["length"]["distribution"]["short"],
        medium=analysis["length"]["distribution"]["medium"],
        long=analysis["length"]["distribution"]["long"],
        very_long=analysis["length"]["distribution"]["very_long"],
        very_short_pct=round(analysis["length"]["distribution"]["very_short"] / analysis["total_posts"] * 100) if analysis["total_posts"] else 0,
        short_pct=round(analysis["length"]["distribution"]["short"] / analysis["total_posts"] * 100) if analysis["total_posts"] else 0,
        medium_pct=round(analysis["length"]["distribution"]["medium"] / analysis["total_posts"] * 100) if analysis["total_posts"] else 0,
        long_pct=round(analysis["length"]["distribution"]["long"] / analysis["total_posts"] * 100) if analysis["total_posts"] else 0,
        very_long_pct=round(analysis["length"]["distribution"]["very_long"] / analysis["total_posts"] * 100) if analysis["total_posts"] else 0,
        best_length="medium length (150-300 characters)" if analysis["length"]["distribution"]["medium"] >= analysis["length"]["distribution"]["short"] else "short (50-150 characters)",
        emoji_list="\n".join([f"- {emoji} ({count} times)" for emoji, count in analysis["emoji"]["top_emojis"][:5]]) or "- No emojis detected",
    )

    for i, post in enumerate(top_captions[:5], 1):
        md += f"""
### #{i} - {post['engagement']} engagements

> "{post['caption'][:200]}{'...' if len(post['caption']) > 200 else ''}"

- **Likes:** {post['likes']:,} | **Comments:** {post['comments']:,}
- **Length:** {post['caption_length']} characters
- **Date:** {post['date']}
- **Link:** [{post['url']}]({post['url']})

"""

    md += """## Lower Performing Captions (For Comparison)

These captions had less engagement:

"""
    for i, post in enumerate(low_captions[:3], 1):
        md += f"""
### #{i} - {post['engagement']} engagements

> "{post['caption'][:150]}{'...' if len(post['caption']) > 150 else ''}"

- **Likes:** {post['likes']:,} | **Comments:** {post['comments']:,}
- **Length:** {post['caption_length']} characters

"""

    md += """## Voice Patterns Summary

Based on this analysis, your authentic voice includes:

1. **Caption Style:** [Update based on patterns]
2. **Emoji Usage:** [Update based on patterns]
3. **Engagement Drivers:** [Update based on what made top posts work]

---

*This file was generated by `scripts/analyze-voice.py`. Run it periodically to update with new content.*
"""

    return md


def main():
    """Main entry point."""
    print("\n" + "=" * 60)
    print("VOICE PATTERN ANALYSIS")
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
    print("1. Analyzing caption length patterns...")
    length_analysis = analyze_caption_length(posts)

    print("2. Analyzing emoji usage...")
    emoji_analysis = analyze_emoji_usage(posts)

    print("3. Analyzing sentence structure...")
    sentence_analysis = analyze_sentence_structure(posts)

    print("4. Finding top performing captions...")
    top_captions = get_top_performing_captions(posts)

    print("5. Finding lower performing captions...")
    low_captions = get_low_performing_captions(posts)

    # Compile analysis
    analysis = {
        "date": archive.get("metadata", {}).get("extracted_at", "Unknown"),
        "total_posts": len(posts),
        "length": length_analysis,
        "emoji": emoji_analysis,
        "sentence": sentence_analysis,
    }

    # Generate output
    print("\n6. Generating voice rules update...")
    voice_rules = generate_voice_rules_update(analysis, top_captions, low_captions)

    # Save to brand-vault
    output_path = get_workspace_root() / "brand" / "voice-rules.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(voice_rules)

    print(f"\n✓ Voice rules updated: {output_path}")

    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total posts analyzed: {len(posts)}")
    print(f"Average caption length: {length_analysis['average']} characters")
    print(f"Emoji usage: {emoji_analysis['emoji_percentage']}% of posts")
    print(f"Average sentences: {sentence_analysis['average_sentences']}")
    print(f"\nTop performing post: {top_captions[0]['engagement']} engagements")
    print(f"  Caption: \"{top_captions[0]['caption'][:80]}...\"")

    print("\n✓ Analysis complete!")


if __name__ == "__main__":
    main()
