# -*- coding: utf-8 -*-
"""Does the 1421H DB's within-line layout match this print better than
the classic 1405H?

Per page: match 1421 lines to image bands by y-center proximity, map each
1421 line's ayah boundaries onto the band's text block (per-line affine),
and count boundaries landing on real white gaps. Compare with the classic
DB's 12.4% (chance 8.2%).
"""
import json
import os
import sqlite3
import sys

import numpy as np
from PIL import Image

ROOT = r"D:\apps\quran\mushafy"
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from generate_ayah_bboxes import page_geometry, ensure_db  # noqa: E402

PAGES_DIR = os.path.join(ROOT, "public", "assets", "mushaf_madinah_images")
V1421 = os.path.join(ROOT, "temp", "bbox-research", "ayahinfo_1421_1260.db")
con = sqlite3.connect(V1421)
res = json.load(open(os.path.join(ROOT, "temp", "bbox-research",
                                  "madinah_ayah_bboxes.json"), encoding="utf-8"))
by_page = {p["page"]: p for p in res["pages"]}


def page_1421(pg):
    cur = con.cursor()
    cur.execute("""SELECT line_number, sura_number, ayah_number,
                   MIN(min_x), MAX(max_x), MIN(min_y), MAX(max_y)
                   FROM glyphs WHERE page_number=?
                   GROUP BY line_number, sura_number, ayah_number
                   ORDER BY line_number, MIN(position)""", (pg,))
    rows = cur.fetchall()
    lines = {}
    for (ln, s, a, x0, x1, y0, y1) in rows:
        lines.setdefault(ln, {"rows": [], "y": [1e9, -1e9]})
        lines[ln]["rows"].append((s, a, x0, x1))
        lines[ln]["y"][0] = min(lines[ln]["y"][0], y0)
        lines[ln]["y"][1] = max(lines[ln]["y"][1], y1)
    return lines


hits = tot = 0
lines_used = 0
sample = [pg for pg in range(3, 605) if pg in by_page][::9]
for pg in sample:
    gray = np.array(Image.open(os.path.join(
        PAGES_DIR, "page_%04d.webp" % pg)).convert("L"))
    ink = gray < 205
    (c0, c1), bands, _, strip = page_geometry(gray, 205)
    lines = page_1421(pg)
    band_centers = np.array([(a + b) / 2.0 for (a, b) in bands])
    # global y-affine from 1421 line centers to band centers (least squares
    # over nearest matches, one iteration of refinement)
    lns = sorted(lines)
    lcy = np.array([(lines[ln]["y"][0] + lines[ln]["y"][1]) / 2.0 for ln in lns])
    # initial: map by order (both sorted top->bottom), pick min count pairs
    n = min(len(lns), len(bands))
    A = np.vstack([lcy[:n], np.ones(n)]).T
    sol, *_ = np.linalg.lstsq(A, band_centers[:n], rcond=None)
    sy_, ty_ = float(sol[0]), float(sol[1])
    for ln in lns:
        cy = (lines[ln]["y"][0] + lines[ln]["y"][1]) / 2.0
        by_ = cy * sy_ + ty_
        # nearest band
        k = int(np.argmin(np.abs(band_centers - by_)))
        if abs(band_centers[k] - by_) > 60:
            continue
        a, b = bands[k]
        tb = None
        from generate_ayah_bboxes import band_text_block
        tb = band_text_block(ink, a, b, exclude=strip)
        if not tb:
            continue
        il, ir = tb
        rows = lines[ln]["rows"]
        dbx0 = min(r[2] for r in rows)
        dbx1 = max(r[3] for r in rows)
        if dbx1 <= dbx0 or len(rows) < 2 or ir <= il:
            continue
        s_ = (ir - il) / float(dbx1 - dbx0)
        t_ = il - dbx0 * s_
        # gaps in the band
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
        if st is not None and len(inside) - st >= 3:
            gaps.append((il + st, ir))
        if not gaps:
            continue
        lines_used += 1
        xs = sorted((r[2], r[3]) for r in rows)
        for (x0a, x1a), (x0b, x1b) in zip(xs, xs[1:]):
            wx = ((x1a + x0b) / 2.0) * s_ + t_
            tot += 1
            hits += any(g[0] - 5 <= wx <= g[1] + 5 for g in gaps)

print("pages: %d  lines used: %d  boundaries: %d"
      % (len(sample), lines_used, tot))
print("1421H ayah boundaries on real gaps: %d/%d (%.1f%%)"
      % (hits, tot, 100.0 * hits / tot if tot else 0))
print("  (classic 1405H scored 12.4%%, chance 8.2%%)")
con.close()
