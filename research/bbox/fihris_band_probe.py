# -*- coding: utf-8 -*-
"""Pixel composition of the thick rule bands: p260 x 0.19-0.24 (even/L),
p111 x 0.79-0.85 (odd/R). Column densities for: dark ink, gold hue,
any saturation, cream tint. Identifies what 'extends across' means."""
import os
import numpy as np
from PIL import Image

PAGES_DIR = os.path.join("public", "assets", "mushuf_mwdoa_images")


def gold_frac(a):
    r = a[:, :, 0].astype(int)
    g = a[:, :, 1].astype(int)
    b = a[:, :, 2].astype(int)
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    sat = mx - mn
    hue = np.where(mx == r, ((g - b) / np.maximum(mx - mn, 1) * 60 + 360) % 360,
                  np.where(mx == g, 60 * (2 + (b - r) / np.maximum(mx - mn, 1)),
                           60 * (4 + (r - g) / np.maximum(mx - mn, 1))))
    return ((hue >= 22) & (hue < 52) & (sat > 38) & (mx < 248))


def probe(p, x0f, x1f):
    im = Image.open(os.path.join(PAGES_DIR, "page_%04d.webp" % p)).convert("RGB")
    a = np.array(im)
    H, W = a.shape[:2]
    gray = np.array(im.convert("L"))
    ink = gray < 160
    gold = gold_frac(a)
    r, g, b = a[:, :, 0].astype(int), a[:, :, 1].astype(int), a[:, :, 2].astype(int)
    sat = (np.maximum(np.maximum(r, g), b) - np.minimum(np.minimum(r, g), b))
    r0, r1 = int(H * 0.08), int(H * 0.96)
    rh = float(r1 - r0)
    x0, x1 = int(x0f * W), int(x1f * W)
    print("p%d x %.2f..%.2f (each col 0.2%%W): ink gold sat10+ light" % (p, x0f, x1f))
    step = max(1, W // 500)
    for cx in range(x0, x1, step):
        i = ink[r0:r1, cx:cx + step].mean()
        gl = gold[r0:r1, cx:cx + step].mean()
        st = (sat[r0:r1, cx:cx + step] > 10).mean()
        li = gray[r0:r1, cx:cx + step].mean()
        bar = "#" * int(i * 40)
        print("  %.3f  ink=%.2f gold=%.2f sat=%.2f L=%3d %s" %
              (cx / W, i, gl, st, li, bar))


probe(260, 0.170, 0.260)
probe(111, 0.770, 0.860)
