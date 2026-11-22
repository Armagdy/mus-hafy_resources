# -*- coding: utf-8 -*-
"""Per-line best-shift distribution: is the within-line displacement of the
classic DB vs this print a consistent constant (calibratable) or scattered?

For each paired line: slide the DB's word-boundary set over the measured
gaps, find the dx maximizing gap hits. Aggregate the per-line best dx.
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

res = json.load(open(os.path.join(
    ROOT, "temp", "bbox-research", "madinah_ayah_bboxes.json"),
    encoding="utf-8"))
by_page = {p["page"]: p for p in res["pages"]}

BEST, HITS0, HITSB = [], [], []
sample = [pg for pg in range(3, 605) if pg in by_page][::9]
for pg in sample:
    p = by_page[pg]
    tr = p["transform"]
    sx, tx = tr["sx"], tr["tx"]
    gray = np.array(Image.open(os.path.join(
        PAGES_DIR, "page_%04d.webp" % pg)).convert("L"))
    ink = gray < 205
    (c0, c1), bands, _, strip = page_geometry(gray, 205)
    db_lines, groups, db_extent, first = db_page(con, pg)

    words = {}
    for (ln, s, a, x0, y0, x1, y1) in groups:
        words.setdefault(ln, []).append((x0, x1))

    for ln in sorted(words):
        if not (0 < ln <= len(bands)) or len(words[ln]) < 3:
            continue
        a, b = bands[ln - 1]
        tb = band_text_block(ink, a, b, exclude=strip)
        if not tb:
            continue
        il, ir = tb
        band = ink[a:b]
        colsum = band.sum(axis=0)
        inside = colsum[il:ir + 1] == 0
        gaps, st = [], None
        for i, v in enumerate(inside):
            if v and st is None:
                st = i
            elif not v and st is not None:
                if i - st >= 3:
                    gaps.append((il + st, il + i - 1))
                st = None
        if len(gaps) < 2:
            continue
        xs = sorted(words[ln])
        bounds = [((x1a + x0b) / 2.0) * sx + tx
                  for (x0a, x1a), (x0b, x1b) in zip(xs, xs[1:])]

        def score(dx):
            return sum(any(g[0] - 5 <= wx + dx <= g[1] + 5 for g in gaps)
                       for wx in bounds)

        s0 = score(0)
        best_dx, best_s = 0, s0
        for dx in range(-40, 41, 2):
            s = score(dx)
            if s > best_s:
                best_dx, best_s = dx, s
        if best_s > 0 or s0 > 0:
            BEST.append(best_dx)
            HITS0.append(s0)
            HITSB.append(best_s)

B = np.array(BEST)
print("lines analyzed: %d" % len(B))
print("per-line best dx: median=%+.0f  p10=%+.0f  p90=%+.0f  mean=%+.1f"
      % (np.median(B), np.percentile(B, 10), np.percentile(B, 90), B.mean()))
hist = {}
for v in B:
    hist[int(v) // 10 * 10] = hist.get(int(v) // 10 * 10, 0) + 1
print("best-dx histogram (10px bins):")
for k in sorted(hist):
    print("   %+4d..: %s (%d)" % (k, "#" * int(40 * hist[k] / max(hist.values())), hist[k]))
print("gap-hits at dx=0: %d   at best: %d" % (sum(HITS0), sum(HITSB)))
con.close()
