# -*- coding: utf-8 -*-
"""Within-line word-boundary test with the FINAL transform + chance baseline.

For each paired line:
  - predict word boundaries from the DB word boxes (mapped with the final
    page transform)
  - measure real white gaps (>=3px) in the band
  - hit = boundary lands within +-5px of a real gap

Baselines for comparison:
  - chance: same number of boundaries at random positions in the line
  - shifted: DB boundaries shifted by +25px (simulating a wrong print)
If the DB matches this print, DB hits >> chance. If DB ~ chance, the
print's within-line layout differs from the DB.
"""
import json
import os
import random
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

rng = random.Random(7)
DB_HITS = DB_TOT = CH_HITS = CH_TOT = SH_HITS = SH_TOT = 0
SEG_HITS = SEG_TOT = 0

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
    segs = {}
    for (ln, s, a, x0, y0, x1, y1) in groups:
        words.setdefault(ln, []).append((x0, x1))
        segs.setdefault((ln, s, a), (x0, x1))

    for ln in sorted(words):
        if not (0 < ln <= len(bands)) or len(words[ln]) < 2:
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
        if st is not None and len(inside) - st >= 3:
            gaps.append((il + st, ir))
        if not gaps:
            continue

        def hit(wx):
            return any(g[0] - 5 <= wx <= g[1] + 5 for g in gaps)

        # DB word boundaries
        xs = sorted(words[ln])
        for (x0a, x1a), (x0b, x1b) in zip(xs, xs[1:]):
            wx = ((x1a + x0b) / 2.0) * sx + tx
            DB_TOT += 1
            DB_HITS += hit(wx)
            # shifted baseline (+25px)
            SH_TOT += 1
            SH_HITS += hit(wx + 25)
        # chance baseline: same count, random positions
        for _ in xs[:-1]:
            CH_TOT += 1
            CH_HITS += hit(rng.uniform(il + 10, ir - 10))

    # ayah-segment boundaries only (the splits that matter for highlighting)
    per_line = {}
    for (ln, s, a), (x0, x1) in segs.items():
        per_line.setdefault(ln, []).append((x0, x1, s, a))
    for ln, lst in per_line.items():
        if not (0 < ln <= len(bands)) or len(lst) < 2:
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
        if st is not None and len(inside) - st >= 3:
            gaps.append((il + st, ir))
        lst2 = sorted(lst)
        for (x0a, x1a, _, _), (x0b, x1b, _, _) in zip(lst2, lst2[1:]):
            wx = ((x1a + x0b) / 2.0) * sx + tx
            SEG_TOT += 1
            SEG_HITS += any(g[0] - 5 <= wx <= g[1] + 5 for g in gaps)

print("pages sampled: %d" % len(sample))
print("DB word boundaries on real gaps:   %d/%d  (%.1f%%)"
      % (DB_HITS, DB_TOT, 100.0 * DB_HITS / DB_TOT))
print("chance baseline:                   %d/%d  (%.1f%%)"
      % (CH_HITS, CH_TOT, 100.0 * CH_HITS / CH_TOT))
print("shifted(+25px) baseline:           %d/%d  (%.1f%%)"
      % (SH_HITS, SH_TOT, 100.0 * SH_HITS / SH_TOT))
print("DB ayah-segment boundaries:        %d/%d  (%.1f%%)"
      % (SEG_HITS, SEG_TOT, 100.0 * SEG_HITS / SEG_TOT))
con.close()
