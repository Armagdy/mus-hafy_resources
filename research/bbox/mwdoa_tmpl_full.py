# -*- coding: utf-8 -*-
"""
Template matching with the FULL confirmed medallion (53x64 at x=239 y=972 on
page 300) — the earlier attempt failed because the template was a tiny
fragment of the ornament. The diamond outline dominates; only the small
number inside the rosette varies.
"""
import numpy as np
from PIL import Image
import cv2

DIR = r"D:\apps\quran\mushafy\public\assets\mushuf_mwdoa_images"
CONFIRMED = (239, 972, 53, 64)  # x, y, w, h on page 300 (user: row 11 col 8)


def gold_map(a, sat_th=38):
    r = a[:, :, 0].astype(np.int32)
    g = a[:, :, 1].astype(np.int32)
    b = a[:, :, 2].astype(np.int32)
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    sat = mx - mn
    hue = np.where(mx == r, ((g - b) / np.maximum(mx - mn, 1) * 60 + 360) % 360,
                   np.where(mx == g, 60 * (2 + (b - r) / np.maximum(mx - mn, 1)),
                            60 * (4 + (r - g) / np.maximum(mx - mn, 1))))
    gold = ((hue >= 22) & (hue < 52) & (sat > sat_th) & (mx < 248))
    return np.where(gold, np.clip(sat, 0, 255), 0).astype(np.uint8)


def main():
    im300 = Image.open(DIR + "\\page_0300.webp").convert("RGB")
    a300 = np.array(im300)
    gm300 = gold_map(a300)

    # template: full medallion + small padding
    pad = 8
    x, y, w, h = CONFIRMED
    x0 = max(0, x - pad); y0 = max(0, y - pad)
    x1 = min(gm300.shape[1], x + w + pad); y1 = min(gm300.shape[0], y + h + pad)
    tmpl = gm300[y0:y1, x0:x1]
    print("template size:", tmpl.shape)

    res = cv2.matchTemplate(gm300, tmpl, cv2.TM_CCOEFF_NORMED)
    loc = np.where(res >= 0.55)
    pts = sorted(zip(loc[1], loc[0], res[loc[0], loc[1]]), key=lambda p: -p[2])
    kept = []
    for (py, px, s) in pts:
        if all(abs(py - ky) > 30 or abs(px - kx) > 30 for (ky, kx, _) in kept):
            kept.append((py, px, float(s)))
        if len(kept) >= 25:
            break
    print("\npage 300 matches (y, x, score):")
    for (py, px, s) in kept:
        tag = ""
        if abs(px - x) < 25 and abs(py - y) < 25:
            tag = " <== confirmed marker"
        print("   y=%4d x=%4d score=%.2f%s" % (py, px, s, tag))

    # try on other pages with the same template
    for pg in (3, 50, 120, 400):
        im = Image.open(DIR + "\\page_%04d.webp" % pg).convert("RGB")
        gm = gold_map(np.array(im))
        res = cv2.matchTemplate(gm, tmpl, cv2.TM_CCOEFF_NORMED)
        loc = np.where(res >= 0.55)
        pts = sorted(zip(loc[1], loc[0], res[loc[0], loc[1]]), key=lambda p: -p[2])
        kept = []
        for (py, px, s) in pts:
            if all(abs(py - ky) > 30 or abs(px - kx) > 30 for (ky, kx, _) in kept):
                kept.append((py, px, float(s)))
            if len(kept) >= 25:
                break
        print("\npage %d: matches>=0.55: %d  top scores: %s"
              % (pg, len(kept), [round(k[2], 2) for k in kept[:12]]))

    # score distribution on page 3 to find a separating threshold
    im = Image.open(DIR + "\\page_0003.webp").convert("RGB")
    gm = gold_map(np.array(im))
    res = cv2.matchTemplate(gm, tmpl, cv2.TM_CCOEFF_NORMED)
    print("\npage 3 score histogram (all positions):")
    hist, edges = np.histogram(res, bins=10, range=(-1, 1))
    for i in range(10):
        print("  %.1f..%.1f: %d" % (edges[i], edges[i + 1], hist[i]))


main()
