# -*- coding: utf-8 -*-
"""
Composite hypothesis: the mwdoa marker = golden number blob INSIDE a thin
black ornament ring. The strict red candidates missed rings (fill < 0.35).

Test: for each golden candidate on p300 (G1..G6, G2 confirmed by the user),
measure black-ink coverage in a ring around the golden blob, plus the
black-ink structure (hollow ring = ink surrounds empty center).
"""
import numpy as np
from PIL import Image

DIR = r"D:\apps\quran\mushafy\public\assets\mushuf_mwdoa_images"
PAGE = 300

im = Image.open(DIR + "\\page_%04d.webp" % PAGE).convert("RGB")
a = np.array(im).astype(np.int32)
gray = np.array(im.convert("L"))
H, W = gray.shape

G = {
    "G1 (y=590)": (314, 590, 26, 16),
    "G2 (y=824) CONFIRMED": (147, 824, 18, 26),
    "G3 (y=974)": (39, 974, 19, 17),
    "G4 (y=1229)": (403, 1229, 56, 66),
    "G5 (y=1315)": (237, 1315, 53, 43),
    "G6 (y=1338)": (234, 1338, 53, 42),
}


def ring_stats(x, y, w, h, pad=10):
    x0 = max(0, x - pad); y0 = max(0, y - pad)
    x1 = min(W, x + w + pad); y1 = min(H, y + h + pad)
    outer = gray[y0:y1, x0:x1] < 160
    inner = gray[y:y + h, x:x + w] < 160
    # ring = outer minus inner box
    ring = outer.copy()
    ring[y - y0:y - y0 + h, x - x0:x - x0 + w] = False
    ink_ring = outer.sum() - ring.sum()  # ink inside inner box
    ring_cov = ring.mean()
    inner_cov = inner.mean()
    # hollow-ness: ink on the border band vs center
    cy0 = y - y0 + h // 4; cy1 = y - y0 + 3 * h // 4
    cx0 = x - x0 + w // 4; cx1 = x - x0 + 3 * w // 4
    center = outer[cy0:cy1, cx0:cx1]
    center_cov = center.mean()
    return ring_cov, inner_cov, center_cov


print("candidate            ring_cov inner_cov center_cov")
for name, (x, y, w, h) in G.items():
    ring_cov, inner_cov, center_cov = ring_stats(x, y, w, h)
    print("%-22s %.3f     %.3f     %.3f" % (name, ring_cov, inner_cov, center_cov))

# Also: black ink around G2 at various pads
print("\nG2 ink profile by pad:")
for pad in (4, 8, 12, 16, 24):
    x, y, w, h = G["G2 (y=824) CONFIRMED"]
    ring_cov, inner_cov, center_cov = ring_stats(x, y, w, h, pad)
    print("  pad=%2d: ring_cov=%.3f inner_cov=%.3f" % (pad, ring_cov, inner_cov))

# What does the G2 neighborhood look like numerically? Ink rows/cols
print("\nG2 neighborhood 40x60 ink pattern ('#'=dark ink, '+'=gold, '.'=paper):")
x, y, w, h = G["G2 (y=824) CONFIRMED"]
r = a[:, :, 0].astype(np.int32); g = a[:, :, 1].astype(np.int32); b = a[:, :, 2].astype(np.int32)
mx = np.maximum(np.maximum(r, g), b); mn = np.minimum(np.minimum(r, g), b)
sat = mx - mn
hue = np.where(mx == r, ((g - b) / np.maximum(mx - mn, 1) * 60 + 360) % 360,
               np.where(mx == g, 60 * (2 + (b - r) / np.maximum(mx - mn, 1)),
                        60 * (4 + (r - g) / np.maximum(mx - mn, 1))))
y0 = max(0, y - 17); y1 = min(H, y + h + 17)
x0 = max(0, x - 22); x1 = min(W, x + w + 22)
for yy in range(y0, y1, 2):
    row = ""
    for xx in range(x0, x1, 1):
        dark = gray[yy, xx] < 160
        goldp = (25 <= hue[yy, xx] < 50) and sat[yy, xx] > 45
        row += "#" if dark else ("+" if goldp else ".")
    print("  ", row)
