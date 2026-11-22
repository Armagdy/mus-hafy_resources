# -*- coding: utf-8 -*-
"""Inspect the 9 pages where a colored strip was detected on BOTH sides.

For each: strip details (width/peak/vcover) + DARK INK density inside each
strip (the real fihrist carries index text; a decorative band does not).
"""
import json
import os
import numpy as np
from PIL import Image

PAGES_DIR = os.path.join("public", "assets", "mushuf_mwdoa_images")
SCAN = json.load(open(os.path.join("temp", "bbox-research", "fihris_scan2.json"),
                      encoding="utf-8"))
BOTH = [38, 41, 178, 253, 301, 319, 388, 405, 519]


def probe(p):
    r = next(x for x in SCAN if x["page"] == p)
    W, H = r["W"], r["H"]
    im = Image.open(os.path.join(PAGES_DIR, "page_%04d.webp" % p)).convert("RGB")
    a = np.array(im)
    gray = np.array(im.convert("L"))
    ink = gray < 160
    r0, r1 = int(H * 0.08), int(H * 0.96)
    print("p%-4d even? %s" % (p, "yes" if p % 2 == 0 else "no"))
    for side, clip, fx in (("L", r["clip_l"], r["fx0"]), ("R", r["clip_r"], r["fx1"])):
        if clip is None:
            print("   %s: none" % side)
            continue
        x0, x1 = (fx, clip) if side == "L" else (clip, fx)
        reg = a[r0:r1, x0:x1]
        greg = gray[r0:r1, x0:x1]
        dark = float((greg < 160).mean())
        rr, gg, bb = (reg[:, :, 0].astype(int), reg[:, :, 1].astype(int),
                      reg[:, :, 2].astype(int))
        sat = (np.maximum(np.maximum(rr, gg), bb) - np.minimum(np.minimum(rr, gg), bb)) > 40
        q = (reg[sat] // 32 * 32)
        dom = []
        if len(q):
            vals, counts = np.unique(q.reshape(-1, 3), axis=0, return_counts=True)
            for v, c in zip(vals[np.argsort(-counts)[:3]], counts[np.argsort(-counts)[:3]]):
                dom.append("#%02x%02x%02x x%d" % (v[0], v[1], v[2], c))
        print("   %s: strip x %.3f..%.3f w=%.3fW dark=%.2f dom=%s" %
              (side, x0 / W, x1 / W, (x1 - x0) / W, dark, ", ".join(dom)))


for p in BOTH:
    probe(p)
