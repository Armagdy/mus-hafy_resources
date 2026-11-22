# -*- coding: utf-8 -*-
"""
mwdoa detector v7b: parameter sweep around the confirmed medallion class.
Target: per-page detected count == expected ayah ends (classic pagination).
"""
import importlib.util
import os
import sqlite3
from collections import Counter

import numpy as np
from PIL import Image
import cv2

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
spec = importlib.util.spec_from_file_location(
    "gen", os.path.join(ROOT, "scripts", "generate_ayah_bboxes.py"))
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)

PAGES_DIR = os.path.join(ROOT, "public", "assets", "mushuf_mwdoa_images")
SAMPLE = list(range(3, 605, 9))


def masks(a, sat_th):
    r = a[:, :, 0].astype(np.int32)
    g = a[:, :, 1].astype(np.int32)
    b = a[:, :, 2].astype(np.int32)
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    sat = mx - mn
    hue = np.where(mx == r, ((g - b) / np.maximum(mx - mn, 1) * 60 + 360) % 360,
                   np.where(mx == g, 60 * (2 + (b - r) / np.maximum(mx - mn, 1)),
                            60 * (4 + (r - g) / np.maximum(mx - mn, 1))))
    gold = ((hue >= 22) & (hue < 52) & (sat > sat_th) & (mx < 248)).astype(np.uint8)
    return gold


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


def detect(a, gray, bands, lh, cfg):
    gold = masks(a, cfg["sat_th"])
    if cfg["dilate"] > 0:
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (cfg["dilate"] * 2 + 1,) * 2)
        gold = cv2.dilate(gold, k)
    H, W = gold.shape
    n, labels, stats, cents = cv2.connectedComponentsWithStats(gold, 8)
    out = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if w < cfg["size_lo"] * lh or w > 1.45 * lh:
            continue
        if h < cfg["size_lo"] * lh or h > 1.45 * lh:
            continue
        ar = h / float(w)
        if ar < 0.5 or ar > 2.4:
            continue
        fill = area / float(w * h)
        if fill < cfg["fill_lo"] or fill > 0.65:
            continue
        cy = y + h / 2.0
        if not any(bb[0] - 10 <= cy <= bb[1] + 10 for bb in bands):
            continue
        m = labels == i
        dark = ((gray[y:y + h, x:x + w] < cfg["dark_th"]) & m[y:y + h, x:x + w])
        if dark.sum() / float(w * h) < cfg["dark_ratio_min"]:
            continue
        out.append((int(x), int(y), int(w), int(h)))
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


def run(cfg, con, ends, cache):
    exact = 0
    deltas = []
    for pg in SAMPLE:
        if pg in cache:
            a, gray, bands, lh = cache[pg]
        else:
            im = Image.open(os.path.join(PAGES_DIR, "page_%04d.webp" % pg)).convert("RGB")
            a = np.array(im)
            gray = np.array(im.convert("L"))
            bands, lh = uniform_bands_lh(gray)
            cache[pg] = (a, gray, bands, lh)
        marks = detect(a, gray, bands, lh, cfg)
        e = ends.get(pg, 0)
        deltas.append(len(marks) - e)
        if len(marks) == e:
            exact += 1
    dist = Counter(deltas)
    return exact, dist


def main():
    con = sqlite3.connect(gen.ensure_db())
    ends = expected_counts(con)
    cache = {}

    grid = []
    for sat_th in (30, 38, 45):
        for dark_th in (150, 180, 200):
            for dark_ratio_min in (0.03, 0.06):
                for dilate in (0, 3):
                    for size_lo, fill_lo in ((0.30, 0.08), (0.38, 0.10)):
                        cfg = dict(sat_th=sat_th, dark_th=dark_th,
                                   dark_ratio_min=dark_ratio_min,
                                   dilate=dilate, size_lo=size_lo,
                                   fill_lo=fill_lo)
                        exact, dist = run(cfg, con, ends, cache)
                        near = sum(v for k, v in dist.items() if abs(k) <= 1)
                        grid.append((exact, near, cfg, dict(sorted(dist.items()))))
    grid.sort(key=lambda t: -t[0])
    print("top configs by exact matches (of %d pages):" % len(SAMPLE))
    for exact, near, cfg, dist in grid[:8]:
        print("  exact=%2d near=%2d  %s" % (exact, near, cfg))
        print("       dist=%s" % dist)


main()
