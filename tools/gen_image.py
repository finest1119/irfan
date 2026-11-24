"""Generate an image. Engine order (Irfan, 24 Nov 2026): Codex CLI first (uses the ChatGPT/Codex quota),
fall back to Google Gemini (Nano Banana) only if Codex fails or its quota is depleted.

Usage: .venv/bin/python tools/gen_image.py OUT.png "prompt" [aspect] [gemini-model] [--engine codex|gemini]
  aspect: 1:1, 16:9, 21:9, 9:16 ... (default 1:1)
  gemini-model: default gemini-3-pro-image (Nano Banana Pro) — only used for the Gemini fallback
Notes:
  - Codex is forced to its built-in image_gen tool: MCP servers are disabled (`-c mcp_servers={}`) because the
    Codex Higgsfield app otherwise grabs the request and fails when Higgsfield has no credits.
  - Prints which engine produced the file.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import warnings

warnings.filterwarnings("ignore")
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

args = [a for a in sys.argv[1:] if not a.startswith("--engine")]
engine = "codex"
for a in sys.argv[1:]:
    if a.startswith("--engine"):
        engine = a.split("=", 1)[1] if "=" in a else sys.argv[sys.argv.index(a) + 1]
        if "=" not in a:
            args.remove(engine)
out, prompt = os.path.abspath(args[0]), args[1]
aspect = args[2] if len(args) > 2 else "1:1"
model = args[3] if len(args) > 3 else "gemini-3-pro-image"


def codex(out, prompt, aspect):
    if not shutil.which("codex"):
        return False, "codex not installed"
    work = tempfile.mkdtemp(prefix="codex-img-")
    name = "image.png"
    instr = ("Use ONLY your built-in native image generation tool (image_gen). Do NOT use Higgsfield, codex_apps "
             "or any MCP/app connector. Aspect ratio %s. Create this image: %s\n\nSave the generated image as %s in "
             "the current directory (PNG). Reply only with the saved file path." % (aspect, prompt, name))
    try:
        # Windows: npm installs codex as codex.cmd, which CreateProcess only finds via its full path
        exe = shutil.which("codex") if os.name == "nt" else "codex"
        r = subprocess.run([exe, "exec", "--skip-git-repo-check", "-s", "workspace-write",
                            "-c", "mcp_servers={}", instr], cwd=work, capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired:
        return False, "codex timed out"
    src = os.path.join(work, name)
    if not os.path.exists(src):
        pngs = [f for f in os.listdir(work) if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))]
        src = os.path.join(work, pngs[0]) if pngs else None
    if src and os.path.getsize(src) > 1000:
        os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
        shutil.move(src, out)
        shutil.rmtree(work, ignore_errors=True)
        return True, "codex"
    tail = (r.stdout + r.stderr)[-400:]
    shutil.rmtree(work, ignore_errors=True)
    return False, "codex produced no image: " + tail.replace("\n", " ")


def gemini(out, prompt, aspect, model):
    from dotenv import load_dotenv
    from google import genai
    from google.genai import types
    load_dotenv(os.path.join(ROOT, ".env"))
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    resp = client.models.generate_content(
        model=model, contents=prompt,
        config=types.GenerateContentConfig(response_modalities=["IMAGE"],
                                           image_config=types.ImageConfig(aspect_ratio=aspect)))
    for part in resp.candidates[0].content.parts:
        if part.inline_data:
            os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
            with open(out, "wb") as f:
                f.write(part.inline_data.data)
            return True, "gemini:" + model
    return False, "gemini returned no image: " + str(resp)[:300]


if engine == "codex":
    ok, how = codex(out, prompt, aspect)
    if not ok:
        print("codex failed (%s) -> falling back to Gemini" % how, file=sys.stderr)
        ok, how = gemini(out, prompt, aspect, model)
else:
    ok, how = gemini(out, prompt, aspect, model)
if not ok:
    sys.exit(how)
print("saved", out, "via", how)
