# -*- coding: utf-8 -*-
"""Self-contained review gallery for the tashel + mwdoa bbox outputs."""
import base64
import io
import os
from PIL import Image

WORK = r"D:\apps\quran\mushafy\temp\bbox-research"

CAPTIONS = {
    ("tashel", 1): "Al-Fatiha page — tashel's page 1 is REAL content (unlike madinah).",
    ("tashel", 2): "Baqarah start — pages fit, residual ~6 px.",
    ("tashel", 3): "Full text page — index fit.",
    ("tashel", 106): "Surah-header page (4:176 lines 1-5, header at 6-7).",
    ("tashel", 300): "Dense page — main validation page.",
    ("tashel", 431): "The one page with a higher residual (32 px) — check this one extra carefully.",
    ("tashel", 604): "Final page with three surahs.",
    ("mwdoa", 2): "Baqarah start — 5 markers = 5 expected ends.",
    ("mwdoa", 3): "Full page — 11 markers = 11 expected.",
    ("mwdoa", 106): "Three ends only (4:176, 5:1, 5:2) — 3 = 3.",
    ("mwdoa", 113): "A RECOVERED page (faded markers, low-threshold retry) — worth a close look.",
    ("mwdoa", 300): "Your confirmed marker is here (row 11 col 8). Red ellipses = detected medallions; colored rects = generated ayah segments.",
    ("mwdoa", 604): "Last page, three surahs — 15 ends (16 raw detections, lowest-score pruned).",
}
KEYS = list(CAPTIONS.keys())


def embed(mushaf, page):
    src = os.path.join(WORK, "overlays", "%s_p%04d.png" % (mushaf, page))
    im = Image.open(src)
    w = 900
    h = int(im.height * w / im.width)
    im = im.resize((w, h), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "WEBP", quality=82)
    return "data:image/webp;base64,%s" % base64.b64encode(buf.getvalue()).decode(), len(buf.getvalue())


cards = []
total = 0
for (mushaf, pg) in KEYS:
    try:
        uri, n = embed(mushaf, pg)
    except FileNotFoundError:
        print("missing overlay:", mushaf, pg)
        continue
    total += n
    note = CAPTIONS[(mushaf, pg)]
    cls = "card warn" if (mushaf, pg) == ("tashel", 431) else "card"
    cards.append(f"""
    <div class="{cls}">
      <h2>{mushaf} — page {pg}</h2>
      <p>{note}</p>
      <img src="{uri}" alt="{mushaf} page {pg}">
    </div>""")

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>tashel + mwdoa bbox review</title>
<style>
  body {{ font-family: system-ui, sans-serif; background: #101418; color: #e8eaed; margin: 0; padding: 12px; }}
  h1 {{ font-size: 1.15rem; margin: 8px 4px 2px; }}
  .sub {{ color: #9aa0a6; font-size: .85rem; margin: 2px 4px 14px; }}
  .card {{ background: #1b2027; border-radius: 12px; padding: 10px 12px; margin: 14px 0; }}
  .card.warn {{ border: 2px solid #e37400; }}
  .card h2 {{ font-size: 1rem; margin: 4px 0 2px; color: #8ab4f8; }}
  .card p {{ color: #bdc1c6; font-size: .8rem; margin: 2px 0 8px; }}
  .card img {{ width: 100%; height: auto; border-radius: 8px; display: block; }}
</style>
</head>
<body>
<h1>tashel + mwdoa (الموضوعي) — ayah bounding-box review</h1>
<div class="sub">tashel: classic-layout fit (like madinah, ~6 px residuals, 604/604 pages). mwdoa: golden-medallion marker detection — red ellipses are the detected end-of-ayah medallions, colored rects the generated per-ayah segments (one color per ayah). Pinch-zoom freely.</div>
{''.join(cards)}
</body>
</html>"""

out = os.path.join(WORK, "review_tashel_mwdoa.html")
with open(out, "w", encoding="utf-8") as f:
    f.write(html)
print("wrote %s (%.2f MB, %d cards)" % (out, os.path.getsize(out) / 1e6, len(cards)))
