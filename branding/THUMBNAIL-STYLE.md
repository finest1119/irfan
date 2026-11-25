# Reels Cover Style Spec (reference: "The World Decoded")
Source: facebook.com/profile.php?id=61595892121610, Reels tab, studied 25 Nov 2026 (~30 covers). Screenshots: `thumbnail-reference/`.

## The reference Page
- **The World Decoded**: 73K followers, "Science, technology and engineering". Short explainers built from **stylised 3D renders**, the same format we make.
- **Top reels:** 16M (jet "FALL"), 2.1M (crane "GET DOWN?"), 1.2M (elevator "JUST SNAPPED"), 1.1M (jet "BREAK APART"), 559K (solar), 459K (tire), 310K (dishes).
- **Typical:** 30K–80K. **Lowest:** 3.6K (NSA), 7K (gearbox), 8.1K (microwave), 8.8K (foot), 9K (FBI).

## Image
- A **real frame from the reel's own 3D scene**, with the hero object at the moment of drama: a jet tumbling, an elevator cab dropping with screaming people, a crane on a skyscraper roof. No faces or emotion shots (one real-photo exception: Jensen Huang, 68K). No before/after layouts.
- **Medium zoom:** the hero object fills about 40–60% of the frame width and sits in the lower 55–60%, so the text has clean space above it. The camera often looks slightly down or is tilted for drama.
- **Bright and saturated:** clean daylight renders with blue sky, or a dark navy/purple background with a lit object. Colours are punchy but not neon. The background is simple enough for text to read over it.
- **Three templates:** (A) full-bleed scene with text on top, used by all the top performers. (B) "Editorial": a cream paper header with a torn bottom edge over the scene, 42K–559K. (C) A flat neon background (green, pink, orange or red) with the image in an arch window. Template C is consistently weak, about 8K–45K.

## Text hook
- **Two tiers:**
  1. A **setup line** of 2–5 words in sentence case, e.g. "The elevator cable", "How does the crane". It is white heavy sans on dark scenes, or black text on a white box when the scene is busy.
  2. A **payoff** of 1–3 words in ALL CAPS, at about 1.5–2× the setup size, e.g. "JUST SNAPPED", "GET DOWN?".
- **Total length:** 4–8 words. A third micro-line, about 0.5× size, is used only for context ("inside your washer", "every US cop uses").
- **Font:** a geometric heavy sans (Montserrat/Poppins ExtraBold–Black style). It is not condensed and has tight leading.
- **Payoff styling:** the payoff sits in a **solid highlight box**, one box per line, slightly staggered like stickers, with no stroke. Box colours: orange-red #F2542D, cyan/teal #1FB5C9, royal blue #2D6BE4, green #22B14C or yellow #FFD21F. Text is white, or black on yellow/cyan. The other option is coloured text without a box: red #E63030 or yellow #FFC21A on a dark sky.
- **No stroke or outline.** There is only a faint soft shadow, or none. Readability comes from the box or a dark background.
- **Position:** the top 12–40% of the frame, centred, with the block about 65–85% of frame width. It never overlaps the hero object.

## Hook-wording patterns (real covers)
- "What could make a jet / FALL from the sky?" (16M): question, danger, mystery cause.
- "How does the crane / GET DOWN?" (2.1M): question about an everyday mystery that everyone has wondered about.
- "The elevator cable / JUST SNAPPED" (1.2M): present-tense disaster that puts you in the moment.
- "Did this jet / BREAK APART in the air?" (1.1M): yes/no question with a visual clue.
- "YOUR SOLAR PANELS / SHUT OFF in a blackout" (559K): "you" plus a counter-intuitive fact.
- "Rinsing your dishes makes them / DIRTIER" (310K): "you" plus a habit-reversal shock.
- "CHANGING A TIRE ON A / 360-TON TRUCK" (459K): a big number for scale.
- "There's / CONCRETE inside your washer": a hidden thing inside a familiar object.
- "Drop uranium in water and / IT BOILS BY ITSELF": cause → surprising effect.
- **Why they work:** a curiosity gap where the payoff word is the surprise; "you/your" makes it personal; numbers give scale; "JUST" adds urgency. The setup line gives context and the caps word delivers the jolt.

## Extras
- **No** arrows, circles, emojis, red X marks or zoom bubbles.
- **Small factual stickers do appear:** a yellow rounded label near the hero object with a true detail ("26,000 feet in 70 seconds", "the clues are this small"), an in-scene tag ("55 lb (25 kg)", "MILITARY RADAR"), a comic burst ("AAAAH!") or a "?" glyph.

## High-view vs low-view
- **High-view covers:** a full-bleed physical scene of motion or danger, a universal everyday mystery, and a question or "just happened" verb.
- **Low-view covers:** abstract or institutional subjects (an NSA building, the FBI seal, a gearbox), politics/news, the flat neon arch template (C), and payoffs that are just a noun ("RADAR", "NO GEARS").

## Recipe for our tool (1080×1920)
- **Image:** a frame rendered from the reel's own 3D scene at its most dramatic true moment. Place the hero object at y 750–1650 and keep y 180–720 calm (sky, wall, dark), so add camera headroom if needed. Grade +10% saturation and +5% contrast. No fake elements that are not in the video.
- **Safe zones:** keep text out of y < 160 and y > 1600, where the FB UI and the view-count overlay sit. Keep 90 px side margins.
- **Setup line:** y 220–330. Montserrat Black (or Poppins ExtraBold), 64–72 px, sentence case. White with a 0 0 12px rgba(0,0,0,.45) shadow, or #111 on a white box (padding 14/24 px, radius 6).
- **Payoff:** y 340–620, 1–3 words, ALL CAPS, Montserrat Black 120–150 px, line-height 1.0, max width 900 px. Put each line in its own box with padding 12/28 px and radius 6. Box colours: our red #E63946 with white text, or yellow #FFD21F with #0B1F3A text, or navy #0B1F3A with white text on a light sky. Use one accent colour per cover.
- **Optional context micro-line:** 40–44 px, under the payoff, white-box style.
- **Optional fact sticker:** yellow #FFD21F rounded box, #111 text, 40 px bold, near the hero (y 1200–1500). Use only a number or fact stated in the video.
- **Total hook:** at most 8 words. A question or a present-tense event is preferred, with "your" where it is honest.
- **Truth rule:** every word must be literally true to the video. A question is allowed only if the video answers it. No invented numbers, events or "JUST" unless it happens in the reel. No arrows, emojis, red X or circles.
