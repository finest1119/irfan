"""Generate an image with Nano Banana (Gemini image models).

Usage: .venv/bin/python tools/gen_image.py OUT.png "prompt" [aspect] [model]
  aspect: 1:1, 16:9, 21:9, 9:16 ... (default 1:1)
  model:  default gemini-3-pro-image (Nano Banana Pro)
"""
import os
import sys
import warnings

warnings.filterwarnings("ignore")
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
out, prompt = sys.argv[1], sys.argv[2]
aspect = sys.argv[3] if len(sys.argv) > 3 else "1:1"
model = sys.argv[4] if len(sys.argv) > 4 else "gemini-3-pro-image"

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
resp = client.models.generate_content(
    model=model,
    contents=prompt,
    config=types.GenerateContentConfig(
        response_modalities=["IMAGE"],
        image_config=types.ImageConfig(aspect_ratio=aspect),
    ),
)
for part in resp.candidates[0].content.parts:
    if part.inline_data:
        os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
        with open(out, "wb") as f:
            f.write(part.inline_data.data)
        print("saved", out)
        break
else:
    sys.exit("no image returned: " + str(resp)[:500])
