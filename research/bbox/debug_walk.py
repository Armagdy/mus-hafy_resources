# -*- coding: utf-8 -*-
"""Debug the walk on p4/p300: column ink over BAND rows vs full-window rows."""
import importlib.util
import os
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
spec = importlib.util.spec_from_file_location(
    "genmw", os.path.join(ROOT, "scripts", "generate_ayah_bboxes_mwdoa.py"))
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)

PAGES_DIR = os.path.join(ROOT, "public", "assets", "mushuf_mwdoa_images")


def probe(p):
    im = Image.open(os.path.join(PAGES_DIR, "page_%04d.webp" % p)).convert("RGB")
    gray = np.array(im.convert("L"))
    H, W = gray.shape
    ink = gray < 160
    bands, lh, (tx0, tx1), (fx0, fx1, vclusters) = gen.uniform_bands_lh(gray)
    lo, hi = min(b[0] for b in bands), max(b[1] for b in bands)
    print("p%d  bands=%d lo=%d hi=%d (H=%d)  vclusters=%s" %
          (p, len(bands), lo, hi, H, [(round(a / W, 3), round(b_ / W, 3))
                                     for a, b_ in vclusters[:4]]))
    print("   x:  band-rows-ink   window-rows-ink")
    r0, r1 = int(H * 0.08), int(H * 0.96)
    for x in range(int(0.16 * W), int(0.24 * W), 4):
        bink = ink[lo:hi, x:x + 4].mean()
        wink = ink[r0:r1, x:x + 4].mean()
        print("   %.3f   %.3f            %.3f" % (x / W, bink, wink))


probe(4)
probe(300)
