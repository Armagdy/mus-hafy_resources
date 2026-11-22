# -*- coding: utf-8 -*-
"""Measure the residual systematic offset of the FINAL fits.

For every page: for each DB line with a paired band, compare the mapped
DB line extent against the band's measured text block, and cross-correlate
the mapped DB word-box ink profile against the measured ink profile.

If the DB matches the print, the errors cluster at ~0. A constant nonzero
median = a global calibration offset. Systematic left/right asymmetry =
a scale miscalibration.
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
DB = ensure_db(os.path.join(ROOT, "temp", "bbox-research"))
con = sqlite3.connect(DB)

res = json.load(open(os.path.join(
    ROOT, "temp", "bbox-research", "madinah_ayah_bboxes.json"),
    encoding="utf-8"))
by_page = {p["page"]: p for p in res["pages"]}

L_ERRS, R_ERRS, BEST_DX, RATIOS = [], [], [], []
sample = [pg for pg in range(3, 605) if pg in by_page][::12]
for pg in sample:
    p = by_page[pg]
    tr = p["transform"]
    sx, tx = tr["sx"], tr["tx"]
    gray = np.array(Image.open(os.path.join(
        PAGES_DIR, "page_%04d.webp" % pg)).convert("L"))
    ink = gray < 205
    (c0, c1), bands, _, strip = page_geometry(gray, 205)
    db_lines, groups, db_extent, first = db_page(con, pg)

    per = {}
    words = {}
    for (ln, s, a, x0, y0, x1, y1) in groups:
        if ln not in per:
            per[ln] = [1e9, -1e9]
        per[ln][0] = min(per[ln][0], x0)
        per[ln][1] = max(per[ln][1], x1)
        words.setdefault(ln, []).append((x0, x1))

    for ln in sorted(per):
        if not (0 < ln <= len(bands)):
            continue
        a, b = bands[ln - 1]
        tb = band_text_block(ink, a, b, exclude=strip)
        if not tb:
            continue
        il, ir = tb
        px0 = per[ln][0] * sx + tx
        px1 = per[ln][1] * sx + tx
        L_ERRS.append(il - px0)
        R_ERRS.append(ir - px1)

        # word-profile correlation
        band = ink[a:b]
        colsum = band.sum(axis=0) / float(b - a)
        xs = np.arange(il, ir + 1)
        if len(xs) < 60:
            continue
        db_at = (xs - tx) / sx
        pred = np.zeros(len(db_at), bool)
        for (x0, x1) in words[ln]:
            pred = pred | ((db_at >= x0) & (db_at <= x1))
        cors = {}
        for dx in range(-30, 31):
            l2, r2 = il + dx, ir + dx
            if l2 < 0 or r2 >= gray.shape[1]:
                continue
            mm = (colsum[l2:r2 + 1] > 0.06).astype(float)
            if mm.std() < 1e-9:
                continue
            cc = np.corrcoef(pred.astype(float), mm)[0, 1]
            if not np.isnan(cc):
                cors[dx] = cc
        if 0 in cors and len(cors) >= 40:
            bdx = max(cors, key=cors.get)
            BEST_DX.append(bdx)
            RATIOS.append(cors[0] / max(1e-9, cors[bdx]))

L, R, D = (np.array(x) for x in (L_ERRS, R_ERRS, BEST_DX))
print("lines measured: %d (pages %d..%d)" % (len(L), sample[0], sample[-1]))
print("left edge err  (ink - mapped_db):  median=%+6.1f  p10=%+6.1f  p90=%+6.1f"
      % (np.median(L), np.percentile(L, 10), np.percentile(L, 90)))
print("right edge err (ink - mapped_db):  median=%+6.1f  p10=%+6.1f  p90=%+6.1f"
      % (np.median(R), np.percentile(R, 10), np.percentile(R, 90)))
print("word-profile best shift: median=%+6.1f  p10=%+6.1f  p90=%+6.1f"
      "  corr(0)/corr(best) median=%.2f"
      % (np.median(D), np.percentile(D, 10), np.percentile(D, 90),
         np.median(RATIOS)))
print("\nconstant translation would be (L+R)/2 median = %+.1f px"
      % np.median((L + R) / 2))
print("scale component (L-R)/2 median = %+.1f px (+: box too wide)"
      % np.median((L - R) / 2))
con.close()
