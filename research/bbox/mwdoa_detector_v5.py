# -*- coding: utf-8 -*-
"""
mwdoa marker detector v5: golden blob + WHITE ISOLATION.

The confirmed marker (G2) is a compact golden ornament sitting in cleared
paper space (gap between the ayah's last word and the next content).
Golden TEXT fragments always have neighboring strokes close by, so they fail
the isolation test.

Validation: per-page counts vs expected ayah ends (classic layout), plus
threshold sweeps for the isolation/fill parameters.
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


def gold_and_dark(a):
    r = a[:, :, 0].astype(np.int32)
    g = a[:, :, 1].astype(np.int32)
    b = a[:, :, 2].astype(np.int32)
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    sat = mx - mn
    gray = mx  # ~luminance proxy
    hue = np.where(mx == r, ((g - b) / np.maximum(mx - mn, 1) * 60 + 360) % 360,
                   np.where(mx == g, 60 * (2 + (b - r) / np.maximum(mx - mn, 1)),
                            60 * (4 + (r - g) / np.maximum(mx - mn, 1))))
    gold = ((hue >= 22) & (hue < 52) & (sat > 45) & (gray < 245)).astype(np.uint8)
    dark = (gray < 170).astype(np.uint8)
    return gold, dark


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


def detect(a, bands, iso_pad=12, iso_thresh=0.80, fill_lo=0.15, sat_th=50):
    gold, dark = gold_and_dark(a)
    H, W = gold.shape
    if not bands:
        return []
    lh = float(bands[0][1] - bands[0][0])
    n, labels, stats, cents = cv2.connectedComponentsWithStats(gold, 8)
    busy = ((gold > 0) | (dark > 0)).astype(np.uint8)
    out = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if h < 0.18 * lh or h > 0.65 * lh:
            continue
        if w < 0.10 * lh or w > 0.55 * lh:
            continue
        if h < w * 0.85:
            continue
        fill = area / float(w * h)
        if fill < fill_lo or fill > 0.60:
            continue
        cy = y + h / 2.0
        if not any(bb[0] - 10 <= cy <= bb[1] + 10 for bb in bands):
            continue
        # isolation: halo around the blob must be mostly paper
        x0 = max(0, x - iso_pad); y0 = max(0, y - iso_pad)
        x1 = min(W, x + w + iso_pad); y1 = min(H, y + h + iso_pad)
        halo = busy[y0:y1, x0:x1].astype(bool).copy()
        halo[y - y0:y - y0 + h, x - x0:x - x0 + w] = False
        area_halo = halo.size - w * h
        if area_halo <= 0:
            continue
        iso = 1.0 - halo.sum() / float(area_halo)
        if iso < iso_thresh:
            continue
        out.append((int(x), int(y), int(w), int(h), round(iso, 2)))
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

    print("parameter sweep (isolated golden tallish blobs):")
    for iso_th in (0.70, 0.75, 0.80, 0.85, 0.90):
        exact = 0
        deltas = []
        for pg in sample:
            im = Image.open(os.path.join(
                PAGES_DIR, "page_%04d.webp" % pg)).convert("RGB")
            a = np.array(im)
            gray = np.array(im.convert("L"))
            bands = uniform_bands(gray)
            marks = detect(a, bands, iso_thresh=iso_th)
            e = ends.get(pg, 0)
            deltas.append(len(marks) - e)
            if len(marks) == e:
                exact += 1
        import collections
        dist = collections.Counter(deltas)
        print("  iso=%.2f: exact %d/%d  delta-dist %s"
              % (iso_th, exact, len(sample), dict(sorted(dist.items())[:10])))

    # detailed look with the best guess
    for pg in (3, 50, 120, 300, 400):
        im = Image.open(os.path.join(
            PAGES_DIR, "page_%04d.webp" % pg)).convert("RGB")
        a = np.array(im)
        gray = np.array(im.convert("L"))
        bands = uniform_bands(gray)
        marks = detect(a, bands)
        print("page %3d: detected=%2d expected=%2d"
              % (pg, len(marks), ends.get(pg, 0)))


main()
