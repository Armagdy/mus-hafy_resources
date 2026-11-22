# -*- coding: utf-8 -*-
"""Measure residual Y offset of the final fits (per ayah-line segment).

The y transform was fit on line CENTERS; the emitted boxes use the mapped
DB per-ayah-line (min_y, max_y). Compare those against the detected bands.
"""
import json
import os
import sqlite3
import sys

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, r"D:\apps\quran\mushafy\scripts")
from generate_ayah_bboxes import page_geometry, db_page, ensure_db  # noqa: E402

PAGES_DIR = os.path.join(ROOT, "public", "assets", "mushaf_madinah_images")
con = sqlite3.connect(ensure_db(os.path.join(ROOT, "temp", "bbox-research")))

res = json.load(open(os.path.join(
    ROOT, "temp", "bbox-research", "madinah_ayah_bboxes.json"),
    encoding="utf-8"))
by_page = {p["page"]: p for p in res["pages"]}

TOP, BOT = [], []
sample = [pg for pg in range(3, 605) if pg in by_page][::12]
for pg in sample:
    p = by_page[pg]
    tr = p["transform"]
    sy, ty = tr["sy"], tr["ty"]
    gray = np.array(Image.open(os.path.join(
        PAGES_DIR, "page_%04d.webp" % pg)).convert("L"))
    ink = gray < 205
    (c0, c1), bands, _, _ = page_geometry(gray, 205)
    db_lines, groups, db_extent, first = db_page(con, pg)

    # per-db-line y extents (all glyphs of the line)
    per = {}
    for (ln, s, a, x0, y0, x1, y1) in groups:
        if ln not in per:
            per[ln] = [1e9, -1e9]
        per[ln][0] = min(per[ln][0], y0)
        per[ln][1] = max(per[ln][1], y1)
    for ln in sorted(per):
        if not (0 < ln <= len(bands)):
            continue
        a, b = bands[ln - 1]
        py0 = per[ln][0] * sy + ty
        py1 = per[ln][1] * sy + ty
        TOP.append(a - py0)     # + : ink starts BELOW the mapped db top
        BOT.append(b - py1)     # + : ink ends BELOW the mapped db bottom

T, B = np.array(TOP), np.array(BOT)
print("lines measured: %d" % len(T))
print("top edge: ink_band_top - mapped_db_top   median=%+6.1f p10=%+6.1f p90=%+6.1f"
      % (np.median(T), np.percentile(T, 10), np.percentile(T, 90)))
print("bot edge: ink_band_bot - mapped_db_bot   median=%+6.1f p10=%+6.1f p90=%+6.1f"
      % (np.median(B), np.percentile(B, 10), np.percentile(B, 90)))
print("\n=> mapped db boxes sit %+.1f px (vert) vs ink; height deficit=%.1f px"
      % (np.median((T + B) / 2), np.median(B - T)))
con.close()
