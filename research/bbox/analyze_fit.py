# -*- coding: utf-8 -*-
"""Per-line text-extent measurement, frame-masked, vs DB line extents.

For each detected band: true ink extent with a sane cutoff, excluding
vertical frame columns. Compare with the DB's per-line glyph extents and
with the page-level extent fit used by the generator.
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
DB = ensure_db()


def band_extents(ink, keep, bands, cutoff=0.15, pad=4):
    """True per-band text extents, masking vertical frame columns."""
    lo, hi = bands[0][0], bands[-1][1]
    colrows = ink[lo:hi][:, keep].sum(axis=0)
    span = hi - lo
    # vertical frame columns: inked in most of the text-block rows
    vcol = colrows > 0.55 * span
    # dilate vcol by pad and drop those columns
    drop = np.zeros(len(keep), bool)
    idx = np.where(vcol)[0]
    for i in idx:
        drop[max(0, i - pad):i + pad + 1] = True
    keep2 = keep[~drop]
    out = []
    for (a, b) in bands:
        colsum = ink[a:b][:, keep2].sum(axis=0)
        nz = np.where(colsum > cutoff * (b - a))[0]
        if len(nz):
            out.append((int(keep2[nz.min()]), int(keep2[nz.max()])))
        else:
            out.append((None, None))
    return out, (int(keep2[0]), int(keep2[-1]))


def theil_sen(pairs):
    slopes = []
    n = len(pairs)
    for i in range(n):
        for j in range(i + 1, n):
            dx = pairs[j][0] - pairs[i][0]
            if dx != 0:
                slopes.append((pairs[j][1] - pairs[i][1]) / dx)
    s = float(np.median(slopes))
    t = float(np.median([y - s * x for (x, y) in pairs]))
    return s, t


page_no = int(sys.argv[1]) if len(sys.argv) > 1 else 564
gray = np.array(Image.open(os.path.join(
    PAGES_DIR, "page_%04d.webp" % page_no)).convert("L"))
H, W = gray.shape
ink = gray < 205
interior, bands, their_x = page_geometry(gray, 205)
keep = np.arange(interior[0], interior[1] + 1)

ext, keep2 = band_extents(ink, keep, bands)
print("page %d  W=%d  interior=%s  naive their_x=%s  keep2=%s"
      % (page_no, W, interior, their_x, keep2))

con = sqlite3.connect(DB)
db_lines, groups, db_extent, first = db_page(con, page_no)
per_line_db = {}
for (ln, s, a, x0, y0, x1, y1) in groups:
    if ln not in per_line_db:
        per_line_db[ln] = [1e9, -1e9]
    per_line_db[ln][0] = min(per_line_db[ln][0], x0)
    per_line_db[ln][1] = max(per_line_db[ln][1], x1)

pairs = []
print("\nline  db extent        band ink extent")
for ln in sorted(per_line_db):
    dbx = per_line_db[ln]
    if 0 < ln <= len(bands) and ext[ln - 1][0] is not None:
        bx = ext[ln - 1]
        pairs.append(((dbx[0] + dbx[1]) / 2.0, (bx[0] + bx[1]) / 2.0,
                      dbx, bx))
        print(" %2d   (%6.1f,%6.1f)   (%s,%s)"
              % (ln, dbx[0], dbx[1], bx[0], bx[1]))

# robust fit on centers + spans
cen = [((d[0] + d[1]) / 2.0, (t[0] + t[1]) / 2.0) for (d, t) in
       [(p[2], p[3]) for p in pairs]]
sc, tc = theil_sen([(d[0], t[0]) for (d, t) in
                   [(p[2], p[3]) for p in pairs]])
print("\nTheil-Sen center fit: sx=%.5f tx=%.1f" % (sc, tc))

# page-extent fit with the CLEAN extents (min of lefts, max of rights)
tx0 = min(p[3][0] for p in pairs)
tx1 = max(p[3][1] for p in pairs)
sx = (tx1 - tx0) / float(db_extent[1] - db_extent[0])
tx = tx0 - db_extent[0] * sx
print("clean page-extent fit: extent=(%d,%d) sx=%.5f tx=%.1f"
      % (tx0, tx1, sx, tx))
print("old contaminated fit:  extent=(1,1088) sx=0.95017 tx=-58.9")

print("\nper-line residual with each fit (warped db extent vs band ink):")
for p in pairs:
    d, t = p[2], p[3]
    for name, s_, t_ in (("ts", sc, tc), ("clean", sx, tx),
                         ("old", 0.95017, -58.9)):
        wx0, wx1 = d[0] * s_ + t_, d[1] * s_ + t_
        err = (abs(wx0 - t[0]) + abs(wx1 - t[1])) / 2
        print("  db_line %s fit=%s  left_err=%+7.1f right_err=%+7.1f"
              % (p and "", name, t[0] - wx0, t[1] - wx1), end="")
        print()
    break
for p in pairs:
    d, t = p[2], p[3]
    row = "db line %s: " % ""
    for name, s_, t_ in (("ts", sc, tc), ("clean", sx, tx),
                        ("old", 0.95017, -58.9)):
        wx0, wx1 = d[0] * s_ + t_, d[1] * s_ + t_
        print("  %s: left=%+7.1f right=%+7.1f | "
              % (name, t[0] - wx0, t[1] - wx1), end="")
    print()
