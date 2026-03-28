# Product Vision Prompt Template
# Generic template for analyzing product photos.
# Customize this for your domain (jewelry, art, fashion, etc.)
# Variables: {idea_seed_section}

Analyze this product photo and provide a structured analysis.
{idea_seed_section}

Respond with a JSON object with these fields:

- hypotheses: Array of 3-5 initial observations about the product
  Format: "description [confidence] - visual evidence"
  Confidence levels: high, medium, low
  Example: "Handmade necklace with silver chain [high] - visible clasp and pendant"

- product_type: Classify the product. Use your best judgment for the category.
  Use "item" if uncertain (prefer this over wrong classification).

- content_type: One of (finished, process, workspace, detail, lifestyle)
  * finished: Completed product, ready for sale
  * process: Work in progress, showing creation
  * workspace: Studio/workshop environment
  * detail: Close-up of specific feature
  * lifestyle: Product in use or styled setting

- primary_colors: Array of 1-2 main colors visible
- secondary_colors: Array of accent or background colors

- surface_qualities: Array of visible surface characteristics (max 5):
  * FINISH: matte, satin, gloss, polished, brushed, textured, rough, smooth
  * PATTERN: solid, patterned, striped, spotted, gradient, marbled
  * MATERIAL: natural, metallic, transparent, opaque, translucent, woven, carved

- materials: What the product appears to be made of (e.g., "silver", "cotton", "wood")

- technique: How the product appears to have been made (e.g., "handmade", "machine-made", "hand-painted")

- mood: One of (warm, cool, earthy, modern, organic, dramatic, serene, bold, intimate, playful, minimal, moody, vibrant, rustic, luminous, elegant, casual)

- dimensions_visible: Boolean - can you estimate size?
- piece_count: Integer - how many items are visible?
- brief_description: 5-10 word description for a caption hook

- uncertainties: Array of things you CANNOT determine. Be specific. Use [] if highly confident.

- color_distribution: How colors are distributed
  Options: "uniform", "gradient", "patterned", "variegated", "striped", "spotted"

QUALITY RULES:
- Be specific. No generic descriptions.
- Each observation must be unique to this specific product.
- Describe what you actually SEE, not what you assume.

Example response:
{{"product_type": "necklace", "content_type": "finished", "primary_colors": ["silver", "turquoise"], "secondary_colors": ["black"], "surface_qualities": ["polished", "smooth", "metallic"], "materials": "sterling silver, turquoise stone", "technique": "handmade", "mood": "elegant", "dimensions_visible": false, "piece_count": 1, "brief_description": "Turquoise pendant on polished silver chain", "hypotheses": ["Sterling silver pendant necklace [high] - visible hallmark on clasp"], "uncertainties": ["Chain length unclear from photo angle"], "color_distribution": "uniform"}}
