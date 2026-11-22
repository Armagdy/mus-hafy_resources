# -*- coding: utf-8 -*-
"""
mwdoa marker-count validation.

Detector: gray<160 connected components that are compact (roughly square,
0.25-1.1 x line height), reasonably filled (>=0.30), and whose center sits
inside a detected text-line band.

Validation: for each page, the number of detected markers should equal the
number of ayahs ENDING on that page in the standard Madani layout
(derivable from the classic DB: ayah keys on page p that do not appear on
page p+1).

If the counts match on most pages => mwdoa follows the standard pagination
AND the detector works => boxes can be generated.
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
SAMPLE = list(range(2, 605, 7))  # ~86 pages


def line_bands(gray, th=160, min_d=0.03, gap=25):
    H, W = gray.shape
    ink = gray < th
    # mask frame columns (dense over most of height)
    cold = ink.sum(axis=0) / H
    keep = np.where(cold <= 0.4)[0]
    if len(keep) < W * 0.4:
        keep = np.arange(int(W * 0.08), int(W * 0.92))
    inner = ink[:, keep]
    rowd = inner.sum(axis=1) / inner.shape[1]
    bands, in_b = [], False
    for i, v in enumerate(rowd):
        if v > min_d and not in_b:
            st, in_b = i, True
        elif v <= min_d and in_b:
            if i - st > gap:
                bands.append((st, i))
            in_b = False
    if in_b and H - st > gap:
        bands.append((st, H))
    bands = [b for b in bands if b[0] > 5 and b[1] < H - 5]
    if bands:
        hs = [b[1] - b[0] for b in bands]
        med = float(np.median(hs))
        bands = [b for b in bands if (b[1] - b[0]) >= 0.45 * med]
    return bands, inner


def detect_markers(gray, bands, inner, th=160):
    if not bands:
        return []
    lh = float(np.median([b[1] - b[0] for b in bands]))
    ink = (gray < th).astype(np.uint8)
    n, labels, stats, cents = cv2.connectedComponentsWithStats(ink, 8)
    out = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if h < 0.25 * lh or h > 1.15 * lh:
            continue
        if w < 0.25 * lh or w > 1.15 * lh:
            continue
        if w > h * 1.7 or h > w * 1.7:
            continue
        fill = area / float(w * h)
        if fill < 0.30 or fill > 0.85:
            continue
        cy = y + h / 2.0
        cx = x + w / 2.0
        # center must be inside (or very near) a line band
        ok = any(b[0] - 6 <= cy <= b[1] + 6 for b in bands)
        if not ok:
            continue
        out.append((int(cx), int(cy), int(w), int(h), round(fill, 2)))
    return out


def expected_counts(con):
    """ayahs ENDING on each page, per the classic layout."""
    cur = con.cursor()
    page_keys = {}
    for pg in range(1, 605):
        cur.execute(
            "SELECT DISTINCT sura_number, ayah_number FROM glyphs "
            "WHERE page_number=?", (pg,))
        page_keys[pg] = set(cur.fetchall())
    ends = {}
    for pg in range(1, 604):
        ends[pg] = len(page_keys[pg] - page_keys[pg + 1])
    ends[604] = len(page_keys[604])
    return ends


def main():
    db = gen.ensure_db()
    con = sqlite3.connect(db)
    ends = expected_counts(con)
    match = 0
    off = []
    total = 0
    for pg in SAMPLE:
        path = os.path.join(PAGES_DIR, "page_%04d.webp" % pg)
        gray = np.array(Image.open(path).convert("L"))
        bands, inner = line_bands(gray)
        marks = detect_markers(gray, bands, inner)
        exp = ends.get(pg, 0)
        total += 1
        d = len(marks) - exp
        if d == 0:
            match += 1
        else:
            off.append((pg, len(marks), exp))
        if pg in (2, 3, 300, 604):
            print("page %3d: detected=%d expected=%d bands=%d"
                  % (pg, len(marks), exp, len(bands)))
    print("\nsampled %d pages: exact count match on %d (%.0f%%)"
          % (total, match, 100.0 * match / max(total, 1)))
    print("mismatched (page, detected, expected):")
    print(" ", off[:40])
    if off:
        import collections
        dist = collections.Counter(d for (_, m, e) in off for d in [m - e])
        print("delta distribution:", dict(dist))


main()
