# -*- coding: utf-8 -*-
"""
mwdoa: rank G2-like candidates by direct patch similarity to the confirmed
marker (G2, 18x26 tallish golden ornament). Print the top scores and check
whether the score distribution is bimodal (markers vs noise).
"""
import numpy as np
from PIL import Image
import cv2

DIR = r"D:\apps\quran\mushafy\public\assets\mushuf_mwdoa_images"
G2 = (147, 824, 18, 26)  # x, y, w, h on page 300


def uniform_bands_lh(gray, th=160):
    H, W = gray.shape
    ink = gray < th
    cold = ink.sum(axis=0) / H
    keep = np.where(cold <= 0.4)[0]
    if len(keep) < W * 0.4:
        keep = np.arange(int(W * 0.08), int(W * 0.92))
    inner = ink[:, keep]
    rowd = inner.sum(axis=1) / inner.shape[1]
    raw, in_b = [], False
    for i, v in enumerate(rowd):
        if v > 0.03 and not in_b:
            st, in_b = i, True
        elif v <= 0.03 and in_b:
            if i - st > 25:
                raw.append((st, i))
            in_b = False
    if in_b and H - st > 25:
        raw.append((st, H))
    raw = [b for b in raw if b[0] > 5 and b[1] < H - 5]
    hs = [b[1] - b[0] for b in raw]
    med = float(np.median(hs))
    raw = [b for b in raw if (b[1] - b[0]) >= 0.45 * med]
    lh = float(np.median([b[1] - b[0] for b in raw]))
    bands = [(int(round((y0 + y1) / 2 - lh / 2)), int(round((y0 + y1) / 2 + lh / 2)))
             for (y0, y1) in raw]
    return bands, lh


def goldness(a):
    r = a[:, :, 0].astype(np.int32)
    g = a[:, :, 1].astype(np.int32)
    b = a[:, :, 2].astype(np.int32)
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    sat = mx - mn
    hue = np.where(mx == r, ((g - b) / np.maximum(mx - mn, 1) * 60 + 360) % 360,
                   np.where(mx == g, 60 * (2 + (b - r) / np.maximum(mx - mn, 1)),
                            60 * (4 + (r - g) / np.maximum(mx - mn, 1))))
    return ((hue >= 22) & (hue < 52) & (sat > 40) & (mx < 245)).astype(np.uint8)


def patch(gray_map, x, y, w, h, size=48, pad=10):
    H, W = gray_map.shape
    x0 = max(0, x - pad); y0 = max(0, y - pad)
    x1 = min(W, x + w + pad); y1 = min(H, y + h + pad)
    crop = gray_map[y0:y1, x0:x1].astype(np.float32)
    if crop.size == 0:
        return None
    p = cv2.resize(crop, (size, size), interpolation=cv2.INTER_AREA)
    s = p.std()
    return (p - p.mean()) / (s + 1e-6)


def main():
    im = Image.open(DIR + "\\page_0300.webp").convert("RGB")
    a = np.array(im)
    gray = np.array(im.convert("L"))
    bands, lh = uniform_bands_lh(gray)
    gold = goldness(a)

    # template: G2 on the GOLD map (marker = golden ornament)
    tg = patch(gold.astype(np.float32), *G2)
    # template: G2 on GRAY map
    tgray = patch(gray, *G2)

    # candidates: tallish compact golden components inside bands
    n, labels, stats, cents = cv2.connectedComponentsWithStats(gold, 8)
    cands = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if not (10 <= w <= 34 and 14 <= h <= 42):
            continue
        ar = h / float(w)
        if ar < 0.8 or ar > 2.6:
            continue
        cy = y + h / 2.0
        if not any(bb[0] - 10 <= cy <= bb[1] + 10 for bb in bands):
            continue
        cands.append((x, y, w, h, area))
    print("tallish golden candidates on p300:", len(cands))

    scored = []
    for (x, y, w, h, area) in cands:
        pg_ = patch(gold.astype(np.float32), x, y, w, h)
        pc = patch(gray, x, y, w, h)
        if pg_ is None or pc is None:
            continue
        sg = float((pg_ * tg).mean())
        sc = float((pc * tgray).mean())
        # skip the self-match
        selfpos = abs(x - G2[0]) < 4 and abs(y - G2[1]) < 4
        scored.append((max(sg, sc), sg, sc, x, y, w, h, selfpos))

    scored.sort(reverse=True)
    print("\ntop 30 by score (score, gold-NCC, gray-NCC, x, y, w, h, isG2):")
    for s in scored[:30]:
        print("  %.3f  %.3f  %.3f   x=%4d y=%4d %2dx%2d %s"
              % (s[0], s[1], s[2], s[3], s[4], s[5], s[6], "G2" if s[7] else ""))

    # distribution of scores
    sc_arr = np.array([s[0] for s in scored])
    print("\nscore distribution: max=%.2f p75=%.2f median=%.2f min=%.2f"
          % (sc_arr.max(), np.percentile(sc_arr, 75), np.median(sc_arr), sc_arr.min()))
    hist, edges = np.histogram(sc_arr, bins=10, range=(0, 1))
    for i in range(10):
        print("  %.1f-%.1f: %s (%d)" % (edges[i], edges[i + 1], "#" * int(hist[i] / 2), hist[i]))


main()
