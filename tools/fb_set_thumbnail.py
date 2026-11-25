"""Set a custom cover on an existing (uploaded / scheduled / published) Page Reel.

Usage:
  .venv/bin/python tools/fb_set_thumbnail.py <video_id> <image.jpg|png>

Method: POST /{video-id}/thumbnails, multipart `source` (image, <10 MB) + `is_preferred=true`, Page token in the body
(https://developers.facebook.com/docs/graph-api/reference/video/thumbnails/). Uses the same .env credentials and
helper as tools/fb_schedule_reel.py; never prints the token. Records the result in output/api-posts.json if the
video is listed there.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fb_schedule_reel as R  # noqa: E402


def main(video_id, image):
    if not os.path.exists(image):
        sys.exit("image not found: %s" % image)
    if os.path.getsize(image) >= 10 * 1024 * 1024:
        sys.exit("image must be < 10 MB")
    r = R.set_thumbnail(video_id, image)
    print("thumbnail:", r)
    if os.path.exists(R.STATE):
        st = json.load(open(R.STATE))
        for rec in st:
            if rec.get("video_id") == video_id:
                rec.update(thumb=os.path.basename(image), thumb_result=r)
                json.dump(st, open(R.STATE, "w"), indent=1)
                break
    if "ERR" in r:
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
