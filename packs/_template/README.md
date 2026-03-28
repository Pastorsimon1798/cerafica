# Domain Pack Template

This is the starting point for creating a domain pack for your product type.

## What is a Domain Pack?

A domain pack contains all the product-specific knowledge that the content pipeline needs:
- **Vision prompt** — tells the AI how to analyze your product photos
- **Analysis schema** — defines what fields to extract (product types, materials, techniques)
- **Vocabulary** — domain-specific language for richer, more authentic captions

## Files

| File | Purpose |
|------|---------|
| `vision_prompt.md` | Template for AI photo analysis. Customize the product categories, materials, and analysis fields for your domain. |
| `analysis_schema.yaml` | Defines domain-specific fields for photo analysis results. |
| `vocabulary.py` | Color, surface, and mood vocabulary injected into caption generation prompts. |

## How to Create Your Own

1. Copy this `_template/` directory to `packs/your-domain/`
2. Edit `vision_prompt.md` — replace generic product types with yours
3. Edit `analysis_schema.yaml` — define your product categories and attributes
4. Edit `vocabulary.py` — add descriptive language for your domain
5. Update `brand.yaml` to point to your new domain pack:
   ```yaml
   product:
     domain: "your-domain"
     domain_pack: "packs/your-domain"
   ```

## Examples by Domain

**Jewelry**: product types (ring, necklace, bracelet), materials (gold, silver, gemstones), techniques (casting, wire-wrapping, soldering)

**Art/Prints**: product types (painting, print, sculpture), materials (oil, acrylic, charcoal), techniques (impasto, wash, stippling)

**Vintage/Curated**: product types by era and category, condition vocabulary, provenance terms

**Fashion**: product types (dress, jacket, accessory), materials (silk, cotton, leather), construction details
