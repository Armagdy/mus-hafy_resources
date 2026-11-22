# -*- coding: utf-8 -*-
"""Score the FINAL emitted madinah asset: every internal ayah boundary on
every line should land on a real white gap in the print."""
import json
import os
import sys

import numpy as np
from PIL import Image

ROOT = r"D:\apps\quran\mushafy"
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from generate_ayah_bboxes import page_geometry, band_text_block

PAGES_DIR = os.path.join(ROOT, "public", "assets", "mushaf_madinah_images")
asset = json.load(open(os.path.join(ROOT, "public", "assets",
                                    "ayah-bboxes", "madinah.json"),
                       encoding="utf-8"))

sample = sorted(int(k) for k in asset["pages"])[::9]
hits = tot = 0
oob = 0
for pg in sample:
    gray = np.array(Image.open(os.path.join(
        PAGES_DIR, "page_%04d.webp" % pg)).convert("L"))
    H, W = gray.shape
    ink = gray < 205
    (c0, c1), bands, _, strip = page_geometry(gray, 205)
    entries = asset["pages"][str(pg)]
    # segment y ranges map to bands: group segments by their band
    by_line = {}
    for e in entries:
        for (x, y, w, h) in e["seg"]:
            yc = (y + h / 2.0) * H
            # find band containing yc
            for k, (a, b) in enumerate(bands):
                if a - 5 <= yc <= b + 5:
                    by_line.setdefault(k + 1, []).append(
                        (e["s"], e["a"], x * W, (x + w) * W))
                    break
            else:
                oob += 1
    for ln, segs in by_line.items():
        if len(segs) < 2 or not (0 < ln <= len(bands)):
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
        xs = sorted((r[2], r[3]) for r in segs)
        for (x0a, x1a), (x0b, x1b) in zip(xs, xs[1:]):
            wx = (x1a + x0b) / 2.0
            tot += 1
            hits += any(g[0] - 5 <= wx <= g[1] + 5 for g in gaps)

print("pages sampled: %d   segments not on any band: %d" % (len(sample), oob))
print("FINAL asset boundaries on real gaps: %d/%d (%.1f%%)"
      % (hits, tot, 100.0 * hits / max(1, tot)))
print("  (classic-based asset was ~13%, 1421 source data ~63%)")
