# Self-Made Engineer: Windows render box (Dell G15 5520)

Machine: i7-12700H · 16 GB DDR5 · RTX 3050 Ti Laptop **4 GB VRAM** · ~326 GB free · Windows 11.

## Does Build #1 fit?
| | Budget | Build #1 (estimate from stats JSON, s11 Bolts) | Status |
|---|---|---|---|
| VRAM | 4 GB card, target ≤ 3 GB | images 593 MB + geometry 290 MB + buffers/denoiser/context ≈ **1.6–2.2 GB** | OK on paper, **not yet measured on NVIDIA** |
| RAM | 16 GB | peak RSS 1.6–1.8 GB (stills on the Mac); full render with persistent data expected ≈ 3–5 GB | OK |
| Disk | 326 GB free | assets + CC0 lib < 3 GB; PNG frames for ~104 s × 30 fps ≈ 3–6 GB | OK |

The one-shot keeps **one scene for the whole video** (world, kitchen and the cable section all live in it), so the
VRAM figure is the same for every frame. No individual scene stands out. Risks to watch:
- **Windows desktop takes 0.3–0.6 GB of VRAM.** Close browsers and games while rendering, and use the iGPU
  for the display if the BIOS/NVIDIA Control Panel allows it.
- **Full resolution (1080×1920) has not been rendered yet.** The Mac stills ran at scale 0.5. The denoiser buffers
  grow ×4, which is still inside the 2.2 GB upper estimate.
- **Dense frames:** grass (~25k instanced clumps), the trees and the ridge (~184k tris) are all in the hook/wide shots.
  Measure f300 and a wide f1600 first.
- **Fallback if VRAM runs out:** the 2K texture cap is hard-coded in `render_oneshot.py` and there is no CLI flag yet.
  Report it to the SME session: a 1K-cap flag or CPU fallback for that job is a small code change. The driver resumes
  where it stopped.

## Setup checklist (in order)
1. **NVIDIA driver:** install the latest Studio Driver with GeForce Experience or from nvidia.com and reboot.
   Then run `nvidia-smi` in a terminal. It must list the RTX 3050 Ti.
2. **Blender 5.3.0**, the same version as the Mac. Use the blender.org Windows installer or the zip. Note the path
   (`C:\Program Files\Blender Foundation\Blender 5.3\blender.exe`) and put it in `.env` / PATH like the WJH box does.
3. **Blender GPU:** open Blender → Edit → Preferences → System → Cycles Render Devices → **OptiX** → tick the
   RTX 3050 Ti. If OptiX shows no device, pick CUDA. Save Preferences. `render_oneshot.py` chooses
   OptiX → CUDA by itself, so the stats JSON `device` should say OPTIX.
4. **Git:** install Git for Windows, then
   `git clone https://github.com/finest1119/irfan.git` and
   `git checkout claude/optimistic-hawking-lkruq9`, the current working branch (d0ba893 includes the s11 Bolts and the Oswald fonts).
5. **Python 3.12 or newer** from python.org (tick "Add to PATH"). In the repo:
   `python -m venv .venv` → `.venv\Scripts\pip install pillow numpy requests google-genai faster-whisper fonttools`.
   Run `setx PYTHONUTF8 1` once, then open a new terminal.
6. **Secrets:** copy `.env` and `.env.page2` from the Mac by USB or AirDrop. **Never** through git or chat.
7. **Quaternius kits:** copy `assets/cc0/quaternius/UBC_Standard.zip` and `UAL_Standard.zip` (plus their extracted
   folders) from the Mac by hand. There's no anonymous URL.
8. **CC0 assets:** run `.venv\Scripts\python tools\fetch_cc0.py`. It fetches `tree_small_02` and the rest, and checks sha256.
   Then rebuild the library:
   `blender -b --factory-startup -P page2/blender/cc0_lib.py -- build`.
9. **Fonts:** `assets/fonts/Oswald-Bold.ttf` and `Oswald-SemiBold.ttf` arrive with git and are used by the thumbnail tool.
   You don't need to install them in Windows.
10. **Smoke test:**
    - `.venv\Scripts\python page2\tools\test_oneshot.py` → ALL PASS.
    - `oneshot.py still` for f300 and f1600 at full scale. While it runs, `nvidia-smi -l 1` shows peak VRAM.
      Write the number into BUILD-LOG.
11. **Render:** run `oneshot.py render`. It's resumable, so it's safe to stop and restart. Keep the laptop on AC power with
    the "Best performance" power mode, and don't let it sleep.
