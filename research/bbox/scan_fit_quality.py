# -*- coding: utf-8 -*-
"""Scan all madinah pages for paired-fit reliability.

For each page: pair db full-width lines with band text blocks and look at
the scatter of (block left, block right, width ratio). Pages whose full-line
blocks disagree wildly (scattered left edges / ratios) get a different
treatment than pages where every full line spans the same block.
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
from generate_ayah_bboxes import (page_geometry, db_page, ensure_db,
                                  band_text_block)  # noqa: E402

PAGES_DIR = os.path.join(ROOT, "public", "assets", "mushaf_madinah_images")
con = sqlite3.connect(ensure_db(os.path.join(ROOT, "temp", "bbox-research")))

stats = []
for pg in range(3, 605):
    path = os.path.join(PAGES_DIR, "page_%04d.webp" % pg)
    gray = np.array(Image.open(path).convert("L"))
    H, W = gray.shape
    ink = gray < 205
    (c0, c1), bands, _ = page_geometry(gray, 205)
    db_lines, groups, db_extent, first = db_page(con, pg)
    if not groups or not db_extent[0]:
        continue
    per_line_x = {}
    for (ln, s, a, x0, y0, x1, y1) in groups:
        if ln not in per_line_x:
            per_line_x[ln] = [1e9, -1e9]
        per_line_x[ln][0] = min(per_line_x[ln][0], x0)
        per_line_x[ln][1] = max(per_line_x[ln][1], x1)
    db_w = float(db_extent[1] - db_extent[0])
    lefts, rights, ratios = [], [], []
    for ln, (x0, x1) in per_line_x.items():
        if ln in dict() or not (0 < ln <= len(bands)):
            continue
        if (x1 - x0) >= 0.85 * db_w:
            tb = band_text_block(ink, bands[ln - 1][0], bands[ln - 1][1])
            if tb:
                lefts.append(tb[0])
                rights.append(tb[1])
                ratios.append((tb[1] - tb[0]) / (x1 - x0))
    if len(lefts) >= 3:
        stats.append((pg, np.median(lefts), np.median(rights),
                      float(np.median(ratios)),
                      float(np.percentile(lefts, 75) - np.percentile(lefts, 25)),
                      len(lefts)))

ratios_all = np.array([s[3] for s in stats])
print("pages analyzed: %d" % len(stats))
print("median block ratio: %.3f (p5=%.3f p95=%.3f)"
      % (np.median(ratios_all), np.percentile(ratios_all, 5),
         np.percentile(ratios_all, 95)))
print("median left-edge IQR: %.1f px" % np.median([s[4] for s in stats]))

suspects = [s for s in stats if s[3] < 0.60 or s[3] > 0.90 or s[4] > 45]
print("\nsuspect pages (ratio out of range or left-edge scatter > 45px): %d"
      % len(suspects))
for s in suspects:
    print("  p%-3d med_left=%4.0f med_right=%4.0f ratio=%.3f iqr_left=%5.1f n=%d"
          % s)
con.close()
