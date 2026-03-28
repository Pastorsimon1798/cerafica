# Ceramics Vision Prompt Template
# Used by the vision pipeline to analyze ceramic pottery photos.
# Variables: {idea_seed_section}, {color_sections}, {chemistry_section}

Analyze this ceramic pottery photo and provide a structured analysis.
{idea_seed_section}

SURFACE EFFECTS COMMON IN THIS STUDIO (cone 10 reduction):
- Carbon trapping and crackle networks (Shino-family glazes)
- Blue pooling in recesses, color breaking at thin spots (Chun-family)
- Warm luster and honey tones with copper flashing (layered glazes)
- Iron speckling and dark surface variation (iron-saturated glazes)
Your job is to DESCRIBE what you see, not identify glazes.

Respond with a JSON object with these fields:

- hypotheses: Array of 3-5 initial hypotheses about the piece
  Format: "description [confidence] - visual evidence"
  Confidence levels: high, medium, low
  Example: "Bud vase with Shino glaze [high] - crackle texture visible, carbon trapping at shoulder"
  For multi-piece photos (3+ different types), lead with "Collection of mixed forms [high] - ..."

- piece_type: Classify using these STANDARD CERAMICS TERMINOLOGY definitions:

  MULTI-PIECE PHOTOS (CHECK FIRST):
  * collection: Multiple DIFFERENT pieces in one shot (e.g., 3 bowls + 2 vases + 1 mug)
    Use this when pieces are not all the same type - do NOT force one category.
  * If all pieces ARE the same type (e.g., 5 bud vases), still use the singular form (bud_vase)
    and set piece_count to the number visible.

  BUD VASE vs VASE (critical distinction):
  * bud_vase: SMALLEST vase category. Designed for ONE flower stem. Narrow neck, usually < 6" tall.
             Key: opening barely wide enough for single stem, proportionally small overall.
  * vase: For multiple flowers/arrangements. Wider opening than bud vase, typically 6"+ tall.
          Key: opening can hold several stems, larger body.

  JAR vs BOWL (critical distinction):
  * jar: Opening is NARROWER than the widest part of body (constricted lip).
         Often has lid-seating rim even if no lid present. Storage form.
  * bowl: Opening is WIDER than or equal to body width. Open, accessible form.
          Depth typically less than width.

  OTHER FORMS:
  * mug: Has handle, cylindrical or tapered body, for drinking hot beverages
  * cup: Smaller than mug, may or may not have handle, for drinking
  * tumbler: Cylindrical drinking vessel WITHOUT handle
  * planter: Container for plants, often with drainage considerations
  * plate: Flat, shallow, for serving food
  * pitcher: Has SPOUT and handle, for pouring liquids
  * teapot: Has LID, spout, AND handle, for brewing tea
  * sculpture: Non-functional artistic form

  UNCERTAINTY: Use "piece" if uncertain (prefer this over wrong classification)

- content_type: One of (finished, process, kiln_reveal, studio, detail)
- firing_state: CRITICAL - What stage of firing is this piece?
  * "greenware" - NEVER fired. Raw clay, fresh off wheel, still drying. Soft, can be scratched with fingernail.
  * "bisque" - FIRED ONCE (bisque fire ~ cone 06). Porous, matte, no glaze. Clay has changed color from raw (gray/pink -> white/terracotta). LOOKS FIRED, not raw.
  * "glazed" - Glaze applied (shiny or matte coating visible), may be unfired or fired
  * "finished" - Fully fired and glazed, ready to use
  * null if unclear

  KEY DISTINCTION: Greenware vs Bisque
  * Greenware = raw, unfired clay (grayish-pink or cream, looks "wet" or "leather hard")
  * Bisque = has been through kiln once (white or terracotta, looks "dry" and "fired", no shine but definitely transformed)

- primary_colors: Array of 1-2 main colors. Use CONE 10 REDUCTION vocabulary:
{color_sections}
  * Or any color you see - unexpected combinations are welcome!
- secondary_colors: Array of accent colors (same vocabulary)

- glaze_type: null always. Do NOT write brand names (e.g., "Shino", "Tenmoku").
  Instead, in hypotheses you may reference chemistry from the STUDIO GLAZE CHEMISTRY table below.
  Describe what the chemistry IS (oxide compounds), not brand names.
  null always.

STUDIO GLAZE CHEMISTRY (use these aliases in hypotheses -- describe compounds, never brand names):
{chemistry_section}

- color_appearance: VIVID VISUAL DESCRIPTION of the surface. This is the PRIMARY field for describing glaze effects.
  Use pottery chemistry vocabulary: breaking, pooling, running, carbon trapping, flashing, crawling, rivulets.
  Use emotional/sensory language: "velvety matte," "glassy depth," "warm radiance," "cool luminosity."
  Make at least 3 distinct observations about this specific piece. Be specific -- no generic descriptions.
  Minimum 15 words, ideally 25-40 words. Each description must be UNIQUE to this piece.
  Examples: "chalcedony blue pooling in recesses with calcite breaking at the rim, carbon trapping visible at shoulder creating speckled iron deposits over the raw clay"
             "slate and pyrolusite flowing in variegated waves across the belly, a prominent crackle network catching light along the shoulder where the glaze thins to reveal bisque beneath"
             "deep denim pooling at the neck, transitioning through a metallic slate-gray midsection into bronze luster highlights near the foot where crawling exposes the warm B-Mix body"
  null if unglazed/unfired

- surface_qualities: Array of visible surface phenomena (max 5, only if finished/fired):

  REQUIREMENTS:
  - Always include a SHEEN LEVEL (matte, satin, or gloss) -- actually LOOK at the reflectivity
  - Include at least one QUALITY CATEGORY beyond sheen
  - Each quality must be a DISTINCT phenomenon -- no listing 3 variations of the same thing

  SHEEN LEVELS (judge by reflectivity):
  * matte: No reflection, flat finish. Looks absorbent, like raw clay.
  * satin: Subtle reflection, soft glow. Semi-reflective, like eggshell.
  * gloss: Clear reflection, mirror-like highlights. Glassy, wet-looking.

  QUALITY CATEGORIES:
  * SHEEN: matte, satin, gloss
  * COLOR EFFECTS: variegation (mottled), breaking (color change at edges), color_pooling, flashing (localized kiln-atmosphere color), blush, halo, mottling
  * MOVEMENT: crawling (glaze pulls back), running, rivulets, dripping, cascading, pinholing, running_thin
  * CRYSTALLINE: crystalline (visible crystals), oil_spot (metallic spots on dark), crackle (fine crack network), waxy (micro-crystalline sheen), micro_crystal
  * REDUCTION: carbon_trapping (dark speckles in lighter glaze), luster (metallic sheen), reduction_shadow, wadding_mark, flame_mark
  * TEXTURE: smooth, speckled (visible particles), leather_hard (if unfired), raw, waxy, sandy, gritty
  * PATTERN: striped, banded, spotted, dappled, feathered
  * EDGE EFFECTS: dry_foot (unglazed base), lip_mark, thumbprint
  null if none visible or unclear

- clay_type: Identify clay body if visible at unglazed areas or foot:
  * "b_mix" - Smooth white/cream porcelain
  * "death_valley" - Iron speckling visible, rustic look
  * "porcelain" - Pure white, translucent when thin
  * "stoneware" - Generic gray/tan stoneware
  * "sculptural_raku" - Blackened, crackled surface from raku firing
  * "earthenware" - Low-fire red/brown clay
  * null if fully glazed (can't see clay)

- form_attributes: Array of structural/aesthetic features. Use ceramics education vocabulary:
  * Functional: lidded, stackable, pourable, handheld, nested
  * Body Profile: cylindrical, spherical, ovoid, conical, bell_shaped, shouldered, necked, waisted, bulbous, elongated, squat, tall_slender, balanced, short_wide, heavy_bottomed, top_heavy, s_curve, tapered_bottom, wide_mouth, trumpet, barrel, drum, mushroom, pagoda, kidney, crescent, pod
  * Rim/Lip: flared, tapered, rolled, rounded, squared, pinched, cut, split, everted, collared
  * Foot/Base: footed, trimmed, flat_base, pedestal, foot_ring, wide_foot, unglazed_foot, triple_foot
  * Character: organic, geometric, asymmetrical, sculptural, refined, rustic, bold, delicate, playful, dramatic, serene, intimate, industrial, minimal, ornate, monumental, whimsical
  * Surface Form: faceted, fluted, ribbed, carved, textured, smooth, pierced, incised, stamped, combed, paddled, slip_trail, sgraffito, wax_resist, impressed
  * Or any descriptor you see - unusual combinations are welcome!

- purpose: "functional"|"decorative"|"sculptural"|"hybrid"|null
- product_family: "dinnerware"|"serveware"|"drinkware"|"decor"|"garden"|"art"|null
- technique: One of (wheel-thrown, handbuilt, slip-cast, coil_built, pinch_pot, slab_built, wheel_altered, extruded, press_molded, or null)
- mood: One of (warm, cool, earthy, modern, organic, dramatic, serene, bold, intimate, playful, minimal, moody, vibrant, rustic, luminous)
- dimensions_visible: Boolean - can you estimate size?
- piece_count: Integer - how many pieces are visible? (1=single, 2-5=few, 6+=collection)
- brief_description: 5-10 word description for the hook

- uncertainties: Array of things you CANNOT determine. Be specific about WHAT and WHY. Use [] if highly confident.

- color_distribution: How colors are distributed across the piece surface
  Options: "uniform" (even), "breaking" (color shifts at edges/thin spots), "pooling" (darker in recesses),
           "variegated" (mottled/patchy), "gradient" (smooth transition), "banded" (horizontal/vertical bands),
           "dappled" (spotted color variation), "streaked" (directional lines of color), "speckled" (fine dots),
           "ombre" (gradual fade between colors), "feathered" (soft blended edges), "mottled" (irregular patches)
  Example: "breaking"

DIVERSITY RULES -- Read carefully:
- Do NOT use "earth tones" as a color. That is not a color. Use specific taxonomy words from the color vocabulary above.
- Do NOT default to "earthy" for mood. Consider: warm, cool, modern, organic, dramatic, serene, bold, intimate.
- Do NOT always say "gloss" for sheen. Actually LOOK at the reflectivity. Satin and matte are equally valid.
- Each surface quality should be a DISTINCT phenomenon. Don't list 3 variations of the same thing.
- color_appearance MUST be unique to this specific piece. No generic descriptions.
- Vary your sentence structure. Do not start every description the same way.

Example response:
{{"piece_type": "bud_vase", "content_type": "finished", "firing_state": "finished", "primary_colors": ["sienna", "copper"], "secondary_colors": ["bronze"], "glaze_type": null, "color_appearance": "chalcedony blue pooling in recesses with calcite breaking at the rim over exposed ferruginous clay, carbon trapping visible at shoulder creating speckled iron deposits", "surface_qualities": ["waxy", "crawling", "luster", "color_pooling"], "clay_type": "b_mix", "form_attributes": ["necked", "organic", "delicate"], "purpose": "decorative", "product_family": "decor", "technique": "wheel-thrown", "mood": "warm", "dimensions_visible": true, "piece_count": 1, "brief_description": "Lustrous bud vase with warm sienna and copper tones", "hypotheses": ["Bud vase with Shino glaze [high] - crackle texture visible, carbon trapping", "Small pitcher [low] - no handle visible but form could accommodate"], "uncertainties": [], "color_distribution": "breaking"}}
