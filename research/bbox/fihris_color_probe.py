# -*- coding: utf-8 -*-
"""Compare segment x-extents (from the emitted JSON) with the page image's
colored regions — find what sits at the edges inside the frame (the fihrist).

For each sampled page: print the JSON segment x-range union, then scan the
image columns INSIDE the frame for saturated COLOR (non-black, non-gold)
to see if a colored index strip sits near an edge.
"""
import json
import os
import numpy as np
from PIL import Image

PAGES_DIR = os.path.join("public", "assets", "mushuf_mwdoa_images")
JSON_PATH = os.path.join("public", "assets", "ayah-bboxes", "mwdoa.json")

data = json.load(open(JSON_PATH, encoding="utf-8"))
pages = data["pages"]

PAGES = [2, 3, 4, 50, 51, 106, 107, 200, 201, 300, 301, 400, 401, 500, 501]

SLABS = 20


def color_slab(page_no):
    im = Image.open(os.path.join(PAGES_DIR, "page_%04d.webp" % page_no)).convert("RGB")
    a = np.array(im)
    H, W = a.shape[:2]
    r, g, b = a[:, :, 0].astype(int), a[:, :, 1].astype(int), a[:, :, 2].astype(int)
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    sat = (mx - mn) > 40
    r0, r1 = int(H * 0.12), int(H * 0.94)
    prof = sat[r0:r1].sum(axis=0) / float(r1 - r0)
    return W, H, [float(prof[int(W * i / SLABS):int(W * (i + 1) / SLABS)].mean())
                  for i in range(SLABS)]


print("page   segXmin..segXmax   color density per 5%-slab (LEFT ... RIGHT)")
for p in PAGES:
    ent = pages.get(str(p))
    if not ent:
        print("%4d   (no data)" % p)
        continue
    xs = [s[0] for e in ent for s in e["seg"]]
    xe = [s[0] + s[2] for e in ent for s in e["seg"]]
    W, H, slab = color_slab(p)
    bar = "".join("%X" % min(15, int(v * 25)) for v in slab)
    print("%4d   %.3f..%.3f      %s" % (p, min(xs), max(xe), bar))
