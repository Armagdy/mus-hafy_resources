# -*- coding: utf-8 -*-
"""
mwdoa: find the ayah-marker color.

The thematic mushaf color-codes text by topic, but the end-of-ayah medallion
is usually a FIXED color across the whole book. For each hue bucket we:
  - build a mask of saturated pixels in that hue,
  - count compact blobs whose center sits in a text-line band.
The marker hue shows up as the bucket whose blob count is stable (~5-10)
across pages and whose blobs are roughly square, ~line-height sized.
"""
import numpy as np
from PIL import Image
import cv2

DIR = r"D:\apps\quran\mushafy\public\assets\mushuf_mwdoa_images"
PAGES = [300, 50, 120, 400]


def line_bands(gray, th=160):
    H, W = gray.shape
    ink = gray < th
    cold = ink.sum(axis=0) / H
    keep = np.where(cold <= 0.4)[0]
    if len(keep) < W * 0.4:
        keep = np.arange(int(W * 0.08), int(W * 0.92))
    inner = ink[:, keep]
    rowd = inner.sum(axis=1) / inner.shape[1]
    bands, in_b = [], False
    for i, v in enumerate(rowd):
        if v > 0.03 and not in_b:
            st, in_b = i, True
        elif v <= 0.03 and in_b:
            if i - st > 25:
                bands.append((st, i))
            in_b = False
    if in_b and H - st > 25:
        bands.append((st, H))
    bands = [b for b in bands if b[0] > 5 and b[1] < H - 5]
    if bands:
        hs = [b[1] - b[0] for b in bands]
        med = float(np.median(hs))
        bands = [b for b in bands if (b[1] - b[0]) >= 0.45 * med]
    return bands


def analyze(pg):
    im = Image.open(DIR + r"\page_%04d.webp" % pg).convert("RGB")
    a = np.array(im).astype(np.int32)
    gray = np.array(im.convert("L"))
    bands = line_bands(gray)
    lh = float(np.median([b[1] - b[0] for b in bands])) if bands else 60
    H, W = gray.shape

    r, g, b = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    sat = mx - mn
    # HSV hue
    hue = np.zeros((H, W), np.float32)
    nz = mx > 10
    hr = ((g - b) / np.maximum(mx - mn, 1) * 60 + 360) % 360
    hg = 60 * (2 + (b - r) / np.maximum(mx - mn, 1))
    hb = 60 * (4 + (r - g) / np.maximum(mx - mn, 1))
    hue = np.where(mx == r, hr, np.where(mx == g, hg, hb))

    colored = (sat > 60) & (mx < 240)  # saturated, not paper-white
    print("\npage %d: bands=%d lh=%.0f colored=%.2f%%"
          % (pg, len(bands), lh, 100 * colored.mean()))

    results = []
    for h0 in range(0, 360, 15):
        mask = ((hue >= h0) & (hue < h0 + 15) & colored).astype(np.uint8)
        if mask.sum() < 500:
            continue
        n, labels, stats, cents = cv2.connectedComponentsWithStats(mask, 8)
        cnt = 0
        sizes = []
        for i in range(1, n):
            x, y, w, h, area = stats[i]
            if h < 0.2 * lh or h > 1.2 * lh:
                continue
            if w < 0.2 * lh or w > 1.2 * lh:
                continue
            if w > h * 1.8 or h > w * 1.8:
                continue
            cy = y + h / 2.0
            if not any(bb[0] - 6 <= cy <= bb[1] + 6 for bb in bands):
                continue
            cnt += 1
            sizes.append((w, h))
        if cnt:
            results.append((cnt, h0, mask.sum(), sizes[:4]))
    for cnt, h0, npx, sizes in sorted(results, reverse=True)[:12]:
        print("  hue %3d-%3d: blobs-in-bands=%2d px=%6d sizes=%s"
              % (h0, h0 + 15, cnt, npx, sizes))


for pg in PAGES:
    analyze(pg)
