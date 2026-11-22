# -*- coding: utf-8 -*-
"""Structure probe: for the 9 both-sides pages, compare the row-banding
inside the INNER wide pale strip vs the central text area.

- If the inner strip's ink rows align with the page's text bands and have
  text-like heights -> it is TEXT on a colored background (do not clip).
- If it has its own small/dense row structure -> margin panel like the
  fihrist (clip).
Also print the fihrist strip's row structure for comparison.
"""
import os
import numpy as np
from PIL import Image

PAGES_DIR = os.path.join("public", "assets", "mushuf_mwdoa_images")

CASES = [
    (38, (0.640, 0.960), (0.039, 0.174)),   # even: inner=R wide, fihrist=L
    (41, (0.037, 0.357), (0.829, 0.963)),   # odd:  inner=L wide, fihrist=R
    (178, (0.641, 0.961), (0.037, 0.173)),
    (301, (0.041, 0.361), (0.827, 0.960)),
]


def row_bands(gray, x0, x1, th=160):
    ink = gray[:, x0:x1] < th
    prof = ink.sum(axis=1) / float(x1 - x0)
    bands, in_b, st = [], False, 0
    for i, v in enumerate(prof):
        if v > 0.05 and not in_b:
            st, in_b = i, True
        elif v <= 0.05 and in_b:
            if i - st > 8:
                bands.append((st, i))
            in_b = False
    if in_b and len(prof) - st > 8:
        bands.append((st, len(prof)))
    return bands


def report(page_no, inner, fihris, text):
    im = Image.open(os.path.join(PAGES_DIR, "page_%04d.webp" % page_no)).convert("L")
    gray = np.array(im)
    H, W = gray.shape
    r0, r1 = int(H * 0.06), int(H * 0.97)
    g = gray[r0:r1]
    cols = lambda span: (int(span[0] * W), int(span[1] * W))

    print("=== p%d (parity %s) ===" % (page_no, "even" if page_no % 2 == 0 else "odd"))
    for label, span in (("inner-wide", inner), ("fihrist", fihris), ("text", text)):
        x0, x1 = cols(span)
        bands = row_bands(g, x0, x1)
        hs = [b[1] - b[0] for b in bands]
        ys = [round(b[0] / (r1 - r0), 3) for b in bands[:6]]
        print("  %-9s x %.2f..%.2f  rows=%2d medH=%3s first-ys=%s" %
              (label, span[0], span[1], len(bands),
               int(np.median(hs)) if hs else "-", ys))


for p, inner, fihris in CASES:
    report(p, inner, fihris, (0.40, 0.60))
