# Benchmark render: Asus ROG Strix G513QC (ED laptop), 26 Nov 2026

Ryzen 7 5800H · 16 GB · RTX 3050 Laptop 4 GB · NVIDIA Studio 621.40 · Blender 5.3.0 · Windows 11 Home.
Episode: `episodes/2026-11-24-1-plane-crash` (v2, EEVEE, 24 samples, 1080×1920). Nothing was posted.

Method: the Gemini TTS step was skipped, so timings are synthetic (~2.6 words/s, i.e. 112.8 s = 3385 frames) and
captions are empty. Textures come from `v2_textures.make`. Renders go through `render_episode_v2.py` with the
engine swapped by a wrapper. `nvidia-smi` was logged every 0.5 s for the whole run.
All output is in `output/bench-plane-crash/` (gitignored).

## Stills (one frame, mid-beat)

| Beat | EEVEE render | Cycles OptiX + OptiX denoise (64 spp adaptive) | Scene build |
|---|---|---|---|
| hook | 17.5 s (first run, shader compile) | 13.7 s | 74 s |
| one | 5.2 s | 10.6 s | 72 s |
| three | 12.9 s | 12.5 s | 90 s |
| takeaway | 10.4 s | 17.3 s | 1 s |

## Animation (the number that matters)

| Test | Result |
|---|---|
| EEVEE, 1 process, 60 frames (beat `one`) | **0.90 s/frame** (marginal; one Blender start + build ≈ 160 s) |
| EEVEE, 3 processes in parallel (pipeline `parallel: 3`), 3 × 45 frames | 212 s wall = 1.57 s/frame **including** 3 × start/build |
| Encode `hevc_nvenc` (p6), 112.8 s, FB copy | 1st pass 10.21 MB (over), retry at 85 % bitrate (as `step_fb` does) **7.64 MB** ✓, encode about 21 s |

## GPU (nvidia-smi)

| Phase | Peak VRAM | Peak temp | Avg temp |
|---|---|---|---|
| Stills (EEVEE + Cycles) | 2159 MiB | 82 °C | 58 °C |
| EEVEE 60 frames | 1860 MiB | 76 °C | 61 °C |
| **3 Blender in parallel** | **3484 MiB / 4096 (85 %)** | **87 °C** | 77 °C |

Peak power draw was 98 W.

## Verdict

- 0.90 s/frame with EEVEE is in the **≤ 1.5 s** band of WINDOWS-SETUP.md. Rough estimate per ~113 s episode:
  3385 × 0.9 s ≈ 51 min of frames, plus about 160 s of start and build per 150-frame chunk. Spread over
  3 processes, that comes to **≈ 45–60 min per episode**, so 5 videos/day ≈ 4–5 h of rendering. This still has to
  be confirmed on one real end-to-end episode, which needs TTS, overlays and assemble.
- EEVEE stays the engine. Cycles OptiX is not faster on these scenes and costs more VRAM.
- **Watch it:** with 3 parallel processes the GPU reached **87 °C** (above the 85 °C guideline) and 85 % VRAM.
  Use a cooling pad / hard surface. If temperatures stay > 85 °C or VRAM runs out on heavier scenes, drop to
  `--parallel 2`.
- Note: `make_episode.py` starts Blender with `--factory-startup`, so the OptiX preference is not used there.
  EEVEE always runs on the GPU that Windows assigns to blender.exe, which is set to High performance (NVIDIA).
