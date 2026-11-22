# -*- coding: utf-8 -*-
"""Coarse ASCII render of a page's margin zone to SEE its structure.

Legend: '#'=dark ink, 'o'=saturated chip color, '~'=cream tint (fihrist
background), '.'=white paper, ' '=<threshold noise>.
"""
import os
import sys
import numpy as np
from PIL import Image

PAGES_DIR = os.path.join("public", "assets", "mushuf_mwdoa_images")


def render(page_no, x0f, x1f, cols=70, rows=90):
    im = Image.open(os.path.join(PAGES_DIR, "page_%04d.webp" % page_no)).convert("RGB")
    a = np.array(im)
    H, W = a.shape[:2]
    x0, x1 = int(x0f * W), int(x1f * W)
    reg = a[:, x0:x1]
    r, g, b = (reg[:, :, 0].astype(int), reg[:, :, 1].astype(int),
               reg[:, :, 2].astype(int))
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    sat = mx - mn
    light = mx
    ink = (light < 160)
    chip = (sat > 40) & ~ink
    cream = (sat >= 10) & (sat <= 40) & (light > 150)
    sy = H // rows
    sx = (x1 - x0) // cols
    out = []
    for j in range(rows):
        line = []
        for i in range(cols):
            block = slice(j * sy, (j + 1) * sy), slice(i * sx, (i + 1) * sx)
            if ink[block].mean() > 0.18:
                line.append("#")
            elif chip[block].mean() > 0.3:
                line.append("o")
            elif cream[block].mean() > 0.3:
                line.append("~")
            elif light[block].mean() > 200:
                line.append(".")
            else:
                line.append(" ")
        out.append("".join(line))
    return out


def show(page_no, x0f, x1f, **kw):
    print("=== p%d  x %.2f..%.2f (left->right) ===" % (page_no, x0f, x1f))
    for line in render(page_no, x0f, x1f, **kw):
        print(line)
    print()


sys.stdout.reconfigure(encoding="utf-8")
# p111 odd: weird dense band at 0.767-0.783 then ribbon 0.80-0.817 then entries
show(111, 0.70, 1.00, cols=60, rows=70)
# p260 even: two rules + dense col at 0.20-0.22
show(260, 0.0, 0.30, cols=60, rows=70)
