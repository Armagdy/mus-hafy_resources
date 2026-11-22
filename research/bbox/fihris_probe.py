# -*- coding: utf-8 -*-
"""Locate the marginal FIHRIS (index) strip on mwdoa pages.

For each sampled page: column ink profile over the band rows, split into
20 vertical slabs; print ink density per slab so the marginal sidebar
(if any) shows up as a dense slab near one edge.
"""
import os
import numpy as np
from PIL import Image

PAGES_DIR = os.path.join("public", "assets", "mushuf_mwdoa_images")

PAGES = [2, 3, 4, 50, 51, 106, 107, 200, 201, 300, 301, 400, 401, 500, 501]

SLABS = 20


def col_profile(page_no):
    im = Image.open(os.path.join(PAGES_DIR, "page_%04d.webp" % page_no)).convert("L")
    g = np.array(im)
    H, W = g.shape
    ink = g < 160
    # band rows only (exclude top/bottom 12% to skip header/footer ornaments)
    r0, r1 = int(H * 0.12), int(H * 0.94)
    prof = ink[r0:r1].sum(axis=0) / float(r1 - r0)
    slab = [float(prof[int(W * i / SLABS):int(W * (i + 1) / SLABS)].mean())
            for i in range(SLABS)]
    return W, H, slab


print("page   W    H    ink density per 5%-slab (LEFT ... RIGHT)")
for p in PAGES:
    W, H, slab = col_profile(p)
    bar = "".join("%X" % min(15, int(v * 25)) for v in slab)
    print("%4d  %4d %4d  %s" % (p, W, H, bar))
