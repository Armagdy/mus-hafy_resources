# -*- coding: utf-8 -*-
"""Measure per-line horizontal offset between warped DB boxes and real ink.

For one page:
  - rebuild the ink mask exactly like generate_ayah_bboxes.page_geometry
  - per detected band, find the ink x-extent (columns with real text)
  - per DB line, take the union of warped group boxes -> x-extent
  - report (ink_x0 - box_x0) and (ink_x1 - box_x1): positive means the
    highlight sits LEFT of the text (needs a shift right).
"""
import json
import os
import sqlite3
import sys

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from generate_ayah_bboxes import page_geometry, db_page, ensure_db  # noqa: E402

PAGES_DIR = os.path.join(ROOT, "public", "assets", "mushaf_madinah_images")
DB = ensure_db()

page_no = int(sys.argv[1]) if len(sys.argv) > 1 else 564
thresh = int(sys.argv[2]) if len(sys.argv) > 2 else 205

img_path = os.path.join(PAGES_DIR, "page_%04d.webp" % page_no)
gray = np.array(Image.open(img_path).convert("L"))
H, W = gray.shape
ink = gray < thresh
interior, bands, their_x = page_geometry(gray, thresh=thresh)
print("page %d  W=%d H=%d  interior=(%d..%d)  their_x=%s  bands=%d"
      % (page_no, W, H, interior[0], interior[1], their_x, len(bands)))

con = sqlite3.connect(DB)
db_lines, groups, db_extent, first = db_page(con, page_no)
db_by_no = {ln: (lo, hi) for (ln, lo, hi) in db_lines}
max_line_no = max(db_by_no) if db_by_no else 0

# per-band ink extents (only real text lines, bands index-paired with db lines)
print("\nband -> ink extent (interior cols only):")
band_ink = []
for i, (a, b) in enumerate(bands):
    rows = ink[a:b, interior[0]:interior[1]]
    colsum = rows.sum(axis=0)
    nz = np.where(colsum > 0.10 * (b - a))[0]
    if len(nz):
        x0, x1 = interior[0] + nz.min(), interior[0] + nz.max()
    else:
        x0, x1 = None, None
    band_ink.append((x0, x1))
    print("  band %2d lines %4d-%4d  ink x: %s" % (i + 1, a, b, (x0, x1)))

# recompute the page transform like fit_page does (x part)
sx = (their_x[1] - their_x[0]) / float(db_extent[1] - db_extent[0])
tx = their_x[0] - db_extent[0] * sx
print("\ndb page extent: %s   -> sx=%.5f tx=%.1f" % (db_extent, sx, tx))

# per db line: union of warped group extents, compared with band ink extent
print("\nper-line comparison (db line -> band ink vs warped boxes):")
errs_l, errs_r = [], []
per_line = {}
for (ln, s, a, x0, y0, x1, y1) in groups:
    if ln not in per_line:
        per_line[ln] = [1e9, -1e9]
    per_line[ln][0] = min(per_line[ln][0], x0 * sx + tx)
    per_line[ln][1] = max(per_line[ln][1], x1 * sx + tx)
for ln in sorted(per_line):
    bx0, bx1 = per_line[ln]
    if 0 < ln <= len(bands):
        ix0, ix1 = band_ink[ln - 1]
    else:
        ix0 = ix1 = None
    if ix0 is not None:
        dl, dr = ix0 - bx0, ix1 - bx1
        errs_l.append(dl)
        errs_r.append(dr)
        print("  db line %2d  ink(%6.1f,%6.1f)  box(%6.1f,%6.1f)  "
              "left_err=%+6.1f right_err=%+6.1f  db_y=(%s)"
              % (ln, ix0, ix1, bx0, bx1, dl, dr, db_by_no.get(ln)))
    else:
        print("  db line %2d  box(%6.1f,%6.1f)  NO BAND" % (ln, bx0, bx1))

print("\nmedian left_err  = %+.1f px  (positive => boxes left of text)"
      % float(np.median(errs_l)))
print("median right_err = %+.1f px" % float(np.median(errs_r)))
print("mean   left_err  = %+.1f px" % float(np.mean(errs_l)))

# also: what extent would the fit use if only TEXT bands (glyph lines) count?
text_band_idx = [ln - 1 for ln in sorted(per_line) if 0 < ln <= len(bands)]
tx0 = min(band_ink[i][0] for i in text_band_idx if band_ink[i][0] is not None)
tx1 = max(band_ink[i][1] for i in text_band_idx if band_ink[i][1] is not None)
sx2 = (tx1 - tx0) / float(db_extent[1] - db_extent[0])
tx2 = tx0 - db_extent[0] * sx2
print("\nif their_x used ONLY glyph-text bands: extent=(%d,%d) "
      "-> sx=%.5f tx=%.1f (was %.5f / %.1f, dx at x=100: %+.1f px)"
      % (tx0, tx1, sx2, tx2, sx, tx, (sx2 - sx) * 100 + (tx2 - tx)))
