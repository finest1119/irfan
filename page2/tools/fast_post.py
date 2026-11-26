"""Post step of the `fast` render profile (Session 13; venv + PIL/numpy, no Blender). Windows-safe (pathlib only).

  python page2/tools/fast_post.py EPISODE WORKDIR [--range A-B] [--scale 1.0] [--force] [--no-blur]

For each frame: WORKDIR/frames_oneshot_fast/####.jpg (rendered at 0.75 of the final size)
  -> Lanczos upscale to the final size (episode render.resolution x --scale) + mild unsharp mask
  -> the clamped 2D motion blur for that frame (oneshot_blur.blur_spec over oneshot/camera_speed.json, recomputed
     here so it always matches the current plan; "radial" zoom blur for snap/portal moves, "directional" otherwise,
     never on portal join frames, holds never blur). Deviation: a radial (snap) frame whose mean screen motion is
     mostly one direction (|dx,dy|/px >= 0.5, a whip pan) is blurred directionally instead.
  -> WORKDIR/frames_oneshot/####.jpg (q95, 4:4:4; temp file + os.replace), where `oneshot.py link` / make_episode
     expect them. Existing outputs are skipped unless --force (resumable, idempotent: the raw frames are never
     touched). oneshot.py render --profile fast calls this after every job; run it by hand only to redo frames.

Blur model: px (already clamped at 60 px by blur_spec, in 1080x1920 units) is scaled to the output width and used
as the full kernel length along the unit direction (directional), or as the displacement at a reference radius of
half the frame's half-diagonal (radial, centre fixed, edges move ~2x). Averaging is done in linear light with edge
clamping (no black borders, no wrap).
"""
import argparse
import json
import math
import os
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import oneshot_blur as OB  # noqa: E402

RAW_DIR = "frames_oneshot_fast"
OUT_DIR = "frames_oneshot"
REF_W = 1080.0                     # camera_speed px are measured at 1080x1920
UNSHARP = dict(radius=1.2, percent=45, threshold=2)
GAMMA = 2.2
MAX_TAPS = 48
WHIP_RATIO = 0.5       # radial entry whose mean screen motion is mostly one direction -> directional (a whip pan)


def blur_table(workdir):
    """{global frame: blur entry} from the CURRENT camera_speed.json (blur_2d.json on disk may be stale)."""
    cs = json.loads((Path(workdir) / "oneshot" / "camera_speed.json").read_text(encoding="utf-8"))
    spec = OB.blur_spec(cs)
    speed = {s["f"]: s for s in cs["speed"]}
    for e in spec["frames"]:
        # s13 deviation from blur_spec's mode: the build-01 "snaps" are whip pans (|mean dx,dy| / px ~ 0.9), so a
        # centred zoom blur read wrong next to the Cycles 3D blur. Keep radial only for true push-ins.
        sp = speed.get(e["f"], {})
        ratio = math.hypot(sp.get("dx", 0.0), sp.get("dy", 0.0)) / max(1e-6, float(sp.get("px", 0.0)))
        e["lin_ratio"] = round(ratio, 3)
        if e["mode"] == "radial" and ratio >= WHIP_RATIO:
            e["mode"] = "directional"
            e["mode_from"] = "radial"
    return {e["f"]: e for e in spec["frames"]}, spec


def final_size(episode, scale):
    ep = json.loads(Path(episode).read_text(encoding="utf-8"))
    res = ep.get("render", {}).get("resolution", [1080, 1920])
    return int(res[0] * scale), int(res[1] * scale)


def upscale(im, size):
    im = im.convert("RGB")
    if im.size != tuple(size):
        im = im.resize(size, Image.LANCZOS)
        im = im.filter(ImageFilter.UnsharpMask(**UNSHARP))
    return im


def _taps(length):
    return int(max(3, min(MAX_TAPS, math.ceil(abs(length) / 1.5) + 1)))


def blur_2d(im, entry):
    """Apply one blur_spec entry to a full-res PIL image (returns a new image)."""
    w, h = im.size
    px = float(entry["px"]) * (w / REF_W)
    if px < 0.75:
        return im
    lin = (np.asarray(im, dtype=np.float32) / 255.0) ** GAMMA
    acc = np.zeros_like(lin)
    xs, ys = np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32)
    n = _taps(px if entry["mode"] != "radial" else 2 * px)
    if entry["mode"] == "radial":
        cx, cy = (w - 1) / 2.0, (h - 1) / 2.0
        r_ref = 0.5 * math.hypot(w / 2.0, h / 2.0)
        k = px / r_ref                       # zoom range; centred on 1 so the frame does not drift
        for s in np.linspace(1.0 - k / 2, 1.0 + k / 2, n):
            xi = np.clip(np.rint(cx + (xs - cx) / s), 0, w - 1).astype(np.intp)
            yi = np.clip(np.rint(cy + (ys - cy) / s), 0, h - 1).astype(np.intp)
            acc += lin[yi][:, xi]
    else:
        dx, dy = entry.get("dir", [0.0, 0.0])
        if abs(dx) + abs(dy) < 1e-6:
            return im
        for t in np.linspace(-px / 2, px / 2, n):
            xi = np.clip(np.rint(xs + t * dx), 0, w - 1).astype(np.intp)
            yi = np.clip(np.rint(ys + t * dy), 0, h - 1).astype(np.intp)
            acc += lin[yi][:, xi]
    out = np.clip((acc / n) ** (1.0 / GAMMA) * 255.0 + 0.5, 0, 255).astype(np.uint8)
    return Image.fromarray(out, "RGB")


def process_file(src, dst, size, entry, fmt=None):
    """src (low-res) -> dst (full res, blurred if entry). Atomic write. Returns seconds."""
    t0 = time.time()
    with Image.open(str(src)) as im0:
        im = upscale(im0, size)
    if entry:
        im = blur_2d(im, entry)
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    fmt = fmt or ("PNG" if dst.suffix.lower() == ".png" else "JPEG")
    tmp = dst.with_name(dst.stem + ".tmp" + dst.suffix)
    if fmt == "JPEG":
        im.save(str(tmp), "JPEG", quality=95, subsampling=0)
    else:
        im.save(str(tmp), "PNG", compress_level=6)
    os.replace(str(tmp), str(dst))
    return time.time() - t0


def post_range(episode, workdir, a, b, scale=1.0, force=False, blur=True, quiet=False):
    """Raw frames a..b -> frames_oneshot/. Returns (done, skipped, missing_raw, seconds)."""
    wd = Path(workdir)
    raw, out = wd / RAW_DIR, wd / OUT_DIR
    size = final_size(episode, scale)
    table = blur_table(wd)[0] if blur else {}
    done = skipped = missing = 0
    t0 = time.time()
    for f in range(a, b + 1):
        s, d = raw / ("%04d.jpg" % f), out / ("%04d.jpg" % f)
        if not s.exists():
            missing += 1
            continue
        if d.exists() and not force:
            skipped += 1
            continue
        process_file(s, d, size, table.get(f))
        done += 1
    dt = time.time() - t0
    if not quiet:
        print("[fast_post] f%d-%d -> %s at %dx%d: %d written, %d skipped, %d raw missing, %.1fs (%.2fs/frame)" % (
            a, b, out, size[0], size[1], done, skipped, missing, dt, dt / max(1, done)))
    return done, skipped, missing, dt


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("episode")
    ap.add_argument("workdir")
    ap.add_argument("--range", default="", help="global frames A-B (default: every raw frame)")
    ap.add_argument("--scale", type=float, default=1.0, help="FINAL scale (same as the render's --scale)")
    ap.add_argument("--force", action="store_true", help="rewrite existing frames_oneshot/ frames")
    ap.add_argument("--no-blur", action="store_true")
    a = ap.parse_args()
    wd = Path(a.workdir)
    if a.range:
        lo, hi = [int(x) for x in a.range.split("-")]
    else:
        nums = sorted(int(p.stem) for p in (wd / RAW_DIR).glob("[0-9][0-9][0-9][0-9].jpg"))
        if not nums:
            raise SystemExit("no raw frames in %s" % (wd / RAW_DIR))
        lo, hi = nums[0], nums[-1]
    post_range(a.episode, wd, lo, hi, a.scale, a.force, not a.no_blur)


if __name__ == "__main__":
    main()
