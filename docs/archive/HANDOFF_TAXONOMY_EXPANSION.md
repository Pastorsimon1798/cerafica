# Taxonomy Expansion Handoff

**Date**: 2026-03-13
**Status**: 60% complete

## What's Done

### Phase 1: PhotoAnalysis Dataclass ✅
New fields added to `scripts/lib/caption_generator.py`:
- `clay_type: Optional[str]`
- `form_attributes: list[str]`
- `purpose: Optional[str]`
- `product_family: Optional[str]`
- `safety_flags: list[str]`

### Phase 2: Taxonomy Constants ✅
Added at line ~338:
- `CLAY_BODY_TAXONOMY` - 8 clay types with properties, visual cues, best glazes
- `FORM_ATTRIBUTES` - lidded, stackable, pourable, handheld mappings
- `PURPOSE_RULES` - functional/decorative/sculptural inference
- `PRODUCT_FAMILY_MAP` - dinnerware/serveware/drinkware/decor/garden/art
- `SAFETY_FLAG_RULES` - food_safe, microwave_safe, etc.

### Phase 4: Inference Functions ✅
Added at line ~420:
- `infer_purpose(piece_type)` - returns functional/decorative/sculptural
- `infer_product_family(piece_type)` - returns product category
- `infer_safety_flags(piece_type, glaze_type)` - returns safety flags list
- `infer_form_attributes(piece_type)` - returns form attributes list

## What's Remaining

### Phase 3: Update Ollama Vision Prompt (BLOCKED)
**Location**: `scripts/lib/caption_generator.py` lines 921-993

**Problem**: The prompt exists in TWO places (lines 976 and 1261). Attempting to edit causes "found 2 matches" error.

**Solution needed**:
1. Read both prompt locations to understand why there are duplicates
2. Either make each unique, or update both together with replace_all=true
3. Add new fields to JSON output spec: clay_type, form_attributes, purpose, product_family

**New fields to add to prompt** (after surface_qualities):
```
- clay_type: Identify clay body if visible at unglazed areas:
  * "b_mix" - Smooth white/cream porcelain
  * "death_valley" - Iron speckling, rustic
  * null if fully glazed
- form_attributes: Array ["lidded"|"stackable"|"pourable"|"handheld"] or []
- purpose: "functional"|"decorative"|"sculptural"|"hybrid"|null
- product_family: "dinnerware"|"serveware"|"drinkware"|"decor"|"garden"|"art"|null
```

### Phase 5: Update PhotoAnalysis Construction
**Location**: `scripts/lib/caption_generator.py` lines 1026-1039

Need to add the new fields to the return statement:
```python
return PhotoAnalysis(
    # ... existing fields ...
    clay_type=analysis.get("clay_type"),
    form_attributes=analysis.get("form_attributes", []),
    purpose=analysis.get("purpose") or infer_purpose(analysis.get("piece_type", "piece")),
    product_family=analysis.get("product_family") or infer_product_family(analysis.get("piece_type", "piece")),
    safety_flags=infer_safety_flags(analysis.get("piece_type"), analysis.get("glaze_type"))
)
```

### Phase 6: Update Caption Generation (optional enhancement)
Use new fields in `generate_hook()` and `generate_cta()`:
- Mention clay type in hook if distinctive (Death Valley, B-Mix)
- Add safety flags to CTA ("Microwave safe!", "Food safe!")

## Verification Commands

```bash
# Check module loads correctly
python3 -c "from scripts.lib.caption_generator import PhotoAnalysis, CLAY_BODY_TAXONOMY, infer_purpose; print('OK')"

# Check new fields exist
python3 -c "from scripts.lib.caption_generator import PhotoAnalysis; print([f.name for f in PhotoAnalysis.__dataclass_fields__.values()])"

# Test inference functions
python3 -c "from scripts.lib.caption_generator import infer_purpose, infer_safety_flags; print(infer_purpose('mug'), infer_safety_flags('mug', 'celadon'))"
```

## Key Files

| File | Lines Changed | Purpose |
|------|---------------|---------|
| `scripts/lib/caption_generator.py` | 133-158, 338-470, 921-1039 | Main implementation |
