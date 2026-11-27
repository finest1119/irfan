"""Prepare a weekly compilation and chapter list. Publishing requires a separate title approval."""
import argparse
from datetime import date, datetime, timedelta
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import textwrap
from zoneinfo import ZoneInfo

from yt_upload import PAGES, PRIVATE, READY, lock, read, save, timestamp
from youtube_api import Uploader, API, checked
import requests

MYT = ZoneInfo("Asia/Kuala_Lumpur")
THEMES = {
    "wjh": "What Happens When Everyday Systems Reach Their Limits",
    "sme": "The Physics Behind Backyard Machines",
    "ed": "Hidden Science in the Things You Use Every Day",
}


def select(items):
    # Keep the highest total views for each feasible segment count and running time.
    best = {(0, 0): (0, [])}
    for item in items:
        length = round(item["duration"] * 10)
        for (count, duration), (score, group) in list(best.items()):
            key = (count + 1, duration + length)
            if key[0] > 12 or key[1] > 7200:
                continue
            total = score + int(item["views"] or 0)
            if key not in best or total > best[key][0]:
                best[key] = (total, group + [item])
    possible = [value for (count, _), value in best.items() if count >= 6
                and 480 <= sum(i["duration"] for i in value[1]) <= 719.5]
    return max(possible, key=lambda v: v[0])[1] if possible else []


def render(items, out, ffmpeg):
    fonts = [Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
             Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")]
    font = next((p for p in fonts if p.exists()), None)
    if not font:
        raise ValueError("Install Arial Bold or DejaVu Sans Bold")
    totals = []
    with tempfile.TemporaryDirectory(dir=out) as scratch:
        tmp = Path(scratch)
        shutil.copyfile(font, tmp / "font.ttf")
        for n, item in enumerate(items):
            text = "\n".join(textwrap.wrap(item["title"], width=21))
            (tmp / "title.txt").write_text(text)
            filt = ("[0:v]fps=30,setsar=1,split[bg][fg];"
                    "[bg]scale=480:270:force_original_aspect_ratio=increase,crop=480:270,"
                    "gblur=sigma=12,eq=brightness=-0.15,scale=1920:1080[b];"
                    "[fg]scale=-2:1080[f];[b][f]overlay=(W-w)/2:0,"
                    "drawtext=fontfile=font.ttf:textfile=title.txt:expansion=none:"
                    "fontcolor=white:fontsize=41:line_spacing=10:x=(650-tw)/2:y=(h-th)/2:"
                    "shadowcolor=black@0.7:shadowx=2:shadowy=2[v]")
            seg = tmp / f"{n}.mp4"
            subprocess.run([ffmpeg, "-nostdin", "-loglevel", "error", "-i", str(item["video"]),
                            "-filter_complex", filt, "-map", "[v]", "-map", "0:a:0", "-af", "aresample=48000,apad",
                            "-shortest", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "22",
                            "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "48000", "-ac", "2", str(seg)],
                           cwd=tmp, check=True)
            totals.append(float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries",
                "format=duration", "-of", "csv=p=0", str(seg)])))
        if not 480 <= sum(totals) <= 720:
            raise ValueError("Rendered duration outside the 8–12 minute window")
        (tmp / "clips.txt").write_text("".join(f"file '{n}.mp4'\n" for n in range(len(items))))
        subprocess.run([ffmpeg, "-nostdin", "-loglevel", "error", "-f", "concat", "-safe", "1", "-i",
                        "clips.txt", "-c", "copy", "-movflags", "+faststart", "compiled.mp4"], cwd=tmp, check=True)
        (tmp / "compiled.mp4").replace(out / "video.mp4")
    return totals


def weekly(page, start, preview, do_render):
    if start.weekday() != 0:
        raise ValueError("--week must be a Monday")
    end = start + timedelta(days=7)
    items = []
    states = read(PRIVATE / (page + ".state.json"), {})
    held = set(read(PRIVATE / "hold.json", {}).get(page, []))
    for path in (READY / page).glob("*/metadata.json"):
        m = read(path, {})
        vid = m["facebook_id"]
        if vid in held or not m["facebook_published"]:
            continue
        if preview and not start <= timestamp(m["facebook_time"]).astimezone(MYT).date() < end:
            continue
        if not preview and not states.get(vid, {}).get("youtube_id"):
            continue
        m["video"] = path.with_name("video.mp4")
        items.append(m)
    if items and not preview:
        uploader = Uploader(page, PAGES[page][3])
        lookup = {states[i["facebook_id"]]["youtube_id"]: i for i in items}
        items = []
        ids = list(lookup)
        for i in range(0, len(ids), 50):
            found = checked(requests.get(API + "videos", params={"part": "statistics,snippet,status",
                "id": ",".join(ids[i:i + 50])}, headers=uploader.headers, timeout=40))
            for v in found["items"]:
                published = timestamp(v["snippet"]["publishedAt"]).astimezone(MYT).date()
                if v["status"]["privacyStatus"] == "public" and start <= published < end:
                    m = lookup[v["id"]]
                    m["views"] = int(v["statistics"].get("viewCount", 0))
                    items.append(m)
    chosen = select(sorted(items, key=lambda i: (-int(i["views"] or 0), i["facebook_id"])))
    if not chosen:
        print(page, "insufficient eligible footage for 6–12 segments totalling 8–12 minutes")
        return
    out = READY / "weekly" / page / (str(start) + ("-facebook-preview" if preview else ""))
    out.mkdir(parents=True, exist_ok=True)
    order = [i["facebook_id"] for i in chosen]
    previous = read(out / "selection.json", {})
    if (out / "video.mp4").exists():
        print(page, "existing render:", out)
        return
    lengths = [i["duration"] for i in chosen]
    if do_render:
        ffmpeg = os.environ.get("YOUTUBE_FFMPEG") or read(PRIVATE / "runtime.json", {}).get("ffmpeg", "ffmpeg")
        filters = subprocess.check_output([ffmpeg, "-hide_banner", "-filters"], stderr=subprocess.DEVNULL)
        if b"drawtext" not in filters:
            raise ValueError("Set YOUTUBE_FFMPEG to a build with drawtext")
        lengths = render(chosen, out, ffmpeg)
    elapsed = 0
    chapters = []
    for item, length in zip(chosen, lengths):
        seconds = int(elapsed)
        chapters.append(f"{seconds // 60:02}:{seconds % 60:02} {item['title']}")
        elapsed += length
    theme = THEMES[page]
    if page == "ed" and all(i["copy_source"] == "Facebook" for i in chosen):
        theme = "The Surprising Scale of the World Around Us"
    if previous.get("ids") == order:
        theme = previous.get("proposed_title", theme)
    save(out / "selection.json", dict(proposed_title=theme, ids=order, seconds=elapsed,
         ranking="Facebook views" if preview else "YouTube views", title_approval="pending"))
    (out / "description.txt").write_text(theme + "\n\n" + "\n".join(chapters) + "\n\n#Explained\n")
    print(page, theme, len(chosen), round(elapsed), out)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--page", required=True, choices=PAGES)
    today = datetime.now(MYT).date()
    parser.add_argument("--week", type=date.fromisoformat, default=today-timedelta(days=today.weekday()+7))
    parser.add_argument("--facebook-preview", action="store_true", help="Rank local Facebook sources before YouTube launch")
    parser.add_argument("--render", action="store_true")
    args = parser.parse_args()
    os.umask(0o077)
    try:
        with lock(args.page):
            weekly(args.page, args.week, args.facebook_preview, args.render)
    except Exception as exc:
        raise SystemExit(str(exc) if type(exc) in (RuntimeError, ValueError) else type(exc).__name__) from None
