# -*- coding: utf-8 -*-
"""
Prepare phone-friendly review: downscale the tashel/mwdoa overlay PNGs to
~900px WebP, upload each to catbox individually (direct image links — proven
to work on the user's phone), then build a TINY index.html that references
them by URL (streams like normal images instead of a 4MB base64 blob).
"""
import os
import subprocess
import time

from PIL import Image

WORK = r"D:\apps\quran\mushafy\temp\bbox-research"

CARDS = [
    ("tashel", 1, "Al-Fatiha page — tashel's page 1 is REAL content (unlike madinah)."),
    ("tashel", 2, "Baqarah start — residual ~6 px."),
    ("tashel", 3, "Full text page — index fit."),
    ("tashel", 106, "Surah-header page (4:176 lines 1-5, header at 6-7)."),
    ("tashel", 300, "Dense page — main validation page."),
    ("tashel", 431, "The one page with a higher residual (32 px) — check extra carefully."),
    ("tashel", 604, "Final page with three surahs."),
    ("mwdoa", 2, "Baqarah start — 5 markers = 5 expected ends."),
    ("mwdoa", 3, "Full page — 11 markers = 11 expected."),
    ("mwdoa", 106, "Three ends only — 3 = 3."),
    ("mwdoa", 113, "A RECOVERED page (faded markers, low-threshold retry) — check carefully."),
    ("mwdoa", 300, "Your confirmed marker page. Red ellipses = detected medallions; colored rects = ayah segments."),
    ("mwdoa", 604, "Last page, three surahs — 15 ends (16 raw, lowest-score pruned)."),
]


def upload(path, mime):
    for attempt in range(3):
        try:
            out = subprocess.check_output(
                ["curl", "-s", "--max-time", "300",
                 "-F", "reqtype=fileupload",
                 "-F", "fileToUpload=@%s;type=%s" % (path, mime),
                 "https://catbox.moe/user/api.php"],
                timeout=320).decode().strip()
            if out.startswith("https://"):
                return out
        except Exception as e:
            print("  upload retry (%s): %s" % (attempt, e))
            time.sleep(2)
    return None


links = []
for (mushaf, pg, note) in CARDS:
    src = os.path.join(WORK, "overlays", "%s_p%04d.png" % (mushaf, pg))
    if not os.path.exists(src):
        print("missing:", src)
        continue
    im = Image.open(src)
    w = 900
    h = int(im.height * w / im.width)
    im = im.resize((w, h), Image.LANCZOS)
    webp = os.path.join(WORK, "review_%s_p%04d.webp" % (mushaf, pg))
    im.save(webp, "WEBP", quality=82)
    size = os.path.getsize(webp) / 1024
    url = upload(webp, "image/webp")
    print("%s p%-4d %6.0fKB -> %s" % (mushaf, pg, size, url))
    if url:
        links.append((mushaf, pg, note, url))
    time.sleep(0.5)

# tiny index page referencing the images by URL
cards_html = []
for (mushaf, pg, note, url) in links:
    cls = "card warn" if (mushaf, pg) == ("tashel", 431) else "card"
    cards_html.append(
        '<div class="%s"><h2>%s — page %d</h2><p>%s</p><img src="%s" '
        'alt="%s page %d" loading="lazy"></div>'
        % (cls, mushaf, pg, note, url, mushaf, pg))

html = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>tashel + mwdoa bbox review</title>
<style>
body{font-family:system-ui,sans-serif;background:#101418;color:#e8eaed;margin:0;padding:12px}
h1{font-size:1.15rem;margin:8px 4px 2px}
.sub{color:#9aa0a6;font-size:.85rem;margin:2px 4px 14px}
.card{background:#1b2027;border-radius:12px;padding:10px 12px;margin:14px 0}
.card.warn{border:2px solid #e37400}
.card h2{font-size:1rem;margin:4px 0 2px;color:#8ab4f8}
.card p{color:#bdc1c6;font-size:.8rem;margin:2px 0 8px}
.card img{width:100%;height:auto;border-radius:8px;display:block}
</style></head><body>
<h1>tashel + mwdoa — ayah bounding-box review</h1>
<div class="sub">tashel: classic-layout fit (604/604 pages, ~6 px). mwdoa: golden-medallion marker detection (584/604 pages). Each image loads separately — if one is slow, scroll on.</div>
__CARDS__
</body></html>"""

html = html.replace("__CARDS__", "".join(cards_html))

out_html = os.path.join(WORK, "review_tashel_mwdoa_index.html")
with open(out_html, "w", encoding="utf-8") as f:
    f.write(html)
print("\nindex size: %.0f KB" % (os.path.getsize(out_html) / 1024))
idx_url = upload(out_html, "text/html")
print("INDEX:", idx_url)
with open(os.path.join(WORK, "review_links.txt"), "w") as f:
    for (mushaf, pg, note, url) in links:
        f.write("%s p%d: %s\n" % (mushaf, pg, url))
    f.write("INDEX: %s\n" % idx_url)
