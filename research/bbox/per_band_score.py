# -*- coding: utf-8 -*-
"""Per-band boundary scoring for BOTH DBs on specific pages/bands.

For each band: collect each DB's internal ayah boundaries for that line,
map per-line, and score gap hits. If the 1421's larger boundary sets hit
real gaps while the classic's miss, our print's per-band CONTENT follows
the 1421.
"""
import json
import os
import sqlite3
import sys

import numpy as np
from PIL import Image

ROOT = r"D:\apps\quran\mushafy"
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from generate_ayah_bboxes import page_geometry, ensure_db, band_text_block  # noqa

PAGES_DIR = os.path.join(ROOT, "public", "assets", "mushaf_madinah_images")
cc = sqlite3.connect(ensure_db(os.path.join(ROOT, "temp", "bbox-research")))
c2 = sqlite3.connect(os.path.join(ROOT, "temp", "bbox-research",
                                   "ayahinfo_1421_1260.db"))


def segs(con, pg, ln):
    cur = con.cursor()
    cur.execute("""SELECT sura_number, ayah_number, MIN(min_x), MAX(max_x)
                   FROM glyphs WHERE page_number=? AND line_number=?
                   GROUP BY sura_number, ayah_number""", (pg, ln))
    return cur.fetchall()


def gaps_in(ink, a, b, il, ir):
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
    return gaps


def score(con, pg, ln, ink, bands, strip):
    rows = segs(con, pg, ln)
    if len(rows) < 2 or not (0 < ln <= len(bands)):
        return None
    a, b = bands[ln - 1]
    tb = band_text_block(ink, a, b, exclude=strip)
    if not tb:
        return None
    il, ir = tb
    dbx0 = min(r[2] for r in rows)
    dbx1 = max(r[3] for r in rows)
    if dbx1 <= dbx0:
        return None
    s_ = (ir - il) / float(dbx1 - dbx0)
    t_ = il - dbx0 * s_
    gaps = gaps_in(ink, a, b, il, ir)
    if not gaps:
        return None
    xs = sorted((r[2], r[3]) for r in rows)
    hits = 0
    for (x0a, x1a), (x0b, x1b) in zip(xs, xs[1:]):
        wx = ((x1a + x0b) / 2.0) * s_ + t_
        hits += any(g[0] - 5 <= wx <= g[1] + 5 for g in gaps)
    return hits, len(xs) - 1, [r[0:2] for r in rows]


for pg, lns in ((564, [8, 9, 10, 12, 13, 14, 15]), (3, [1, 2, 3]),
                (300, [5, 8, 12])):
    gray = np.array(Image.open(os.path.join(
        PAGES_DIR, "page_%04d.webp" % pg)).convert("L"))
    ink = gray < 205
    (c0, c1), bands, _, strip = page_geometry(gray, 205)
    print("=== p%d ===" % pg)
    for ln in lns:
        rc = score(cc, pg, ln, ink, bands, strip)
        r2 = score(c2, pg, ln, ink, bands, strip)
        if not rc or not r2:
            continue
        print(" band %2d: classic %d/%d hits  1421 %d/%d hits   content c=%s"
              "  1421=%s" % (ln, rc[0], rc[1], r2[0], r2[1],
                             [(s, a) for (s, a) in rc[2]],
                             [(s, a) for (s, a) in r2[2]]))
cc.close()
c2.close()
