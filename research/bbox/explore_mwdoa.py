# -*- coding: utf-8 -*-
"""
Explore mwdoa pages: what do the ayah-end markers look like, and can we
detect them as compact connected components with distinctive color/geometry?

Page 300 of mwdoa: expected ~8 ayah-end markers (if pagination is standard,
18:54..18:61 like the classic layout).
"""
import numpy as np
from PIL import Image
import cv2

IMG = r"D:\apps\quran\mushafy\public\assets\mushuf_mwdoa_images\page_0300.webp"

im = Image.open(IMG).convert("RGB")
a = np.array(im)
gray = np.array(im.convert("L"))
H, W = gray.shape
print("size", (W, H), "gray mean", round(float(gray.mean()), 1))

for TH in (140, 160, 180):
    ink = (gray < TH).astype(np.uint8)
    # line bands for scale reference
    rowd = ink.sum(axis=1) / W
    bands, in_b = [], False
    for i, v in enumerate(rowd):
        if v > 0.03 and not in_b:
            st, in_b = i, True
        elif v <= 0.03 and in_b:
            if i - st > 25:
                bands.append((st, i))
            in_b = False
    if in_b:
        bands.append((st, H))
    print("\nth=%d: bands=%d" % (TH, len(bands)))
    if not bands:
        continue
    lh = np.median([b[1] - b[0] for b in bands])
    print("  median line height:", lh)

    n, labels, stats, cents = cv2.connectedComponentsWithStats(ink, 8)
    cands = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if h < 0.25 * lh or h > 1.3 * lh:
            continue
        if w < 0.25 * lh or w > 1.3 * lh:
            continue
        if w > h * 1.8 or h > w * 1.8:
            continue
        fill = area / float(w * h)
        if fill < 0.30:
            continue
        # mean color of the component
        mask = labels == i
        px = a[mask]
        mean_col = px.mean(axis=0).astype(int)
        # colorfulness
        mx = px.max(axis=0).astype(int)
        mn = px.min(axis=0).astype(int)
        sat = int(mx.max() - mn.max())
        cands.append((x, y, w, h, int(area), round(fill, 2),
                      tuple(mean_col), sat, int((y + h / 2))))
    print("  marker candidates:", len(cands))
    for c in sorted(cands, key=lambda c: (c[8], c[0])):
        print("   x=%4d y=%4d w=%3d h=%3d fill=%.2f col=%s sat=%d"
              % (c[0], c[1], c[2], c[3], c[5], c[6], c[7]))
