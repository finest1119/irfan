"""Contact sheet for `oneshot.py bench` runs (venv, PIL). One row per bench frame, one column per run.

  python page2/tools/bench_sheet.py WORKDIR default_cycles fast_cycles default_eevee [--out WORKDIR/bench_sheet.jpg]
         [--width 360]

Each name is a folder under WORKDIR/bench/ (= <profile>_<engine><tag>). Labels show the run and its render seconds
for that frame (from bench.json; fast runs also show the post seconds). Pathlib only (Windows-safe).
"""
import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("workdir")
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--out", default=None)
    ap.add_argument("--width", type=int, default=360)
    a = ap.parse_args()
    wd = Path(a.workdir)
    benches = [json.loads((wd / "bench" / r / "bench.json").read_text(encoding="utf-8")) for r in a.runs]
    rows = [(r["frame"], r["shot"]) for r in benches[0]["frames"]]
    cw = a.width
    ch = int(cw * 16 / 9)
    lab = 20
    sheet = Image.new("RGB", (cw * len(a.runs), (ch + lab) * len(rows) + lab), (18, 18, 18))
    d = ImageDraw.Draw(sheet)
    for j, (run, b) in enumerate(zip(a.runs, benches)):
        d.text((j * cw + 4, 4), "%s  mean %s s" % (run, b.get("mean_render_s")), fill=(255, 230, 80))
    for i, (f, shot) in enumerate(rows):
        y = lab + i * (ch + lab)
        for j, (run, b) in enumerate(zip(a.runs, benches)):
            p = wd / "bench" / run / ("f%04d.png" % f)
            if p.exists():
                with Image.open(str(p)) as im:
                    sheet.paste(im.convert("RGB").resize((cw, ch), Image.LANCZOS), (j * cw, y + lab))
            r = next((x for x in b["frames"] if x["frame"] == f), {})
            t = "f%d %s  %ss" % (f, shot, r.get("render_s"))
            if r.get("post_s") is not None:
                t += " +%.2fs post" % r["post_s"]
            d.text((j * cw + 4, y + 4), t, fill=(255, 255, 255))
    out = Path(a.out) if a.out else wd / "bench_sheet.jpg"
    sheet.save(str(out), quality=90)
    print("bench sheet -> %s (%d frames x %d runs)" % (out, len(rows), len(a.runs)))


if __name__ == "__main__":
    main()
