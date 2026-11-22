# -*- coding: utf-8 -*-
"""
mwdoa marker detector v2 — built around the CONFIRMED marker signature
(user-identified G2 on page 300: small, TALL (h>w), light golden tan,
hue ~35, sat ~72, fill ~0.26, sitting inside a line band).

Validation: per page, detected marker count should equal the number of ayahs
ENDING on that page under the standard Madani pagination (derived from the
classic DB). Good match => detector works AND mwdoa pagination is standard.
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


def uniform_bands(gray, th=160):
    """Line bands snapped to a uniform grid (user: all lines same height)."""
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
    # uniform height = median of surviving bands
    lh = float(np.median([b[1] - b[0] for b in raw]))
    # snap: uniform bands of height lh, centered on each raw band center
    bands = []
    for (y0, y1) in raw:
        c = (y0 + y1) / 2.0
        bands.append((int(round(c - lh / 2)), int(round(c + lh / 2))))
    return bands


def detect_markers(a, gray, bands):
    """G2-signature markers: small, tallish, light-golden, inside a band."""
    if not bands:
        return []
    H, W = gray.shape
    lh = float(bands[0][1] - bands[0][0])
    r, g, b = a[:, :, 0].astype(np.int32), a[:, :, 1].astype(np.int32), a[:, :, 2].astype(np.int32)
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    sat = mx - mn
    hue = np.where(mx == r, ((g - b) / np.maximum(mx - mn, 1) * 60 + 360) % 360,
                   np.where(mx == g, 60 * (2 + (b - r) / np.maximum(mx - mn, 1)),
                            60 * (4 + (r - g) / np.maximum(mx - mn, 1))))
    gold = ((hue >= 25) & (hue < 50) & (sat > 45) & (mx < 245)).astype(np.uint8)
    n, labels, stats, cents = cv2.connectedComponentsWithStats(gold, 8)
    out = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if h < 0.18 * lh or h > 0.75 * lh:
            continue
        if w < 0.10 * lh or w > 0.55 * lh:
            continue
        if h < w * 0.9:            # tallish (G2: h/w = 1.44)
            continue
        fill = area / float(w * h)
        if fill < 0.12 or fill > 0.60:
            continue
        cy = y + h / 2.0
        if not any(bb[0] - 8 <= cy <= bb[1] + 8 for bb in bands):
            continue
        out.append((int(x), int(y), int(w), int(h), round(fill, 2)))
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

    sample = list(range(1, 605, 6))
    match = 0
    close = 0
    results = []
    for pg in sample:
        path = os.path.join(PAGES_DIR, "page_%04d.webp" % pg)
        im = Image.open(path).convert("RGB")
        a = np.array(im).astype(np.int32)
        gray = np.array(im.convert("L"))
        bands = uniform_bands(gray)
        marks = detect_markers(a, gray, bands)
        exp = ends.get(pg, 0)
        d = len(marks) - exp
        results.append((pg, len(marks), exp))
        if d == 0:
            match += 1
        if abs(d) <= 1:
            close += 1
        if pg in (1, 2, 3, 300, 604):
            print("page %3d: detected=%2d expected=%2d bands=%d"
                  % (pg, len(marks), exp, len(bands)))
    total = len(results)
    print("\nsampled %d pages: exact match %d (%.0f%%), within +-1: %d (%.0f%%)"
          % (total, match, 100 * match / total, close, 100 * close / total))
    print("\nsample of mismatches (page, detected, expected):")
    print(" ", [r for r in results if r[1] != r[2]][:30])


main()
