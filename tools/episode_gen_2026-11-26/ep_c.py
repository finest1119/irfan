import json
T = {
 "hook": "On Sunday, November eighth, fire broke out in a high-rise of about forty stories in downtown Taiyuan, in northern China. The flames were out in about two hours. The cause is still under investigation.",
 "question": "So why can fire and smoke move so fast through a tall building? Here are the three big reasons.",
 "one_chimney": "One: the building acts like a chimney. Stairwells, elevator shafts and ducts run from bottom to top. Warm air rises through them and pulls more air in below. Engineers call it the stack effect, and it can carry smoke many floors from the fire.",
 "two_outside": "Two: the outside wall. Flames can break out of a window and heat the floor above. Engineers call it leapfrogging. Some exterior cladding can also burn, giving fire a path up the building.",
 "three_height": "Three: height. Fire truck ladders only reach the lower floors. Above that, firefighters climb the stairs with their gear and connect hoses to pipes built into the building. Every floor costs time.",
 "smoke": "And the biggest danger is often not the flames but the smoke. It can fill hallways and stairwells far from the fire. That is why one closed door matters so much.",
 "protections": "Modern towers fight back: sprinklers, fire doors that close on their own, stairwells kept under pressure to push smoke out, and alarms on every floor.",
 "takeaway": "Takeaway: wherever you stay, count the doors to the nearest stairs. Never take the elevator in a fire. And if smoke blocks your way out, shut the door, seal the gaps and call for help.",
 "outro": "Do you know where the fire stairs are in your building? Tell us in the comments, and send this to someone who lives or works high up. Investigators in Taiyuan are still looking for a cause. But how fire moves through a tall building is no mystery.",
}
print(sum(len(t.split()) for t in T.values()), "words")
shots = {
 "hook": {"builder": "tower_hook", "params": {"mode": "hook"}, "overlays": [
   {"type": "card", "text": "TAIYUAN, CHINA · 8 NOV 2026", "at": 0.2},
   {"type": "chips", "y": 0.61, "items": ["ILLUSTRATION", "HIGH-RISE, ABOUT 40 STORIES", "FLAMES OUT IN ABOUT 2 HOURS", "CAUSE UNDER INVESTIGATION"], "cues": ["sunday", "forty", "flames", "cause"]}]},
 "question": {"builder": "tower_cut", "params": {"mode": "reveal"}, "overlays": [
   {"type": "card", "text": "WHY FIRE SPREADS FAST\nIN TALL BUILDINGS", "at": 0.2}]},
 "one_chimney": {"builder": "tower_cut", "params": {"mode": "stack", "shaft_cue": "stairwells", "warm_cue": "warm", "smoke_cue": "carry"}, "overlays": [
   {"type": "card", "text": "1 · LIKE A CHIMNEY", "cue": "one"},
   {"type": "label", "text": "STAIRWELL", "anchor": "stair", "cue": "stairwells", "until": "engineers", "dx": -60, "dy": -110, "color": "teal"},
   {"type": "label", "text": "ELEVATOR SHAFT", "anchor": "lift", "cue": "elevator", "until": "engineers", "dx": 60, "dy": -110, "color": "teal"},
   {"type": "label", "text": "SMOKE", "anchor": "smoke", "cue": "carry", "dx": 60, "dy": -100},
   {"type": "chips", "items": ["WARM AIR RISES", "THE STACK EFFECT", "SMOKE CAN TRAVEL MANY FLOORS"], "cues": ["warm", "stack", "carry"]}]},
 "two_outside": {"builder": "facade_v2", "params": {"hop_cue": "break", "clad_cue": "cladding"}, "overlays": [
   {"type": "card", "text": "2 · THE OUTSIDE WALL", "cue": "two"},
   {"type": "label", "text": "LEAPFROGGING", "anchor": "glow", "cue": "leapfrogging", "until": "cladding", "dx": -70, "dy": -110, "color": "amber"},
   {"type": "label", "text": "CLADDING", "anchor": "clad", "cue": "cladding", "dx": 70, "dy": -110},
   {"type": "chips", "items": ["FLAMES CAN BREAK OUT OF A WINDOW", "HEAT THE FLOOR ABOVE", "SOME CLADDING CAN BURN"], "cues": ["break", "heat", "cladding"]}]},
 "three_height": {"builder": "ladder_v2", "params": {"ladder_cue": "ladders", "climb_cue": "climb"}, "overlays": [
   {"type": "card", "text": "3 · HEIGHT", "cue": "three"},
   {"type": "label", "text": "LADDER STOPS HERE", "anchor": "ladder", "cue": "lower", "until": "climb", "dx": 70, "dy": -100, "color": "amber"},
   {"type": "label", "text": "STANDPIPE", "anchor": "pipe", "cue": "pipes", "dx": -70, "dy": -110},
   {"type": "chips", "items": ["LADDERS REACH LOWER FLOORS", "FIREFIGHTERS CLIMB WITH GEAR", "EVERY FLOOR COSTS TIME"], "cues": ["ladders", "climb", "every"]}]},
 "smoke": {"builder": "corridor_v2", "params": {"fill_cue": "fill"}, "overlays": [
   {"type": "card", "text": "THE BIGGEST DANGER: SMOKE", "at": 0.15},
   {"type": "label", "text": "CLOSED DOOR", "anchor": "door", "cue": "closed", "dx": 80, "dy": 140, "color": "teal"},
   {"type": "chips", "items": ["IT CAN FILL HALLWAYS AND STAIRS", "ONE CLOSED DOOR MATTERS"], "cues": ["fill", "closed"]}]},
 "protections": {"builder": "tower_cut", "params": {"mode": "protect", "sprinkler_cue": "sprinklers", "door_cue": "doors", "fan_cue": "stairwells", "alarm_cue": "alarms"}, "overlays": [
   {"type": "card", "text": "MODERN TOWERS FIGHT BACK", "at": 0.15},
   {"type": "chips", "style": "check", "y": 0.61, "items": ["SPRINKLERS", "SELF-CLOSING FIRE DOORS", "STAIRWELLS UNDER PRESSURE", "ALARMS ON EVERY FLOOR"], "cues": ["sprinklers", "doors", "stairwells", "alarms"]}]},
 "takeaway": {"builder": "hall_v2", "params": {"count_cue": "count", "stairs_cue": "stairs", "lift_cue": "elevator", "seal_cue": "seal"}, "overlays": [
   {"type": "card", "text": "TAKEAWAY", "at": 0.15},
   {"type": "label", "text": "1", "anchor": "d1", "cue": "count", "until": "never", "dx": -60, "dy": -60, "color": "teal"},
   {"type": "label", "text": "2", "anchor": "d2", "cue": "count", "delay": 0.4, "until": "never", "dx": -60, "dy": -60, "color": "teal"},
   {"type": "label", "text": "3", "anchor": "d3", "cue": "count", "delay": 0.8, "until": "never", "dx": -60, "dy": -60, "color": "teal"},
   {"type": "label", "text": "STAIRS", "anchor": "stairs", "cue": "stairs", "until": "never", "dx": 60, "dy": -90, "color": "teal"},
   {"type": "label", "text": "NO ELEVATOR", "anchor": "lift", "cue": "elevator", "until": "shut", "dx": 60, "dy": -100},
   {"type": "chips", "style": "check", "items": ["COUNT THE DOORS TO THE STAIRS", "NEVER TAKE THE ELEVATOR", "SHUT THE DOOR, SEAL GAPS, CALL"], "cues": ["count", "never", "shut"]}]},
 "outro": {"builder": "tower_hook", "params": {"mode": "outro"}, "overlays": [
   {"type": "card", "text": "WHERE ARE YOUR FIRE STAIRS?", "at": 0.2, "until": "investigators"},
   {"type": "chips", "items": ["TELL US IN THE COMMENTS", "SEND THIS TO SOMEONE UP HIGH"], "cues": ["tell", "send"]},
   {"type": "card", "text": "TAIYUAN:\nCAUSE UNDER INVESTIGATION", "cue": "investigators"}]},
}
ep = {
 "id": "2026-11-26-3-high-rise-fire", "keyword": "high rise fire", "slug": "high-rise-fire",
 "title": "Why Fire Spreads So Fast in Tall Buildings: The Science of High-Rise Fires",
 "fb_caption": "On Sunday 8 November, fire broke out in a high-rise of about 40 storeys in downtown Taiyuan, northern China. The flames were out in about two hours and the cause is still under investigation. So why can fire and smoke move so fast through a tall building? Three big reasons: the stack effect turns shafts and stairwells into a chimney, fire can leapfrog up the outside wall, and height slows firefighters down. Modern towers fight back with sprinklers, self-closing fire doors, pressurised stairwells and alarms. Do you know where the fire stairs are in your building? Tell us below.",
 "hashtags": ["#highrisefire", "#firesafety", "#skyscraper", "#engineering", "#science", "#howitworks", "#newsexplained", "#whatjusthappened"],
 "engagement_comment": "Honest check: do you know how many doors there are between your front door and the nearest fire stairs? 1 = yes, I've counted, 2 = roughly, 3 = no idea. Reply with a number!",
 "sources": [
  "Global Times, 8 Nov 2026 (fire in a high-rise in Taiyuan, Shanxi, about 5 pm Sunday; flames out by about 7 pm; cause under investigation): https://www.globaltimes.cn/page/202611/1373913.shtml",
  "China Daily HK, 9 Nov 2026: https://www.chinadailyhk.com/article/642419",
  "AFP via The Korea Times, 9 Nov 2026: https://www.koreatimes.co.kr/world/20261109/fire-in-china-apartment-building-kills-14-state-media",
  "HNGN, 9 Nov 2026 ('about 40 stories', mixed-use; cause under investigation): https://www.hngn.com/articles/273751/20261109/china-high-rise-fire-taiyuan-kills-14-cause-under-investigation.htm",
  "News of Bahrain citing Reuters, 9 Nov 2026 (40-storey mixed-use building): https://www.newsofbahrain.com/en/article/14-dead-in-chinas-high-rise-fire-tragedy",
  "Explainer (general): US Fire Administration, 'Protecting People Who Live or Work in High-Rises' (fire and smoke spread upward; ladders reach limited floors; sprinklers; pressurised stairwells; do not use elevators; close doors; seal cracks and call): https://usfa.fema.gov/blog/protecting-people-who-live-or-work-in-high-rises ; NIST smoke-movement / stack-effect reports; BRANZ SR32 facade fire spread (leap-frogging); USFA residential fatality data (smoke inhalation).",
  "Not used / not shown: casualty numbers (none in voiceover, captions, overlays or post copy), source headlines or URLs on screen, building name, officials or companies. Visuals: the hook tower is generic with soft grey smoke at lower levels only; the explainer beats use a visibly different generic building; nothing suggests how the Taiyuan fire spread.",
  "Posting-day re-check: confirm no cause has been announced (if it has, change the hook's last sentence and the outro loop line)."],
 "tts": {"model": "gemini-3.8-flash-tts", "fallback_model": "gemini-3.1-flash-tts-preview", "voice": "Fenrir",
   "director_notes": "Male documentary-style news explainer for a US/UK social video. Energetic, confident, punchy and fast (about 170-185 words per minute), conversational but serious and respectful. Short sentences, a brief dramatic pause before key facts, lively intonation, never monotone or salesy.\nPronunciation: Taiyuan = tie-yoo-EN; Shanxi = SHAHN-shee.",
   "pause_between_beats": 0.2, "trim_pauses": True},
 "music": None,
 "render": {"resolution": [1080, 1920], "fps": 30, "samples": 24, "parallel": 3},
 "beats": [{"id": k, "text": T[k], "shot": shots[k]} for k in T],
 "pipeline": "v2"}
json.dump(ep, open("/Users/irfan/Documents/Facebook & Youtube Monetisation/irfan/episodes/2026-11-26-3-high-rise-fire/episode.json", "w"), indent=2, ensure_ascii=False)
