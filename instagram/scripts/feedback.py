#!/usr/bin/env python3
"""
Vision Feedback CLI for Ceramic Vision Learning System

A general-purpose human-in-the-loop feedback tool for improving AI predictions
across ALL vision fields: piece_type, glaze_type, surface_qualities, color_appearance,
technique, clay_type, and more.

Usage:
    python3 feedback.py review [--results OUTPUT_FILE] [--field FIELD_NAME]
    python3 feedback.py stats [--field FIELD_NAME]
    python3 feedback.py pending
    python3 feedback.py export [--format fewshot|json]
    python3 feedback.py import FILENAME
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional
from collections import Counter, defaultdict


# =============================================================================
# CONFIGURATION
# =============================================================================

WORKSPACE_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = WORKSPACE_ROOT / "data"
OUTPUT_DIR = WORKSPACE_ROOT / "output"
FEEDBACK_DB = DATA_DIR / "vision-feedback.json"

# All scoreable vision fields
SCORABLE_FIELDS = [
    "piece_type",
    "glaze_type",
    "surface_qualities",
    "color_appearance",
    "technique",
    "clay_type",
    "form_attributes",
    "purpose",
    "product_family",
]

# Score meanings
SCORE_MEANINGS = {
    0: "Completely wrong",
    1: "Wrong category/family",
    2: "Partially correct",
    3: "Completely correct",
}


# =============================================================================
# DATABASE OPERATIONS
# =============================================================================

def load_feedback_db() -> dict:
    """Load the feedback database, creating it if needed."""
    if not FEEDBACK_DB.exists():
        return {
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "feedback_entries": []
        }

    with open(FEEDBACK_DB) as f:
        return json.load(f)


def save_feedback_db(data: dict) -> None:
    """Save the feedback database."""
    with open(FEEDBACK_DB, "w") as f:
        json.dump(data, f, indent=2)


def add_feedback_entry(
    media_filename: str,
    media_path: str,
    ai_prediction: dict,
    human_correction: dict,
    field_scores: dict,
    overall_score: float,
    confidence: str,
    notes: str = ""
) -> str:
    """
    Add a feedback entry to the database.

    Returns:
        The feedback entry ID
    """
    db = load_feedback_db()

    # Generate entry ID
    entry_count = len(db["feedback_entries"])
    entry_id = f"feedback_{entry_count + 1:03d}"

    entry = {
        "id": entry_id,
        "timestamp": datetime.now().isoformat(),
        "media_filename": media_filename,
        "media_path": media_path,
        "ai_prediction": ai_prediction,
        "human_correction": human_correction,
        "field_scores": field_scores,
        "overall_score": overall_score,
        "confidence": confidence,
        "notes": notes
    }

    db["feedback_entries"].append(entry)
    save_feedback_db(db)

    return entry_id


def get_pending_predictions(results_file: str = None) -> list[dict]:
    """
    Get predictions that need feedback.

    Args:
        results_file: Specific results file to load, or latest if None

    Returns:
        List of prediction dicts
    """
    if results_file:
        results_path = Path(results_file)
        if not results_path.is_absolute():
            results_path = OUTPUT_DIR / results_file
    else:
        # Find latest results file
        results_files = sorted(OUTPUT_DIR.glob("results_*.json"), reverse=True)
        if not results_files:
            return []
        results_path = results_files[0]

    if not results_path.exists():
        return []

    with open(results_path) as f:
        data = json.load(f)

    # Extract predictions from posts
    predictions = []
    db = load_feedback_db()
    feedback_filenames = {e["media_filename"] for e in db["feedback_entries"]}

    for post in data.get("posts", []):
        media_path = post.get("media_path", "")
        media_filename = Path(media_path).name

        # Skip if already has feedback
        if media_filename in feedback_filenames:
            continue

        analysis = post.get("analysis", {})
        if not analysis:
            continue

        predictions.append({
            "media_filename": media_filename,
            "media_path": media_path,
            "media_type": post.get("media_type", "unknown"),
            "caption": post.get("caption", ""),
            "analysis": analysis
        })

    return predictions


# =============================================================================
# REVIEW INTERFACE
# =============================================================================

def parse_field_value(input_value: str, field_name: str) -> any:
    """
    Parse user input into the appropriate type for the field.

    Handles:
    - Lists (comma-separated)
    - None values (empty, "null", "none", "✓")
    - Strings
    """
    if not input_value or input_value.lower() in ["null", "none", "✓", "n/a", "-"]:
        return None

    # List fields
    if field_name in ["surface_qualities", "form_attributes", "primary_colors",
                      "secondary_colors", "safety_flags"]:
        items = [item.strip() for item in input_value.split(",")]
        return [item for item in items if item]

    return input_value


def interactive_review(predictions: list[dict], field_filter: str = None) -> None:
    """
    Interactive review of predictions with user feedback.

    Args:
        predictions: List of prediction dicts to review
        field_filter: Only review this specific field
    """
    if not predictions:
        print("No predictions to review.")
        return

    print(f"\nFound {len(predictions)} prediction(s) to review.\n")

    for idx, pred in enumerate(predictions, 1):
        filename = pred["media_filename"]
        analysis = pred["analysis"]

        print("=" * 70)
        print(f"{idx}. {filename}")
        print("=" * 70)

        print("\n📸 AI Prediction:")
        display_prediction(analysis)

        if field_filter:
            print(f"\n🔍 Reviewing field: {field_filter}")
            print("Press Enter to accept, or provide correction:\n")

            # Single field review
            current_value = analysis.get(field_filter, None)
            display_format = format_field_value(current_value, field_filter)
            user_input = input(f"{field_filter} [{display_format}]: ").strip()

            if user_input and user_input not in ["✓", "✓", ""]:
                corrected_value = parse_field_value(user_input, field_filter)
            else:
                corrected_value = current_value

            # Score this field
            score = prompt_for_score(field_filter, current_value, corrected_value)

            # Build correction dict
            human_correction = {field_filter: corrected_value}
            field_scores = {field_filter: score}
            overall_score = score

        else:
            print("\n📝 Enter corrections (press Enter or type ✓ to accept AI prediction):\n")

            # Full review
            human_correction = {}
            field_scores = {}

            # Review each scorable field
            for field in SCORABLE_FIELDS:
                if field not in analysis:
                    continue

                current_value = analysis.get(field)
                display_format = format_field_value(current_value, field)

                prompt = f"{field} [{display_format}]: "
                user_input = input(prompt).strip()

                if user_input and user_input not in ["✓", ""]:
                    corrected_value = parse_field_value(user_input, field)
                    human_correction[field] = corrected_value
                else:
                    human_correction[field] = current_value

            # Score each corrected field
            print("\n📊 Scores (0-3, press Enter for default):\n")
            for field in SCORABLE_FIELDS:
                if field not in analysis:
                    continue

                current = analysis.get(field)
                corrected = human_correction.get(field)

                if current == corrected:
                    default_score = 3
                    score_prompt = f"  {field} [3]: "
                else:
                    default_score = calculate_default_score(current, corrected)
                    score_prompt = f"  {field} [{default_score}]: "

                user_input = input(score_prompt).strip()
                if user_input:
                    score = int(user_input)
                else:
                    score = default_score

                field_scores[field] = score

            overall_score = sum(field_scores.values()) / len(field_scores) if field_scores else 0

        # Confidence
        print()
        confidence = input("Confidence (certain/probably/maybe) [certain]: ").strip().lower()
        if not confidence or confidence not in ["certain", "probably", "maybe"]:
            confidence = "certain"

        # Optional notes
        notes = input("Notes (optional): ").strip()

        # Save feedback
        entry_id = add_feedback_entry(
            media_filename=filename,
            media_path=pred["media_path"],
            ai_prediction=analysis,
            human_correction=human_correction,
            field_scores=field_scores,
            overall_score=round(overall_score, 1),
            confidence=confidence,
            notes=notes
        )

        print(f"\n✓ Saved feedback entry: {entry_id}")
        print(f"  Overall score: {overall_score:.1f}/3.0\n")

        # Continue or stop
        if idx < len(predictions):
            cont = input("Press Enter to continue, or 'q' to quit: ").strip().lower()
            if cont == "q":
                break

    print("\n" + "=" * 70)
    print("Review complete!")
    print("=" * 70)


def display_prediction(analysis: dict) -> None:
    """Display a prediction in a formatted way."""
    fields_to_display = [
        ("Piece Type", "piece_type"),
        ("Glaze", "glaze_type"),
        ("Surface", "surface_qualities"),
        ("Color", "color_appearance"),
        ("Technique", "technique"),
        ("Clay", "clay_type"),
        ("Form", "form_attributes"),
        ("Purpose", "purpose"),
        ("Product", "product_family"),
    ]

    for label, field in fields_to_display:
        value = analysis.get(field)
        if value is not None and value != [] and value != "":
            print(f"  {label}: {format_field_value(value, field)}")


def format_field_value(value: any, field_name: str) -> str:
    """Format a field value for display."""
    if value is None:
        return "?"

    if isinstance(value, list):
        if not value:
            return "[]"
        return ", ".join(value)

    return str(value)


def prompt_for_score(field_name: str, ai_value: any, corrected_value: any) -> int:
    """Prompt user for a score on a single field."""
    if ai_value == corrected_value:
        default = 3
    else:
        default = calculate_default_score(ai_value, corrected_value)

    prompt = f"  Score (0={SCORE_MEANINGS[0]}, 1={SCORE_MEANINGS[1]}, 2={SCORE_MEANINGS[2]}, 3={SCORE_MEANINGS[3]}) [{default}]: "
    user_input = input(prompt).strip()

    if user_input:
        return int(user_input)
    return default


def calculate_default_score(ai_value: any, corrected_value: any) -> int:
    """Calculate a reasonable default score based on the difference."""
    if ai_value == corrected_value:
        return 3

    # Completely different values
    if ai_value is None or corrected_value is None:
        return 0

    # For lists, check overlap
    if isinstance(ai_value, list) and isinstance(corrected_value, list):
        if not ai_value or not corrected_value:
            return 0
        overlap = set(ai_value) & set(corrected_value)
        if overlap:
            return 2  # Partial overlap
        return 1  # Same type, no overlap

    # For strings, check if same family/category
    if isinstance(ai_value, str) and isinstance(corrected_value, str):
        ai_lower = ai_value.lower()
        corrected_lower = corrected_value.lower()

        # Check for word overlap
        ai_words = set(ai_lower.replace("_", " ").replace("-", " ").split())
        corrected_words = set(corrected_lower.replace("_", " ").replace("-", " ").split())

        if ai_words & corrected_words:
            return 1  # Same family

        return 0  # Completely different

    return 1


# =============================================================================
# STATISTICS
# =============================================================================

def show_stats(field_filter: str = None) -> None:
    """Display performance statistics."""
    db = load_feedback_db()
    entries = db["feedback_entries"]

    if not entries:
        print("No feedback data yet. Use 'review' command to add feedback.")
        return

    print("\n" + "=" * 70)
    print("Ceramic Vision Performance Dashboard")
    print("=" * 70)

    # Overall summary
    total = len(entries)
    print("\n📊 Overall Summary")
    print(f"   Total feedback entries: {total}")

    if field_filter:
        print(f"   Filtering by field: {field_filter}")

    # Calculate per-field stats
    field_stats = calculate_field_stats(entries, field_filter)

    print("\n📈 Per-Field Accuracy")
    print(f"{'Field':<20} | {'Last 5':>8} | {'Last 10':>8} | {'All Time':>9} | {'Trend':>6}")
    print("-" * 70)

    for field, stats in field_stats.items():
        last_5 = stats["last_5"]
        last_10 = stats["last_10"]
        all_time = stats["all_time"]
        trend = stats["trend"]

        trend_symbol = {
            "up": "↗",
            "down": "↘",
            "stable": "→"
        }.get(trend, "→")

        print(f"{field:<20} | {last_5:>7.2f}/3 | {last_10:>7.2f}/3 | {all_time:>8.2f}/3 | {trend:>6}")

    # Show confusion patterns
    if not field_filter:
        show_confusion_matrices(entries)

    # Show learned patterns
    show_learned_patterns(entries)

    print("\n" + "=" * 70)


def calculate_field_stats(entries: list, field_filter: str = None) -> dict:
    """Calculate statistics for each field."""
    stats = {}

    for field in SCORABLE_FIELDS:
        if field_filter and field != field_filter:
            continue

        scores = []
        timestamps = []

        for entry in entries:
            if field in entry.get("field_scores", {}):
                scores.append(entry["field_scores"][field])
                timestamps.append(entry["timestamp"])

        if not scores:
            continue

        # Calculate averages
        last_5 = scores[-5:] if len(scores) >= 5 else scores
        last_10 = scores[-10:] if len(scores) >= 10 else scores

        stats[field] = {
            "last_5": sum(last_5) / len(last_5),
            "last_10": sum(last_10) / len(last_10),
            "all_time": sum(scores) / len(scores),
            "trend": calculate_trend(scores)
        }

    return stats


def calculate_trend(scores: list) -> str:
    """Calculate trend direction from scores."""
    if len(scores) < 3:
        return "stable"

    first_half = scores[:len(scores)//2]
    second_half = scores[len(scores)//2:]

    first_avg = sum(first_half) / len(first_half)
    second_avg = sum(second_half) / len(second_half)

    if second_avg > first_avg + 0.2:
        return "up"
    elif second_avg < first_avg - 0.2:
        return "down"
    return "stable"


def show_confusion_matrices(entries: list) -> None:
    """Show common confusion patterns."""
    print("\n🔀 Confusion Matrix (Most Common Errors)")
    print()

    # Track field-specific errors
    field_errors: dict[str, Counter] = defaultdict(Counter)

    for entry in entries:
        ai = entry.get("ai_prediction", {})
        human = entry.get("human_correction", {})

        for field in SCORABLE_FIELDS:
            ai_val = str(ai.get(field) or "null")
            human_val = str(human.get(field) or "null")

            if ai_val != human_val:
                key = f"{ai_val} → {human_val}"
                field_errors[field][key] += 1

    # Show top errors per field
    for field, errors in field_errors.items():
        if not errors:
            continue

        print(f"{field}:")
        for error, count in errors.most_common(3):
            print(f"  - {error}: {count} error(s)")
        print()


def show_learned_patterns(entries: list) -> None:
    """Show learned patterns from high-confidence corrections."""
    print("🧠 Top Learned Patterns")
    print()

    # Get high-confidence, high-score entries
    high_quality = [
        e for e in entries
        if e.get("overall_score", 0) >= 2.5
        and e.get("confidence") in ["certain", "probably"]
    ]

    # Find common patterns
    patterns = Counter()

    for entry in high_quality:
        human = entry.get("human_correction", {})

        # Create pattern signatures
        glaze = human.get("glaze_type")
        surface = human.get("surface_qualities", [])
        piece = human.get("piece_type")

        if glaze and surface:
            patterns[f"{surface} → {glaze}"] += 1

        if piece:
            surface_sig = ", ".join(surface) if surface else "smooth"
            patterns[f"{surface_sig} → {piece}"] += 1

    # Show top patterns
    for pattern, count in patterns.most_common(5):
        print(f"  ✓ {pattern} ({count} verified)")

    print()


# =============================================================================
# PENDING LIST
# =============================================================================

def show_pending() -> None:
    """Show items that need feedback."""
    predictions = get_pending_predictions()

    if not predictions:
        print("✅ All predictions have feedback!")
        return

    print(f"\n📋 Pending Feedback ({len(predictions)} items)")
    print("=" * 70)

    for idx, pred in enumerate(predictions, 1):
        analysis = pred["analysis"]
        piece = analysis.get("piece_type", "?")
        glaze = analysis.get("glaze_type", "?")

        print(f"{idx}. {pred['media_filename']}")
        print(f"    Predicted: {piece}, {glaze}")

    print("=" * 70)


# =============================================================================
# EXPORT/IMPORT
# =============================================================================

def export_examples(format_type: str = "fewshot") -> None:
    """Export verified examples for few-shot learning."""
    db = load_feedback_db()
    entries = db["feedback_entries"]

    # Filter high-quality entries
    high_quality = [
        e for e in entries
        if e.get("overall_score", 0) >= 2.5
        and e.get("confidence") in ["certain", "probably"]
    ]

    if not high_quality:
        print("No high-quality examples to export.")
        return

    # Sort by timestamp (most recent first)
    high_quality.sort(key=lambda x: x["timestamp"], reverse=True)

    if format_type == "fewshot":
        print("\n## Few-Shot Examples for Vision Prompt")
        print()

        for i, entry in enumerate(high_quality[:10], 1):
            correction = entry["human_correction"]
            print(f"Example {i}:")
            print(f"- Form: {correction.get('piece_type', 'unknown')}")
            print(f"- Glaze: {correction.get('glaze_type', 'unknown')}")
            print(f"- Surface: {correction.get('surface_qualities', [])}")
            print(f"- Color: {correction.get('color_appearance', 'unknown')}")
            print(f"- Technique: {correction.get('technique', 'unknown')}")
            print(f"- Clay: {correction.get('clay_type', 'unknown')}")
            print()

    elif format_type == "json":
        output = {
            "version": "1.0",
            "exported_at": datetime.now().isoformat(),
            "examples": [
                {
                    "media_filename": e["media_filename"],
                    "correction": e["human_correction"],
                    "score": e["overall_score"]
                }
                for e in high_quality
            ]
        }

        output_path = OUTPUT_DIR / f"fewshot_examples_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_path, "w") as f:
            json.dump(output, f, indent=2)

        print(f"✓ Exported {len(high_quality)} examples to: {output_path}")


def import_feedback(filename: str) -> None:
    """Import feedback entries from a file."""
    import_path = Path(filename)
    if not import_path.is_absolute():
        import_path = Path.cwd() / filename

    if not import_path.exists():
        print(f"File not found: {filename}")
        return

    with open(import_path) as f:
        data = json.load(f)

    count = 0
    db = load_feedback_db()

    for entry in data.get("feedback_entries", data.get("examples", [])):
        # Generate new ID
        entry_count = len(db["feedback_entries"])
        entry["id"] = f"feedback_{entry_count + 1:03d}"

        db["feedback_entries"].append(entry)
        count += 1

    save_feedback_db(db)
    print(f"✓ Imported {count} feedback entries from: {filename}")


# =============================================================================
# MAIN CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Vision Feedback CLI for Ceramic Vision Learning",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Review recent predictions
    python3 feedback.py review

    # Review specific results file
    python3 feedback.py review --results output/results_20260314_100622.json

    # Review only glaze predictions
    python3 feedback.py review --field glaze_type

    # Show statistics
    python3 feedback.py stats

    # Show statistics for specific field
    python3 feedback.py stats --field piece_type

    # Show pending items
    python3 feedback.py pending

    # Export few-shot examples
    python3 feedback.py export --format fewshot
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Review command
    review_parser = subparsers.add_parser("review", help="Review predictions and provide feedback")
    review_parser.add_argument("--results", help="Specific results file to review")
    review_parser.add_argument("--field", choices=SCORABLE_FIELDS, help="Only review this field")

    # Stats command
    stats_parser = subparsers.add_parser("stats", help="Show performance statistics")
    stats_parser.add_argument("--field", choices=SCORABLE_FIELDS, help="Filter by field")

    # Pending command
    subparsers.add_parser("pending", help="Show items needing feedback")

    # Export command
    export_parser = subparsers.add_parser("export", help="Export verified examples")
    export_parser.add_argument("--format", choices=["fewshot", "json"], default="fewshot",
                              help="Export format")

    # Import command
    import_parser = subparsers.add_parser("import", help="Import feedback from file")
    import_parser.add_argument("filename", help="File to import")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    if args.command == "review":
        predictions = get_pending_predictions(args.results)
        interactive_review(predictions, args.field)

    elif args.command == "stats":
        show_stats(args.field)

    elif args.command == "pending":
        show_pending()

    elif args.command == "export":
        export_examples(args.format)

    elif args.command == "import":
        import_feedback(args.filename)


if __name__ == "__main__":
    main()
