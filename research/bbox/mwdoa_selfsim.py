# -*- coding: utf-8 -*-
"""
mwdoa: self-similarity mining for the marker class.

The end-of-ayah ornament repeats many times per page; random letter/diacritic
fragments rarely do. So: collect ALL compact isolated blobs inside the line
bands (any ink, not just golden), describe each as a normalized patch, and
find the largest mutually-similar cluster. That cluster should be the marker
class. Validate: cluster size per page ~ expected ayah ends; and G2 (the
user-confirmed marker on p300) must belong to the winning cluster.
"""
import numpy as np
from PIL import Image
import cv2

DIR = r"D:\apps\quran\mushafy\public\assets\mushuf_mwdoa_images"
G2 = (147, 824, 18, 26)  # user-confirmed marker on page 300


def uniform_bands(gray, th=160):
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
    if not raw:
        return []
    hs = [b[1] - b[0] for b in raw]
    med = float(np.median(hs))
    raw = [b for b in raw if (b[1] - b[0]) >= 0.45 * med]
    lh = float(np.median([b[1] - b[0] for b in raw]))
    return [(int(round((y0 + y1) / 2 - lh / 2)), int(round((y0 + y1) / 2 + lh / 2)))
            for (y0, y1) in raw], lh


def candidates(a, gray, bands, lh):
    """compact, reasonably isolated blobs inside bands (any ink)."""
    H, W = gray.shape
    ink = (gray < 200).astype(np.uint8)
    # close small gaps so letters merge into words (leaving isolated ornaments)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    closed = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, k)
    n, labels, stats, cents = cv2.connectedComponentsWithStats(closed, 8)
    out = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if h < 0.15 * lh or h > 0.9 * lh:
            continue
        if w < 0.08 * lh or w > 0.9 * lh:
            continue
        if w > h * 3.0 or h > w * 3.0:
            continue
        cy = y + h / 2.0
        if not any(bb[0] - 10 <= cy <= bb[1] + 10 for bb in bands):
            continue
        out.append((int(x), int(y), int(w), int(h), int(area)))
    return out


def patch_desc(gray, x, y, w, h, size=44, pad=8):
    H, W = gray.shape
    x0 = max(0, x - pad); y0 = max(0, y - pad)
    x1 = min(W, x + w + pad); y1 = min(H, y + h + pad)
    crop = gray[y0:y1, x0:x1].astype(np.float32)
    if crop.size == 0:
        return None
    p = cv2.resize(crop, (size, size), interpolation=cv2.INTER_AREA)
    p = (p - p.mean()) / (p.std() + 1e-6)
    return p


def ncc(p, q):
    return float((p * q).mean())


def mine_page(pg, expected=None):
    im = Image.open(DIR + "\\page_%04d.webp" % pg).convert("RGB")
    a = np.array(im)
    gray = np.array(im.convert("L"))
    bands_lh = uniform_bands(gray)
    if not bands_lh:
        return None
    bands, lh = bands_lh
    cands = candidates(a, gray, bands, lh)
    descs = []
    for (x, y, w, h, area) in cands:
        d = patch_desc(gray, x, y, w, h)
        if d is not None:
            descs.append((x, y, w, h, area, d))
    if len(descs) < 4:
        return None

    # find the largest mutually-similar cluster
    best = []
    for i, (x, y, w, h, area, d) in enumerate(descs):
        similar = [i]
        for j, (x2, y2, w2, h2, area2, d2) in enumerate(descs):
            if j == i:
                continue
            # avoid near-duplicates
            if abs(x2 - x) < 15 and abs(y2 - y) < 15:
                similar.append(j)
                continue
            if not (0.7 * w <= w2 <= 1.4 * w and 0.7 * h <= h2 <= 1.4 * h):
                continue
            if ncc(d, d2) > 0.55:
                similar.append(j)
        if len(similar) > len(best):
            best = similar
            seed = (x, y, w, h)

    cluster = [descs[j] for j in best]
    print("page %d: candidates=%d, best cluster=%d  seed=(x=%d y=%d w=%d h=%d)"
          % (pg, len(descs), len(cluster), *seed))
    # is the confirmed G2 inside the cluster?
    if pg == 300:
        inside = any(abs(c[0] - G2[0]) < 20 and abs(c[1] - G2[1]) < 20 for c in cluster)
        print("   confirmed G2 in cluster:", inside)
    return cluster


for pg, exp in [(300, 8), (3, 11), (50, 9), (120, 6), (400, 8)]:
    mine_page(pg, exp)
