# -*- coding: utf-8 -*-
"""
mwdoa marker detector v4: exact G2 signature + isolation.

G2 (confirmed marker): w=18 h=26 at lh=70 -> w~0.26x lh, h~0.37x lh,
h/w=1.44, fill 0.26 (in gold mask), sat 72, compact ISOLATED cluster.

Isolation: dilate the component by ~8px; if it merges with other gold pixels
beyond ~1.6x its own size, it's part of a text stream, not a marker.
"""
import importlib.util
import os
import sqlite3

import numpy as np
from PIL import Image
import cv2

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
spec = importlib.util.spec_from_file_location(
    "gen", os.path.join(ROOT, "scripts", "generate_ayah_bboxes.py"))
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)

PAGES_DIR = os.path.join(ROOT, "public", "assets", "mushuf_mwdoa_images")


def gold_mask(a):
    r = a[:, :, 0].astype(np.int32)
    g = a[:, :, 1].astype(np.int32)
    b = a[:, :, 2].astype(np.int32)
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    sat = mx - mn
    hue = np.where(mx == r, ((g - b) / np.maximum(mx - mn, 1) * 60 + 360) % 360,
                   np.where(mx == g, 60 * (2 + (b - r) / np.maximum(mx - mn, 1)),
                            60 * (4 + (r - g) / np.maximum(mx - mn, 1))))
    return ((hue >= 25) & (hue < 50) & (sat > 62) & (mx < 245)).astype(np.uint8)


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
            for (y0, y1) in raw]


def detect(gm, bands):
    if not bands:
        return []
    lh = float(bands[0][1] - bands[0][0])
    # dilate gold to merge nearby streams
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (13, 13))
    dil = cv2.dilate(gm, k)
    n, labels, stats, cents = cv2.connectedComponentsWithStats(dil, 8)
    out = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        # after dilation the component includes a halo around the marker;
        # expected marker: core ~ (18x26) + halo ~ +6px each side -> ~30x38
        if h < 0.25 * lh or h > 0.75 * lh:
            continue
        if w < 0.18 * lh or w > 0.60 * lh:
            continue
        ar = h / float(w)
        if ar < 0.9 or ar > 2.6:
            continue
        # isolation: the component must be small — huge merged regions are text
        if area > 1.8 * lh * lh:
            continue
        cy = y + h / 2.0
        if not any(bb[0] - 10 <= cy <= bb[1] + 10 for bb in bands):
            continue
        out.append((int(x + 6), int(y + 6), int(w - 12), int(h - 12), int(area)))
    return out


def expected_counts(con):
    cur = con.cursor()
    page_keys = {}
    for pg in range(1, 605):
        cur.execute("SELECT DISTINCT sura_number, ayah_number FROM glyphs WHERE page_number=?", (pg,))
        page_keys[pg] = set(cur.fetchall())
    ends = {}
    for pg in range(1, 604):
        ends[pg] = len(page_keys[pg] - page_keys[pg + 1])
    ends[604] = len(page_keys[604])
    return ends


def main():
    con = sqlite3.connect(gen.ensure_db())
    ends = expected_counts(con)
    sample = list(range(3, 605, 9))
    deltas = []
    exact = 0
    for pg in sample:
        im = Image.open(os.path.join(
            PAGES_DIR, "page_%04d.webp" % pg)).convert("RGB")
        a = np.array(im)
        gray = np.array(im.convert("L"))
        bands = uniform_bands(gray)
        marks = detect(gold_mask(a), bands)
        e = ends.get(pg, 0)
        deltas.append(len(marks) - e)
        if len(marks) == e:
            exact += 1
        if pg in (3, 50, 120, 300, 400):
            print("page %3d: detected=%2d expected=%2d"
                  % (pg, len(marks), e))
    import collections
    dist = collections.Counter(deltas)
    print("\nsampled %d pages: exact %d (%.0f%%)" % (len(sample), exact, 100 * exact / len(sample)))
    print("delta distribution (detected - expected):", dict(sorted(dist.items())))


main()
