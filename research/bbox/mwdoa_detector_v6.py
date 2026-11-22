# -*- coding: utf-8 -*-
"""
mwdoa detector v6: the end-of-ayah marker is an ornate GOLDEN NUMBER written
inline (user-confirmed G2 = such digits), separated from the surrounding
text by typesetting gaps.

Signature: a golden cluster inside a line band with clear HORIZONTAL paper
gaps on BOTH sides (measured at the cluster's vertical center row).
Word-internal golden fragments have neighboring strokes within a few px.
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
    return ((hue >= 22) & (hue < 52) & (sat > 40) & (mx < 245)).astype(np.uint8)


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
    if not raw:
        return [], 0
    hs = [b[1] - b[0] for b in raw]
    med = float(np.median(hs))
    raw = [b for b in raw if (b[1] - b[0]) >= 0.45 * med]
    lh = float(np.median([b[1] - b[0] for b in raw]))
    bands = [(int(round((y0 + y1) / 2 - lh / 2)), int(round((y0 + y1) / 2 + lh / 2)))
             for (y0, y1) in raw]
    return bands, lh


def hgap_runs(busy_row, x0, x1, W):
    """paper-run length to the left and right of [x0,x1] in a busy row."""
    left = 0
    xx = x0 - 1
    while xx >= 0 and not busy_row[xx]:
        left += 1
        xx -= 1
    right = 0
    xx = x1 + 1
    while xx < W and not busy_row[xx]:
        right += 1
        xx += 1
    return left, right


def detect(a, gray, bands, lh, gap_min=6, sat_th=40):
    gold = gold_mask(a)
    # any ink (gold OR dark OR mid) for the gap test
    busy = ((gold > 0) | (gray < 215)).astype(np.uint8)
    H, W = gold.shape
    n, labels, stats, cents = cv2.connectedComponentsWithStats(gold, 8)
    out = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if w < 7 or w > 44:
            continue
        if h < 10 or h > 40:
            continue
        fill = area / float(w * h)
        if fill < 0.12:
            continue
        cy = y + h / 2.0
        bi = next((k for k, bb in enumerate(bands) if bb[0] - 6 <= cy <= bb[1] + 6), None)
        if bi is None:
            continue
        row = busy[int(cy)]
        left, right = hgap_runs(row, x, x + w - 1, W)
        if left < gap_min or right < gap_min:
            continue
        out.append((int(x), int(y), int(w), int(h), bi + 1, left, right))
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

    # does the confirmed G2 pass?
    im = Image.open(os.path.join(PAGES_DIR, "page_0300.webp")).convert("RGB")
    a = np.array(im)
    gray = np.array(im.convert("L"))
    bands, lh = uniform_bands_lh(gray)
    marks = detect(a, gray, bands, lh)
    g2 = [m for m in marks if abs(m[0] - 147) < 12 and abs(m[1] - 824) < 12]
    print("G2 detected by v6 on p300:", bool(g2), g2)

    sample = list(range(3, 605, 9))
    for gap_min in (4, 6, 8, 10, 12):
        exact = 0
        deltas = []
        for pg in sample:
            im = Image.open(os.path.join(
                PAGES_DIR, "page_%04d.webp" % pg)).convert("RGB")
            a = np.array(im)
            gray = np.array(im.convert("L"))
            bands, lh = uniform_bands_lh(gray)
            marks = detect(a, gray, bands, lh, gap_min=gap_min)
            e = ends.get(pg, 0)
            deltas.append(len(marks) - e)
            if len(marks) == e:
                exact += 1
        import collections
        dist = collections.Counter(deltas)
        med = float(np.median(deltas))
        print("gap>=%2d: exact %2d/%d  median-delta=%+.1f  dist(head)=%s"
              % (gap_min, exact, len(sample), med,
                 dict(sorted(dist.items())[:8])))


main()
