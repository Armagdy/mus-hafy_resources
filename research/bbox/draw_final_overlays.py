# -*- coding: utf-8 -*-
"""Draw the FINAL app asset segments over the page images (what ships)."""
import json
import os
import sys

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MUSHAFA = {
    "madinah": ("public/assets/mushaf_madinah_images", 205),
    "tashel": ("public/assets/mushaf_tashel_pages", 140),
}

mushaf = sys.argv[1] if len(sys.argv) > 1 else "madinah"
pages = [int(x) for x in sys.argv[2:]] or [564]

pages_dir, _ = MUSHAFA[mushaf]
data = json.load(open(os.path.join(
    ROOT, "public", "assets", "ayah-bboxes", "%s.json" % mushaf),
    encoding="utf-8"))

out_dir = os.path.join(ROOT, "temp", "bbox-research", "overlays")
os.makedirs(out_dir, exist_ok=True)
pal = [(230, 25, 75), (60, 180, 75), (0, 130, 200), (245, 130, 48),
       (145, 30, 180), (70, 240, 240), (240, 50, 230), (210, 245, 60)]

for pg in pages:
    entries = data["pages"].get(str(pg))
    if not entries:
        print("p%d: no data" % pg)
        continue
    img_path = os.path.join(ROOT, pages_dir, "page_%04d.webp" % pg)
    im = Image.open(img_path).convert("RGB")
    W, H = im.size
    dr = ImageDraw.Draw(im, "RGBA")
    for i, e in enumerate(entries):
        for (x, y, w, h) in e["seg"]:
            dr.rectangle((x * W, y * H, (x + w) * W, (y + h) * H),
                          outline=pal[i % len(pal)], width=3)
    out = os.path.join(out_dir, "final_%s_p%04d.png" % (mushaf, pg))
    im.save(out)
    print("wrote %s (%d ayahs)" % (out, len(entries)))
