# -*- coding: utf-8 -*-
"""Inspect ink column density for one madinah page image."""
import sys

import numpy as np
from PIL import Image

PAGES_DIR = r"public/assets/mushaf_madinah_images"
page = int(sys.argv[1]) if len(sys.argv) > 1 else 564

gray = np.array(Image.open(PAGES_DIR + "/page_%04d.webp" % page).convert("L"))
H, W = gray.shape
ink = gray < 205
print("page %d  W=%d H=%d  ink=%.3f" % (page, W, H, ink.mean()))

# column density in 20px buckets
prof = ink.mean(axis=0)
for x0 in range(0, W, 40):
    v = prof[x0:x0 + 40].mean()
    bar = "#" * int(v * 80)
    print("x %4d-%4d  %5.3f %s" % (x0, min(x0 + 40, W), v, bar))

# raw gray stats at the extremes
print("\ngray: min=%d max=%d mean=%.1f" % (gray.min(), gray.max(), gray.mean()))
cols = ink.sum(axis=0)
print("cols with ink>=1000 rows:", (cols >= 1000).sum(), "of", W)
first_dense = np.where(prof > 0.4)[0]
print("dense cols (>0.4):", first_dense.min() if len(first_dense) else None,
      first_dense.max() if len(first_dense) else None, "count", len(first_dense))
