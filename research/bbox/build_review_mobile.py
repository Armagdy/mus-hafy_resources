# -*- coding: utf-8 -*-
"""Build a fully self-contained, phone-friendly review gallery.
Embedded previews are ~native resolution, so no external files are needed."""
import base64
import io
import os
from PIL import Image

WORK = r"D:\apps\quran\mushafy\temp\bbox-research"

CAPTIONS = {
    1: "ANOMALY — near-identical ornament page (no text structure). DB expects Al-Fatiha here. Needs your decision.",
    2: "ANOMALY — twin ornament page (52% identical pixels to page 1). DB expects Baqarah 1:1-1:5 here. Needs your decision.",
    3: "Clean full-text page — index fit, residual 8.4 px. Boxes should sit on the ayahs.",
    50: "Surah-header page (Al-A'raf starts mid-page) — residual 5.4 px. The header band correctly has NO box; text below should align.",
    106: "Surah-header page — 4:176 on lines 1-5, header at lines 6-7, Surah 5 below. Residual ~5 px.",
    187: "Previously tricky page (multi-layer ornamental frame) — auto-repaired, residual 4.1 px.",
    300: "Dense full page (Al-Kahf 18:54-18:61, 15 lines) — residual 5.2 px. The main validation page.",
    551: "Header page — 60:12-13 on lines 1-6, header at line 7, Surah 61 below. Residual ~4 px.",
    585: "Previously tricky page — auto-repaired, residual 5.9 px.",
    604: "Final page with THREE surahs (112-114) — three headers, residual ~7.3 px.",
}
KEY_PAGES = list(CAPTIONS.keys())


def embed(page, max_w=1080, quality=85):
    src = os.path.join(WORK, "overlays", "madinah_p%04d.png" % page)
    im = Image.open(src)
    if im.width > max_w:
        im = im.resize((max_w, int(im.height * max_w / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "WEBP", quality=quality, method=6)
    data = base64.b64encode(buf.getvalue()).decode("ascii")
    return "data:image/webp;base64,%s" % data, len(buf.getvalue())


cards = []
total = 0
for pg in KEY_PAGES:
    uri, nbytes = embed(pg)
    total += nbytes
    note = CAPTIONS[pg]
    cls = "card bad" if pg in (1, 2) else "card"
    cards.append(f"""
    <div class="{cls}">
      <h2>Page {pg}</h2>
      <p>{note}</p>
      <img src="{uri}" alt="page {pg} overlay">
    </div>""")

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Madinah ayah-bbox review</title>
<style>
  body {{ font-family: system-ui, sans-serif; background: #101418; color: #e8eaed; margin: 0; padding: 12px; }}
  h1 {{ font-size: 1.15rem; margin: 8px 4px 2px; }}
  .sub {{ color: #9aa0a6; font-size: .85rem; margin: 2px 4px 14px; }}
  .card {{ background: #1b2027; border-radius: 12px; padding: 10px 12px; margin: 14px 0; }}
  .card.bad {{ border: 2px solid #e37400; }}
  .card h2 {{ font-size: 1rem; margin: 4px 0 2px; }}
  .card p {{ color: #bdc1c6; font-size: .8rem; margin: 2px 0 8px; }}
  .card img {{ width: 100%; height: auto; border-radius: 8px; display: block; }}
  .stats {{ background: #14202b; border-radius: 12px; padding: 10px 12px; font-size: .8rem; color: #bdc1c6; margin: 12px 0; }}
  .stats b {{ color: #81c995; }}
</style>
</head>
<body>
<h1>Madani mushaf — ayah bounding-box alignment review</h1>
<div class="sub">Boxes come from the classic 1405H word-box database, warped onto your processed page images (page images ~native resolution — pinch-zoom freely). One color per ayah; an ayah spanning several lines gets one box per line. <b>If the boxes sit on the text, the dataset is validated.</b></div>
<div class="stats">
Pipeline fit quality (all 604 pages): <b>median line residual 5.8 px</b> · p90 8.1 px · max 11.3 px ·
<b>0 pagination mismatches</b> vs quran-meta-data.json ·
557 pages clean index-fit · 45 auto-repaired · 2 flagged (pages 1-2).
</div>
{''.join(cards)}
<div class="sub">Generated from D:\\apps\\quran\\mushafy — scripts/generate_ayah_bboxes.py · full output: temp/bbox-research/madinah_ayah_bboxes.json (604 pages, normalized segments). Temporary hosting link — save the file if you want to keep it.</div>
</body>
</html>"""

out = os.path.join(WORK, "review_mobile.html")
with open(out, "w", encoding="utf-8") as f:
    f.write(html)
print("wrote %s (%.2f MB, %d embedded pages, %.2f MB image payload)"
      % (out, os.path.getsize(out) / 1e6, len(KEY_PAGES), total / 1e6))
