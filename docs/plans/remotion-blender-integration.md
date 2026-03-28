# Remotion + Blender Integration Design

**Status:** Design Phase  
**Goal:** Generate photorealistic 3D product videos instead of filming physical pieces  
**Date:** 2026-03-27

---

## Overview

Instead of filming physical pottery pieces, generate videos programmatically:
1. **Blender** → Photorealistic 3D vessel with actual glaze materials
2. **Remotion** → React-based video composition (UI, animations, sequencing)
3. **MCP-Video** → Final encoding/optimization for Instagram/Website

---

## Part 1: Blender MCP Server

### Purpose
Generate photorealistic 3D vessel rotations from photos.

### Workflow
```
High-quality product photo → Blender MCP → 3D model + materials → Rendered rotation video
```

### API Design
```python
# blender_mcp.generate_rotation()
{
    "input_image": "cupr-ex-6.jpg",      # High-quality product photo
    "output": "cupr-ex-6_3d.mp4",
    
    # 3D reconstruction params
    "reconstruction": {
        "method": "photogrammetry",        # or "procedural_from_profile"
        "profile_view": "auto",            # Extract profile from photo
        "symmetry": "radial",              # Pottery is radially symmetric
    },
    
    # Material extraction
    "materials": {
        "base_color": "auto_extract",      # From photo
        "roughness_map": "auto_extract",   # Specular highlights
        "normal_map": "auto_extract",      # Surface texture
        "glaze_type": "carbon_trap_shino", # Manual override option
    },
    
    # Render settings
    "render": {
        "resolution": [1080, 1920],        # 9:16 for Instagram
        "duration_seconds": 10,
        "rotation_degrees": 360,           # Full rotation
        "lighting": "studio_three_point",  # Or "hdri_environment"
        "background": "transparent",       # For compositing
    }
}
```

### Implementation Approaches

#### Option A: Photogrammetry (High Quality, Complex)
- Input: 12-20 photos of piece from different angles
- Process: COLMAP → Mesh → Blender
- Pros: Accurate shape
- Cons: Need multiple photos, computationally expensive

#### Option B: Profile-Based Procedural (Medium Quality, Fast)
- Input: Single high-quality photo
- Process: 
  1. Extract profile curve from photo (silhouette detection)
  2. Lathe modifier → 3D mesh
  3. Project photo texture onto mesh
  4. Add procedural displacement for surface texture
- Pros: Single photo, fast, good enough
- Cons: Symmetric assumption, interior not accurate

#### Option C: AI 3D Generation (Experimental)
- Input: Single photo
- Process: Stable Diffusion 3D → Mesh → Blender refinement
- Tools: Zero123, One-2-3-45, Wonder3D
- Pros: Handles complex shapes
- Cons: Inconsistent quality, requires GPU

### Recommended: Option B (Profile-Based)
```python
# Blender Python API sketch
import bpy

# 1. Load photo
img = bpy.data.images.load("cupr-ex-6.jpg")

# 2. Detect profile (using OpenCV preprocessing or manual curve)
profile_curve = create_bezier_from_photo(img)

# 3. Create lathe
bpy.ops.curve.convert(type='MESH')
bpy.ops.object.modifier_add(type='SCREW')

# 4. Apply photo as texture
material = create_pbr_material_from_photo(img)

# 5. Setup lighting and camera
setup_studio_lighting()
camera = setup_orbit_camera(radius=15, height=10)

# 6. Render rotation
render_orbit_animation(camera, frames=300, output="cupr-ex-6_3d.mp4")
```

---

## Part 2: Remotion Integration

### Purpose
React-based video composition layer between Blender and final output.

### Workflow
```
Blender 3D render → Remotion composition → mcp-video encode → Final output
```

### Why Remotion?
- **Code-based video editing** (version control, reproducible)
- **React components** for UI elements (titles, zoom panels, data displays)
- **Motion graphics** (smooth animations, transitions)
- **Parameterization** (change text/colors without re-rendering 3D)

### Project Structure
```
remotion/
├── src/
│   ├── compositions/
│   │   └── ProductReel.tsx          # Main composition
│   ├── components/
│   │   ├── SpaceBackground.tsx      # Starfield
│   │   ├── VesselDisplay.tsx        # 3D render + effects
│   │   ├── ZoomPanels.tsx           # Detail panels
│   │   ├── ExplorationLogHeader.tsx # "Cerafica Exploration Log"
│   │   ├── ProductMetadata.tsx      # Name, description
│   │   └── Scanlines.tsx            # CRT effect
│   ├── data/
│   │   └── products.json            # Product metadata
│   └── index.tsx
├── public/
│   ├── 3d-renders/                  # Blender output videos
│   │   ├── cupr-ex-6_3d.mp4
│   │   └── ...
│   └── assets/
│       ├── logo.png
│       └── starfield.jpg
└── remotion.config.ts
```

### Composition Component
```tsx
// src/compositions/ProductReel.tsx
import {Composition} from 'remotion';
import {ProductReel} from './ProductReel';

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="ProductReel"
      component={ProductReel}
      durationInFrames={300}        // 10s @ 30fps
      fps={30}
      width={1080}
      height={1920}
      defaultProps={{
        productName: "Cupr-Ex-6",
        renderVideo: "3d-renders/cupr-ex-6_3d.mp4",
        zoomTimestamps: [90, 150, 210],  // Frame numbers
        surfaceGeology: "Stratified canyons veined with metallic copper...",
        atmosphere: "Metallic, like licking a battery",
        temperature: "Variable",
      }}
    />
  );
};
```

### Main Reel Component
```tsx
// src/components/ProductReel.tsx
import {Video, staticFile, useCurrentFrame} from 'remotion';
import {SpaceBackground} from './SpaceBackground';
import {ZoomPanels} from './ZoomPanels';
import {ExplorationLogHeader} from './ExplorationLogHeader';
import {ProductMetadata} from './ProductMetadata';
import {Scanlines} from './Scanlines';

export const ProductReel: React.FC<{
  productName: string;
  renderVideo: string;
  zoomTimestamps: number[];
  surfaceGeology: string;
  atmosphere: string;
  temperature: string;
}> = (props) => {
  const frame = useCurrentFrame();
  
  return (
    <div style={{width: 1080, height: 1920, background: 'black'}}>
      {/* Layer 1: Space background */}
      <SpaceBackground />
      
      {/* Layer 2: 3D vessel render */}
      <Video
        src={staticFile(props.renderVideo)}
        style={{
          position: 'absolute',
          left: 0,
          top: 240,                    // Center in 4:5 safe area
          width: 1080,
          height: 1350,
        }}
      />
      
      {/* Layer 3: UI Frame */}
      <div style={{
        position: 'absolute',
        inset: 20,
        border: '2px solid rgba(0, 255, 255, 0.5)',
        borderRadius: 4,
      }} />
      
      {/* Layer 4: Header */}
      <ExplorationLogHeader 
        productName={props.productName}
        frame={frame}
      />
      
      {/* Layer 5: Zoom panels (appear at specific timestamps) */}
      {props.zoomTimestamps.map((ts, i) => (
        frame > ts && (
          <ZoomPanel
            key={i}
            index={i}
            vesselVideo={props.renderVideo}
            timestamp={ts}
          />
        )
      ))}
      
      {/* Layer 6: Data panel (bottom) */}
      <ProductMetadata
        surfaceGeology={props.surfaceGeology}
        atmosphere={props.atmosphere}
        temperature={props.temperature}
        frame={frame}
      />
      
      {/* Layer 7: Logo */}
      <Logo position="bottom-right" />
      
      {/* Layer 8: CRT scanlines effect */}
      <Scanlines opacity={0.1} />
    </div>
  );
};
```

### Zoom Panel Component
```tsx
// src/components/ZoomPanels.tsx
import {useVideoConfig, Video, staticFile} from 'remotion';
import {interpolate} from 'remotion';

export const ZoomPanel: React.FC<{
  index: number;
  vesselVideo: string;
  timestamp: number;
}> = ({index, vesselVideo, timestamp}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  
  // Slide in animation
  const progress = interpolate(
    frame - timestamp,
    [0, 15],
    [0, 1],
    {extrapolateRight: 'clamp'}
  );
  
  const yOffset = interpolate(progress, [0, 1], [-100, 0]);
  
  // Position based on index (stack vertically on right side)
  const top = 100 + (index * 220);
  
  return (
    <div style={{
      position: 'absolute',
      right: 40,
      top: top + yOffset,
      width: 180,
      height: 200,
      border: '2px solid cyan',
      borderRadius: 4,
      overflow: 'hidden',
      background: 'rgba(0,0,0,0.7)',
    }}>
      {/* Extract frame from vessel video at timestamp */}
      <Video
        src={staticFile(vesselVideo)}
        startFrom={timestamp}
        style={{
          width: '100%',
          height: '100%',
          objectFit: 'cover',
        }}
      />
      <div style={{
        position: 'absolute',
        bottom: 0,
        left: 0,
        right: 0,
        padding: 4,
        background: 'rgba(0,0,0,0.8)',
        color: 'cyan',
        fontSize: 10,
        fontFamily: 'monospace',
      }}>
        ZOOM-{index + 1}
      </div>
    </div>
  );
};
```

---

## Part 3: MCP-Video Integration

### Purpose
Final encoding and optimization after Remotion composition.

### Workflow
```
Remotion render (lossless) → mcp-video → Instagram/Website optimized outputs
```

### Usage
```python
# 1. Remotion renders lossless ProRes or high-bitrate MP4
# remotion render remotion/index.tsx ProductReel --prores=4444

# 2. MCP-Video handles final encoding
import mcp_video

client = mcp_video.Client()

# Instagram version (H.264, high bitrate)
client.convert(
    video="remotion-output.mov",
    output="output/framed/video/Cupr-ex-6_rotating.mp4",
    codec="h264",
    bitrate="8000k",           # High quality for Instagram
    resolution=(1080, 1920),
    profile="high"
)

# Website version (smaller file, good quality)
client.convert(
    video="remotion-output.mov", 
    output="website/images/products/cupr-ex-6_rotating.mp4",
    codec="h264",
    bitrate="4000k",           # Smaller for web
    resolution=(1080, 1920),
    profile="main"
)
```

---

## Full Pipeline

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Product Photo  │────▶│   Blender MCP   │────▶│ 3D Render Video │
│  (high quality) │     │  (3D generation)│     │ (transparent BG)│
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │
┌─────────────────┐     ┌─────────────────┐              │
│   products.json │────▶│    Remotion     │◀─────────────┘
│   (metadata)    │     │ (composition)   │
└─────────────────┘     └────────┬────────┘
                                 │
                                 ▼
                         ┌─────────────────┐
                         │  Lossless ProRes│
                         │  or high-bitrate│
                         └────────┬────────┘
                                  │
                                  ▼
                         ┌─────────────────┐
                         │   MCP-Video     │
                         │ (final encode)  │
                         └────────┬────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    │                             │
                    ▼                             ▼
           ┌─────────────┐               ┌─────────────┐
           │  Instagram  │               │   Website   │
           │  (high bitrate)              │ (optimized) │
           └─────────────┘               └─────────────┘
```

---

## Implementation Phases

### Phase 1: Blender Script (Week 1-2)
- Python script for profile-based vessel generation
- Material extraction from photos
- Camera orbit + render setup
- Manual workflow (not MCP yet)

### Phase 2: Remotion Setup (Week 2-3)
- Initialize Remotion project
- Build ProductReel composition
- All UI components (header, zoom panels, metadata)
- Test with existing video footage

### Phase 3: Integration (Week 3-4)
- Connect Blender output → Remotion input
- MCP-Video final encoding
- Batch processing script for all products
- Compare quality vs filmed footage

### Phase 4: MCP Server (Future)
- Package Blender script as MCP server
- Package Remotion as MCP server
- Single-command generation: `generate_product_video(product_id)`

---

## Open Questions

1. **Quality comparison:** Will 3D render look as good as filmed footage?
2. **Glaze realism:** Can we capture the iridescent/special glaze effects?
3. **Processing time:** Blender render + Remotion comp vs filming time
4. **Manual intervention:** How much manual tweaking needed per piece?

---

## Resources

- **Blender Python API:** https://docs.blender.org/api/current/
- **Remotion Docs:** https://www.remotion.dev/
- **Blender Photogrammetry:** https://github.com/SBCV/Blender-Addon-Photogrammetry-Importer
- **Stable Diffusion 3D:** https://github.com/Stability-AI/stable-fast-3d
