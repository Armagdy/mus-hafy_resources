# -*- coding: utf-8 -*-
"""Build a phone-friendly review gallery for the madinah bbox overlays."""
import base64
import io
import os
from PIL import Image

WORK = r"D:\apps\quran\mushafy\temp\bbox-research"

# page -> caption
CAPTIONS = {
    1: "ANOMALY — near-identical ornament page (no text structure). DB expects Al-Fatiha here. Needs your decision.",
    2: "ANOMALY — twin ornament page (52% identical pixels to page 1). DB expects Baqarah 1:1-1:5 here. Needs your decision.",
    3: "Clean full-text page — index fit, residual 8.4 px. Boxes should sit on the ayahs.",
    50: "Surah-header page (Al-A'raf starts mid-page) — fit residual 5.4 px. Check the header band has NO box (correct) and text below aligns.",
    106: "Surah-header page — 4:176 on lines 1-5, header at 6-7, Surah 5 below. Residual ~5 px.",
    187: "Previously tricky page (multi-layer frame) — now fitted, residual 4.1 px.",
    300: "Dense full page (Al-Kahf 18:54-18:61, 15 lines) — residual 5.2 px. The page used for most validation.",
    551: "Header page — 60:12-13 on lines 1-6, header at 7, Surah 61 below. Residual ~4 px.",
    585: "Previously tricky page — now fitted, residual 5.9 px.",
    604: "Final page with THREE surahs (112-114) — 3 headers, residual ~7.3 px.",
}
KEY_PAGES = list(CAPTIONS.keys())

# other overlays available on the server (linked, not embedded)
ALL_PAGES = sorted(
    int(f.split("_p")[1].split(".")[0])
    for f in os.listdir(os.path.join(WORK, "overlays"))
    if f.startswith("madinah_p"))


def embed(page):
    src = os.path.join(WORK, "overlays", "madinah_p%04d.png" % page)
    im = Image.open(src)
    w = 900
    h = int(im.height * w / im.width)
    im = im.resize((w, h), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "WEBP", quality=82)
    data = base64.b64encode(buf.getvalue()).decode("ascii")
    return "data:image/webp;base64,%s" % data, len(buf.getvalue())


cards = []
total = 0
for pg in KEY_PAGES:
    src_full = "overlays/madinah_p%04d.png" % pg
    uri, nbytes = embed(pg)
    total += nbytes
    note = CAPTIONS[pg]
    cls = "card bad" if pg in (1, 2) else "card"
    cards.append(f"""
    <div class="{cls}">
      <h2>Page {pg} <a class="full" href="{src_full}" target="_blank">open full-resolution ↗</a></h2>
      <p>{note}</p>
      <a href="{src_full}" target="_blank"><img src="{uri}" alt="page {pg} overlay"></a>
    </div>""")

other_links = ", ".join(
    '<a href="overlays/madinah_p%04d.png" target="_blank">%d</a>' % (p, p)
    for p in ALL_PAGES if p not in KEY_PAGES)

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
  .full {{ font-size: .75rem; color: #8ab4f8; text-decoration: none; float: right; }}
  .others {{ background: #1b2027; border-radius: 12px; padding: 10px 12px; font-size: .85rem; line-height: 2; }}
  .others a {{ color: #8ab4f8; }}
  .stats {{ background: #14202b; border-radius: 12px; padding: 10px 12px; font-size: .8rem; color: #bdc1c6; margin: 12px 0; }}
  .stats b {{ color: #81c995; }}
</style>
</head>
<body>
<h1>Madani mushaf — ayah bounding-box alignment review</h1>
<div class="sub">Boxes come from the classic 1405H word-box database, warped onto your processed page images. One color per ayah; an ayah spanning several lines gets one box per line. <b>If the boxes sit on the text, the dataset is validated.</b></div>
<div class="stats">
Pipeline fit quality (all 604 pages): <b>median line residual 5.8 px</b> · p90 8.1 px · max 11.3 px ·
<b>0 pagination mismatches</b> vs quran-meta-data.json ·
557 pages clean index-fit · 45 auto-repaired · 2 flagged (pages 1-2).
</div>
{''.join(cards)}
<div class="others">
<b>Other sampled pages on this server</b> (full-resolution PNGs, pinch-zoom in your browser):<br>
{other_links}
</div>
<div class="sub">Served from your PC — D:\\apps\\quran\\mushafy\\temp\\bbox-research (scripts: scripts/generate_ayah_bboxes.py · output JSON: madinah_ayah_bboxes.json)</div>
</body>
</html>"""

out = os.path.join(WORK, "review.html")
with open(out, "w", encoding="utf-8") as f:
    f.write(html)
print("wrote %s (%.1f MB, %d embedded previews)"
      % (out, os.path.getsize(out) / 1e6, len(KEY_PAGES)))
