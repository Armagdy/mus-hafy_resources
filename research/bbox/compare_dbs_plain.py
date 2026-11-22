# -*- coding: utf-8 -*-
"""Apples-to-apples: classic vs 1421 within-line boundary match, on
non-header pages only, with identical band pairing (line k -> band k).
"""
import json
import os
import sqlite3
import sys

import numpy as np
from PIL import Image

ROOT = r"D:\apps\quran\mushafy"
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from generate_ayah_bboxes import (page_geometry, db_page, ensure_db,
                                  band_text_block)  # noqa: E402

PAGES_DIR = os.path.join(ROOT, "public", "assets", "mushaf_madinah_images")
CLASSIC = ensure_db(os.path.join(ROOT, "temp", "bbox-research"))
V1421 = os.path.join(ROOT, "temp", "bbox-research", "ayahinfo_1421_1260.db")
cc = sqlite3.connect(CLASSIC)
c2 = sqlite3.connect(V1421)

res = json.load(open(os.path.join(ROOT, "temp", "bbox-research",
                                  "madinah_ayah_bboxes.json"), encoding="utf-8"))
by_page = {p["page"]: p for p in res["pages"]}


def line_gaps(con, pg):
    cur = con.cursor()
    cur.execute("SELECT DISTINCT line_number FROM glyphs WHERE page_number=? "
                "ORDER BY line_number", (pg,))
    lns = [r[0] for r in cur.fetchall()]
    return lns, (max(lns) - len(lns)) if lns else 0  # number of gap lines


def segs_by_line(con, pg):
    cur = con.cursor()
    cur.execute("""SELECT line_number, MIN(min_x), MAX(max_x)
                   FROM glyphs WHERE page_number=?
                   GROUP BY line_number, sura_number, ayah_number""",
                (pg,))
    lines = {}
    for (ln, x0, x1) in cur.fetchall():
        lines.setdefault(ln, []).append((x0, x1))
    return lines


def page_gap_hits(gray, ink, strip, bands, lines):
    hits = tot = 0
    for ln, segs in lines.items():
        if len(segs) < 2 or not (0 < ln <= len(bands)):
            continue
        a, b = bands[ln - 1]
        tb = band_text_block(ink, a, b, exclude=strip)
        if not tb:
            continue
        il, ir = tb
        dbx0 = min(x for x, _ in segs)
        dbx1 = max(x1 for _, x1 in segs)
        if dbx1 <= dbx0 or ir <= il:
            continue
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
        s_ = (ir - il) / float(dbx1 - dbx0)
        t_ = il - dbx0 * s_
        xs = sorted(segs)
        for (x0a, x1a), (x0b, x1b) in zip(xs, xs[1:]):
            wx = ((x1a + x0b) / 2.0) * s_ + t_
            tot += 1
            hits += any(g[0] - 5 <= wx <= g[1] + 5 for g in gaps)
    return hits, tot


sample = [pg for pg in range(3, 605) if pg in by_page][::9]
plain = []
for pg in sample:
    lns_c, gaps_c = line_gaps(cc, pg)
    lns_2, gaps_2 = line_gaps(c2, pg)
    # "plain": both DBs have all 15 lines with glyphs (no header/basmalah
    # gaps) and identical structure
    if gaps_c == 0 and gaps_2 == 0 and len(lns_c) == 15 and len(lns_2) == 15:
        plain.append(pg)

res_c = [0, 0]
res_2 = [0, 0]
for pg in plain:
    gray = np.array(Image.open(os.path.join(
        PAGES_DIR, "page_%04d.webp" % pg)).convert("L"))
    ink = gray < 205
    (c0, c1), bands, _, strip = page_geometry(gray, 205)
    h, t = page_gap_hits(gray, ink, strip, bands, segs_by_line(cc, pg))
    res_c[0] += h
    res_c[1] += t
    h, t = page_gap_hits(gray, ink, strip, bands, segs_by_line(c2, pg))
    res_2[0] += h
    res_2[1] += t

print("plain pages (both DBs 15/15 lines, no gaps): %d of %d sampled"
      % (len(plain), len(sample)))
print("classic 1405H boundaries on gaps: %d/%d (%.1f%%)"
      % (res_c[0], res_c[1], 100.0 * res_c[0] / max(1, res_c[1])))
print("1421H    boundaries on gaps: %d/%d (%.1f%%)"
      % (res_2[0], res_2[1], 100.0 * res_2[0] / max(1, res_2[1])))
cc.close()
c2.close()
