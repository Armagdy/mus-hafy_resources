# -*- coding: utf-8 -*-
"""Column-level detail for the DISAGREE pages: print dense vertical ink
LINES (>0.45 density), color density, and ink density per column bucket in
the outer zone, so the true text-column boundary is visible."""
import os
import numpy as np
from PIL import Image

PAGES_DIR = os.path.join("public", "assets", "mushuf_mwdoa_images")
PAGES = [260, 272, 279, 284, 443, 589, 519, 111]


def probe(p):
    im = Image.open(os.path.join(PAGES_DIR, "page_%04d.webp" % p)).convert("RGB")
    a = np.array(im)
    H, W = a.shape[:2]
    gray = np.array(im.convert("L"))
    ink = gray < 160
    r, g, b = a[:, :, 0].astype(int), a[:, :, 1].astype(int), a[:, :, 2].astype(int)
    sat = (np.maximum(np.maximum(r, g), b) -
           np.minimum(np.minimum(r, g), b)) > 40
    r0, r1 = int(H * 0.08), int(H * 0.96)
    rh = float(r1 - r0)
    cold = ink[r0:r1].sum(axis=0) / rh
    satd = sat[r0:r1].sum(axis=0) / rh

    even = p % 2 == 0
    if even:
        lo, hi = 0, int(0.30 * W)
    else:
        lo, hi = int(0.70 * W), W

    # dense vertical lines in the zone
    lines = []
    in_l, st = False, 0
    for i in range(lo, hi):
        if cold[i] > 0.45:
            if not in_l:
                st, in_l = i, True
        elif in_l:
            if i - st >= 1:
                lines.append((st, i, cold[st:i].max()))
            in_l = False
    if in_l:
        lines.append((st, hi, cold[st:hi].max()))
    print("p%-4d %s  vertical lines in outer zone:" % (p, "EVEN(L)" if even else "ODD(R)"))
    for (s_, e_, pk) in lines:
        print("      x %.3f..%.3f  peak=%.2f" % (s_ / W, e_ / W, pk))

    # per-2% bucket ink/color density across the zone
    n = 15
    step = (hi - lo) / n
    row = []
    for i in range(n):
        s0, s1 = int(lo + i * step), int(lo + (i + 1) * step)
        row.append("%.2f/%.2f" % (cold[s0:s1].mean(), satd[s0:s1].mean()))
    print("      ink/color per %.1f%%-bucket: %s" % (100.0 / n, "  ".join(row)))


for p in PAGES:
    probe(p)
