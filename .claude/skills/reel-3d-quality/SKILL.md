---
name: reel-3d-quality
description: Irfan's 3D quality standard for all Facebook/YouTube reels (WJH, SME, ED, Di Belakang Tabir, Kita Buat Dia). Use when planning, briefing (incl. Codex), building, rendering or QC-ing any Blender scene, still or animation for these Pages.
---

# Reel 3D quality standard: "Mildly Elsewhere" level

Irfan's rule (28 Nov 2026): "Mildly Elsewhere style" means that channel's **3D render and animation QUALITY**. It does not mean "always do a cross-section".

- **Cutaway / cross-section:** Irfan likes it ("cantik"). Use it **whenever a scene suits it**, i.e. when cutting something open genuinely explains how it works. It is **not mandatory** in every video or shot.
- **Priority:** production quality in every shot.

## Quality checklist (brief Codex/agents with this; QC against it)
1. **Geometry:** bevels on hard edges, real thickness, no floating or interpenetrating parts, and secondary detail where the camera looks (screws, seams, welds, cables, labels, grime).
2. **Materials:** PBR with variation (dirt, wear, roughness breakup, damp), correct glass/water IOR, and subsurface on skin, fruit and leaves. Never a flat single-colour "toy plastic" look.
3. **Lighting:** a sky/HDRI with soft GI, plus key/fill/rim with soft shadows and grounded contact shadows. AgX/Filmic with a gentle contrast grade.
4. **Camera:** a real lens (35–50 mm), DOF on the subject, eased moves, and motion blur on in animation.
5. **Animation:** eased timing, overlapping action, no robotic constant speeds, and real contact (hands and feet on what they hold or touch).
6. **Render:** Cycles, adaptive sampling (~128–256 spp stills, ~64+ animation), OpenImageDenoise.

## Mac rendering
- The M2 Pro GPU works with Cycles **Metal**. Scripts must enable Metal GPU + CPU, with a CPU fallback.
- The Codex CLI sandbox hides the GPU. Codex writes scripts and runs `--preview` only; the chief runs the full render outside the sandbox.
- Codex CLI: `codex exec -m gpt-6.2-astra -c model_reasoning_effort=max -s workspace-write "<brief>"`.

Toolkit: `pipeline/cutaway/` (cutlib.py). Its helpers work for non-cutaway shots too.
