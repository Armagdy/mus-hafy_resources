# -*- coding: utf-8 -*-
"""Examine the actual writing of the local madinah images vs the online DBs.

Steps:
  1. robust frame-column mask (longest vertical ink run per column)
  2. per-band clean ink extents + internal white gaps
  3. compare against classic 1405H DB (word boxes) and 1421H DB
     (ayah-line boxes): which print's line structure / gap pattern
     matches the image?
"""
import os
import sqlite3
import sys

import numpy as np
from PIL import Image

ROOT = r"D:\apps\quran\mushafy"
PAGES_DIR = os.path.join(ROOT, "public", "assets", "mushaf_madinah_images")
CLASSIC = os.path.join(ROOT, "temp", "bbox-research", "ayahinfo_classic_1260.db")
V1421 = os.path.join(ROOT, "temp", "bbox-research", "ayahinfo_1421_1260.db")


def max_vertical_runs(ink):
    """Longest run of consecutive inked rows, per column."""
    H, W = ink.shape
    runs = np.zeros(W, np.int32)
    cur = np.zeros(W, np.int32)
    prev = np.zeros(W, bool)
    for i in range(H):
        row = ink[i]
        cur = np.where(row & prev, cur + 1, row.astype(np.int32))
        runs = np.maximum(runs, cur)
        prev = row
    return runs


def frame_mask(ink, run_thresh):
    """Columns that are part of vertical frame lines / border ornaments."""
    runs = max_vertical_runs(ink)
    return runs > run_thresh, runs


def band_profile(gray_band, thresh=205, cutoff=0.12):
    """(left, right, gaps) for one text band's columns."""
    ink = gray_band < thresh
    colsum = ink.sum(axis=0)
    nz = np.where(colsum > cutoff * ink.shape[0])[0]
    if not len(nz):
        return None
    left, right = int(nz.min()), int(nz.max())
    # gaps: columns (left..right) with no ink
    empty = colsum[left:right + 1] == 0
    gaps, st = [], None
    for i, v in enumerate(empty):
        if v and st is None:
            st = i
        elif not v and st is not None:
            gaps.append((left + st, left + i - 1))
            st = None
    if st is not None:
        gaps.append((left + st, right))
    return left, right, gaps


def detect_bands(gray, thresh=205):
    ink = gray < thresh
    rowd = ink.mean(axis=1)
    bands, in_b = [], False
    for i, v in enumerate(rowd):
        if v > 0.03 and not in_b:
            st, in_b = i, True
        elif v <= 0.03 and in_b:
            bands.append((st, i))
            in_b = False
    if in_b:
        bands.append((st, len(rowd)))
    return bands


page = int(sys.argv[1]) if len(sys.argv) > 1 else 564
gray = np.array(Image.open(os.path.join(
    PAGES_DIR, "page_%04d.webp" % page)).convert("L"))
H, W = gray.shape
ink = gray < 205

fmask, runs = frame_mask(ink, run_thresh=int(H * 0.05))
print("page %d  W=%d H=%d  frame-masked cols: %d" % (page, W, H, fmask.sum()))
fm_cols = np.where(fmask)[0]
if len(fm_cols):
    runs_g, st = [], fm_cols[0]
    for a, b in zip(fm_cols, fm_cols[1:]):
        if b - a > 4:
            runs_g.append((int(st), int(a)))
            st = b
    runs_g.append((int(st), int(fm_cols[-1])))
    print("frame col runs:", runs_g)

# text columns = non-frame; report longest remaining run (sanity: < line pitch)
clean_cols = np.where(~fmask)[0]
print("longest run among clean cols:", int(runs[clean_cols].max()))

bands = detect_bands(gray)
print("detected bands: %d" % len(bands))
for bi, (a, b) in enumerate(bands):
    prof = band_profile(gray[a:b])
    if prof:
        l, r, gaps = prof
        gstr = " ".join("%d-%d" % g for g in gaps if g[1] - g[0] >= 3)
        print("  band %2d rows %4d-%4d ink %4d..%4d  gaps: %s"
              % (bi + 1, a, b, l, r, gstr[:120]))

# ---------------- DB side ----------------
print("\n== classic 1405H per-line segments (page %d) ==" % page)
con = sqlite3.connect(CLASSIC)
cur = con.cursor()
cur.execute("""SELECT line_number, sura_number, ayah_number,
              MIN(min_x), MAX(max_x), COUNT(*) as words
              FROM glyphs WHERE page_number=?
              GROUP BY line_number, sura_number, ayah_number
              ORDER BY line_number, MIN(position)""", (page,))
for (ln, s, a, x0, x1, nw) in cur.fetchall():
    print("  line %2d  %d:%d  x=%4d..%4d  (%d words)" % (ln, s, a, x0, x1, nw))
con.close()

print("\n== madani 1421H per-line segments (page %d) ==" % page)
con = sqlite3.connect(V1421)
cur = con.cursor()
cur.execute("""SELECT line_number, sura_number, ayah_number,
              MIN(min_x), MAX(max_x)
              FROM glyphs WHERE page_number=?
              GROUP BY line_number, sura_number, ayah_number
              ORDER BY line_number, MIN(position)""", (page,))
for (ln, s, a, x0, x1) in cur.fetchall():
    print("  line %2d  %d:%d  x=%4d..%4d" % (ln, s, a, x0, x1))
con.close()
