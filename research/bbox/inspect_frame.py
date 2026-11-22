# -*- coding: utf-8 -*-
"""Precisely locate the vertical frame elements and the real text x-range."""
import sys

import numpy as np
from PIL import Image

PAGES_DIR = r"public/assets/mushaf_madinah_images"
page = int(sys.argv[1]) if len(sys.argv) > 1 else 564

gray = np.array(Image.open(PAGES_DIR + "/page_%04d.webp" % page).convert("L"))
H, W = gray.shape
ink = gray < 205

# text-block rows only (bands found earlier: 104..1495 for p564) - recompute quickly
rowd = ink.mean(axis=1)
busy = rowd > 0.05
ys = np.where(busy)[0]
print("busy rows: %d..%d" % (ys.min(), ys.max()))
y0, y1 = ys.min(), ys.max()

print("\nper-column ink row-count within text rows y=%d..%d :" % (y0, y1))
seg = ink[y0:y1]
colrows = seg.sum(axis=0)
for x0 in range(0, 80, 4):
    print("  x %4d: %4d/%d" % (x0, colrows[x0], y1 - y0))
print("  ...")
for x0 in range(985, 1090, 4):
    print("  x %4d: %4d/%d" % (x0, colrows[x0], y1 - y0))

# columns that are inked for >60% of the text-block height = frame bars
vline = np.where(colrows > 0.6 * (y1 - y0))[0]
if len(vline):
    # group into runs
    runs, st = [], vline[0]
    for a, b in zip(vline, vline[1:]):
        if b - a > 3:
            runs.append((st, a)); st = b
    runs.append((st, vline[-1]))
    print("\nvertical frame runs (>60%% of text height): %s" % runs)

# text columns: ink rows > 8% of band, EXCLUDING frame runs
good = np.where(colrows > 0.08 * (y1 - y0))[0]
good = [x for x in good if not any(r[0] - 6 <= x <= r[1] + 6 for r in runs)] if len(vline) else good
print("text col extent (excl frame): %s" % ((good[0], good[-1]) if good else None))
