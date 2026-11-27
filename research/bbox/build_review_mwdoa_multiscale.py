# -*- coding: utf-8 -*-
"""Review gallery for the multi-scale mwdoa regeneration: the pages that
were previously flagged (no ayah boxes → no highlighting in the app) and
are now emitted. Embeds the overlay PNGs (red ellipses = detected markers,
colored rects = per-ayah segments) plus the recovered-page list from the
validation run."""
import base64
import io
import json
import os

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CACHE = os.path.join(ROOT, "research", "bbox")
PAGES_DIR = os.path.join(ROOT, "assets", "mushuf_mwdoa_images")

NEW = json.load(open(os.path.join(CACHE, "mwdoa_ayah_bboxes.json"), encoding="utf-8"))
by_page = {p["page"]: p for p in NEW["pages"]}

# review set: every page whose detection needed pass 2 (multi-scale /
# gap fill) + the 20 previously flagged + the first-ayah head-fix pages
# (mwdoa_headfix_pages.json, written by the byte-diff validation).
REVIEW_PAGES = sorted(p["page"] for p in NEW["pages"]
                     if p.get("info", {}).get("multiscale"))
CONTROLS = [241, 243, 300]
PREV_FLAGGED = [160, 233, 242, 253, 279, 292, 319, 339, 345, 368, 375, 384,
                415, 426, 450, 466, 473, 496, 542, 601]
HEADFIX = []
hf_path = os.path.join(CACHE, "mwdoa_headfix_pages.json")
if os.path.exists(hf_path):
    HEADFIX = json.load(open(hf_path, encoding="utf-8"))["pages"]
for pg in PREV_FLAGGED + HEADFIX:
    if pg not in REVIEW_PAGES:
        REVIEW_PAGES.append(pg)
REVIEW_PAGES.sort()
print("review pages:", len(REVIEW_PAGES), "(multiscale + prev-flagged + head-fix:", len(HEADFIX), ")")


def embed_overlay(pg):
    src = os.path.join(CACHE, "overlays", "mwdoa_p%04d.png" % pg)
    im = Image.open(src)
    w = 800
    h = int(im.height * w / im.width)
    im = im.resize((w, h), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "WEBP", quality=75)
    return "data:image/webp;base64,%s" % base64.b64encode(buf.getvalue()).decode()


def caption(pg):
    p = by_page.get(pg)
    if not p:
        return "STILL FLAGGED — no data emitted."
    info = p.get("info", {})
    ay = p["ayahs"]
    rng = "%d:%d..%d:%d" % (ay[0]["surah"], ay[0]["ayah"], ay[-1]["surah"], ay[-1]["ayah"])
    bits = ["%d markers = %d ends" % (info.get("markers", 0), info.get("ending_ayahs", 0))]
    if info.get("multiscale"):
        bits.append("multi-scale sweep")
    if info.get("gap_filled"):
        bits.append("GAP-FILLED (faded markers)")
    if info.get("markers_pruned"):
        bits.append("over-detections score-pruned")
    return "%s — %s" % (rng, ", ".join(bits))


cards = []
for pg in CONTROLS + REVIEW_PAGES:
    try:
        uri = embed_overlay(pg)
    except FileNotFoundError:
        print("missing overlay for page", pg)
        continue
    cls = "card control" if pg in CONTROLS else "card"
    cards.append(f"""
    <div class="{cls}">
      <h2>mwdoa — page {pg}</h2>
      <p>{caption(pg)}</p>
      <img src="{uri}" alt="mwdoa page {pg}">
    </div>""")

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>mwdoa multi-scale recovery review</title>
<style>
  body {{ font-family: system-ui, sans-serif; background: #101418; color: #e8eaed; margin: 0; padding: 12px; }}
  h1 {{ font-size: 1.15rem; margin: 8px 4px 2px; }}
  .sub {{ color: #9aa0a6; font-size: .85rem; margin: 2px 4px 14px; }}
  .card {{ background: #1b2027; border-radius: 12px; padding: 10px 12px; margin: 14px 0; }}
  .card.control {{ border: 2px solid #3aa757; }}
  .card h2 {{ font-size: 1rem; margin: 4px 0 2px; color: #8ab4f8; }}
  .card p {{ color: #bdc1c6; font-size: .8rem; margin: 2px 0 8px; }}
  .card img {{ width: 100%; height: auto; border-radius: 8px; display: block; }}
</style>
</head>
<body>
<h1>mwdoa (الموضوعي) — multi-scale recovery + first-ayah head review</h1>
<div class="sub">Card set 1: the 20 pages previously excluded from the ayah-bbox
asset (no tap selection / no highlighting in the app), regenerated with the
multi-scale template sweep + faded-marker gap fill. Card set 2: the 131 pages
whose FIRST ayah was clipped at the top (the highlight began one or more lines
too low — user-reported on 160/253; the first ayah now starts at the page's top
text band). Green-bordered cards are untouched control pages. Red ellipses =
detected end-of-ayah medallions; colored rects = generated per-ayah segments
(one color per ayah). Pinch-zoom freely; a correct card shows the FIRST color
starting at the very top text line, and every rect ending exactly at its red
medallion.</div>
{''.join(cards)}
</body>
</html>"""

out = os.path.join(CACHE, "review_mwdoa_multiscale.html")
open(out, "w", encoding="utf-8").write(html)
print("wrote %s (%.1f KB, %d cards)" % (out, os.path.getsize(out) / 1024, len(cards)))
