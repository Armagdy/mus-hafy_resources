# -*- coding: utf-8 -*-
"""Fine probe of the marginal colored strip (fihrist) on mwdoa pages.

For each sampled page: 40 x-slabs (2.5% each) of saturated-color density,
plus the vertical extent of the detected strip and the colors it uses.
Also prints the dark-ink extent between the frame borders (what the
generator currently uses as tx0/tx1) for comparison.
"""
import os
import numpy as np
from PIL import Image

PAGES_DIR = os.path.join("public", "assets", "mushuf_mwdoa_images")

PAGES = [3, 4, 51, 106, 107, 201, 300, 301, 400, 401, 500, 501]
SLABS = 40


def analyze(page_no):
    im = Image.open(os.path.join(PAGES_DIR, "page_%04d.webp" % page_no)).convert("RGB")
    a = np.array(im)
    H, W = a.shape[:2]
    r, g, b = a[:, :, 0].astype(int), a[:, :, 1].astype(int), a[:, :, 2].astype(int)
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    sat = (mx - mn) > 40
    gray = np.array(im.convert("L"))
    ink = gray < 160

    # vertical extent: rows where the colored strip region is dense
    r0, r1 = int(H * 0.08), int(H * 0.96)
    left = sat[:, : int(W * 0.13)]
    right = sat[:, W - int(W * 0.13):]
    # pick side by which half has more saturated color inside the bands
    mid = int(W * 0.5)
    side = "L" if sat[:, :mid].sum() > sat[:, mid:].sum() else "R"

    # slab profile over band rows
    prof = sat[r0:r1].sum(axis=0) / float(r1 - r0)
    inkprof = ink[r0:r1].sum(axis=0) / float(r1 - r0)
    slab = [prof[int(W * i / SLABS):int(W * (i + 1) / SLABS)].mean() for i in range(SLABS)]
    inkslab = [inkprof[int(W * i / SLABS):int(W * (i + 1) / SLABS)].mean()
               for i in range(SLABS)]
    bar = "".join("%X" % min(15, int(v * 30)) for v in slab)
    ibar = "".join("%X" % min(15, int(v * 30)) for v in inkslab)

    # vertical run of the strip on its side
    if side == "L":
        striprows = sat[:, : int(W * 0.13)].sum(axis=1)
    else:
        striprows = sat[:, W - int(W * 0.13):].sum(axis=1)
    dense = striprows > (int(W * 0.13) * 0.12)
    ys = np.where(dense)[0]
    vext = (float(ys.min()) / H, float(ys.max()) / H) if len(ys) else None

    # dominant strip colors
    if side == "L":
        reg = a[r0:r1, int(W * 0.03): int(W * 0.13)]
    else:
        reg = a[r0:r1, W - int(W * 0.13): W - int(W * 0.03)]
    flat = reg.reshape(-1, 3)
    mxf = flat.max(axis=1).astype(int)
    mnf = flat.min(axis=1).astype(int)
    colored = flat[(mxf - mnf) > 40]
    # quantize to 32-steps to list dominant hues
    if len(colored):
        q = (colored // 32 * 32)
        vals, counts = np.unique(q, axis=0, return_counts=True)
        order = np.argsort(-counts)[:5]
        dom = ["#%02x%02x%02x x%d" % (v[0], v[1], v[2], c)
               for v, c in zip(vals[order], counts[order])]
    else:
        dom = []

    print("p%-4d side=%s  vext=%s" % (page_no, side, vext))
    print("   color: %s" % bar)
    print("   ink  : %s" % ibar)
    print("   dom  : %s" % ", ".join(dom))


for p in PAGES:
    analyze(p)
