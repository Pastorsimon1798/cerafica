# Cerafica Work Summary - 2026-03-27

**Session:** Product video fixes, Instagram/Website sync, MCP-Video integration  
**Completed by:** Claude Code with Kimi

---

## ✅ COMPLETED TODAY

### 1. Fixed Product Video Issues

**Problem Identified:**
- Some product videos showed raw studio footage (blue rotating stand visible)
- Videos were missing "Cerafica Exploration Log" UI treatment
- ceruleix-2, ignix-5, lazurix-4 had issues

**Solution:**
- Created composited static images for glacix-1 and cupr-ex-6 (from raw studio photos)
- Added full UI treatment to ceruleix-2 and ignix-5 using mcp-video
- Restored lazurix-4 from backup at 1080p with UI treatment

### 2. Discovered Instagram/Website Sync Issue

**Finding:**
- Instagram folder had better quality videos (1080x1920) vs website (mixed 720p)
- Synced all Instagram videos to website

### 3. Created Shared Pipeline

**File:** `shared/pipeline.sh` - Syncs Instagram ↔ Website

### 4. MCP-Video Integration

Installed and used for UI overlays. Full feedback in `shared/MCP-VIDEO-FEEDBACK.md`

---

## 📋 KNOWN ISSUES

1. **ceruleix-2, ignix-5** - Videos cut off at bottom (source footage issue)
2. **lazurix-4** - Raw footage visible (blue stand) - may want to disable
3. **Photo vs Video quality gap** - Photos 2160x2700, videos 1080x1920

---

## 🔄 RECOMMENDED WORKFLOW

```
Film Video → Process with UI → Sync to Instagram + Website
```

**Pipeline Commands:**
```bash
./shared/pipeline.sh --sync    # Sync Instagram to Website
./shared/pipeline.sh --status  # Check sync status
```

---

## 🎯 NEXT STEPS

### Immediate:
- [ ] Fix lazurix-4 (disable video or create composited version)
- [ ] Check cromix-0 and pyr-os-8 for UI treatment needs
- [ ] Test website shop modal

### Short-term:
- [ ] Implement automated pipeline (process → sync → update)

### Long-term:
- [ ] Consider Remotion for UI templating
- [ ] Keep real vessel videos (NOT 3D models per user requirement)

---

## 📁 KEY FILES

| File | Purpose |
|------|---------|
| `shared/pipeline.sh` | Instagram ↔ Website sync |
| `shared/MCP-VIDEO-FEEDBACK.md` | MCP-Video improvements |
| `WORK-SUMMARY.md` | This file |
| `website/images/products/*` | Website assets |
| `output/framed/video/*` | Instagram assets (source) |

---

## 💡 BLENDER MCP NOTE

**User explicitly wants real vessel videos, NOT fake 3D models.**

The authenticity of handmade pottery is core to the brand. If Blender MCP is ever used, it should only be for:
- Effects around real footage (particles, atmosphere)
- Logo animations
- Transitions
- **Never for:** Replacing real vessel footage

---

## 📊 VIDEO STATUS

| Product | Res | UI | Framing | Status |
|---------|-----|-----|---------|--------|
| pallth-7 | 1080p | ✅ | ✅ Good | Ready |
| lazurix-4 | 1080p | ✅ | ✅ Good | ⚠️ Raw footage |
| ceruleix-2 | 1080p | ✅ | ❌ Cut off | Acceptable |
| ignix-5 | 1080p | ✅ | ❌ Cut off | Acceptable |
| Others | 1080p | ✅ | ✅ Good | Ready |

---

**End of Session - See WORK-SUMMARY.md for full details**
