# -*- coding: utf-8 -*-
"""Quick validation of fihrist_clip_x on representative pages."""
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

EXPECT = {
    2: (None, None),          # ornamental front-matter: no strip
    3: (None, 0.80),          # odd: fihris right, rule ~0.80-0.83
    4: (0.175, None),         # even: fihris left ~0.17-0.18
    111: (None, 0.788),       # odd w/ thick band: text ends ~0.789
    178: (0.174, None),
    260: (0.217, None),       # even w/ thick band + pale gap
    272: (0.20, None),        # bridged-chip page: rule wins
    279: (None, 0.799),
    300: (0.175, None),
    443: (None, 0.799),
    519: (None, 0.825),       # pale strip (no chips): rule fallback
    604: (0.174, None),
}


def run(page_no):
    im = Image.open(os.path.join(PAGES_DIR, "page_%04d.webp" % page_no)).convert("RGB")
    a = np.array(im)
    gray = np.array(im.convert("L"))
    H, W = gray.shape
    bands, lh, (tx0, tx1), (fx0, fx1, vclusters) = gen.uniform_bands_lh(gray)
    lo, hi = min(b[0] for b in bands), max(b[1] for b in bands)
    clip_l, clip_r = gen.fihrist_clip_x(a, gray, page_no, fx0, fx1, vclusters,
                                        lo, hi)
    return W, tx0 / W, tx1 / W, \
        (None if clip_l is None else clip_l / W), \
        (None if clip_r is None else clip_r / W)


print("page  W     tx0     tx1     clipL   clipR   expected")
for p, (el, er) in sorted(EXPECT.items()):
    W, tx0, tx1, cl, cr = run(p)
    okl = "?" if el is None else ("OK" if cl is not None and abs(cl - el) < 0.025 else "DIFF")
    okr = "?" if er is None else ("OK" if cr is not None and abs(cr - er) < 0.025 else "DIFF")
    print("%-5d %-5d %.3f  %.3f  %-7s %-7s L:%s R:%s" %
          (p, W, tx0, tx1,
           "-" if cl is None else "%.3f" % cl,
           "-" if cr is None else "%.3f" % cr, okl, okr))
