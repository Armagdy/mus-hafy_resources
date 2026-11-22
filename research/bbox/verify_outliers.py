# -*- coding: utf-8 -*-
"""Verify outlier clip pages: text ink must start/end exactly at the clip."""
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
CASES = [(36, "L", 0.251), (326, "L", 0.236), (236, "L", 0.225),
         (69, "R", 0.759), (241, "R", 0.781)]


def probe(p, side, expect):
    im = Image.open(os.path.join(PAGES_DIR, "page_%04d.webp" % p)).convert("RGB")
    gray = np.array(im.convert("L"))
    H, W = gray.shape
    ink = gray < 160
    bands, lh, (tx0, tx1), (fx0, fx1, vclusters) = gen.uniform_bands_lh(gray)
    lo, hi = min(b[0] for b in bands), max(b[1] for b in bands)
    print("p%d (%s) expect %.3f" % (p, side, expect))
    if side == "L":
        xs = np.arange(int(0.17 * W), int(0.30 * W), 4)
    else:
        xs = np.arange(int(0.70 * W), int(0.83 * W), 4)
    line = []
    for x in xs:
        bink = ink[lo:hi, x:x + 4].mean()
        line.append("%s%.3f" % ("*" if abs(x / W - expect) < 0.004 else " ", bink))
    print("   x   : " + " ".join("%.3f" % (x / W) for x in xs))
    print("   ink : " + " ".join(line))
    print("   (* marks the clip position)")


for p, s, e in CASES:
    probe(p, s, e)
