# -*- coding: utf-8 -*-
"""Ayah-boundary gap test, equal footing for both DBs.

At a true ayah boundary inside a line the print shows: end of last word,
small space, the ayah-end marker (compact ink blob), small space, next
word. So the boundary lands on/near a white gap or a small isolated
ink run. We score both DBs' predicted boundaries the same way.
"""
import os
import sqlite3
import sys

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from generate_ayah_bboxes import page_geometry  # noqa: E402

PAGES_DIR = os.path.join(ROOT, "public", "assets", "mushaf_madinah_images")
CLASSIC = os.path.join(ROOT, "temp", "bbox-research", "ayahinfo_classic_1260.db")
V1421 = os.path.join(ROOT, "temp", "bbox-research", "ayahinfo_1421_1260.db")


def band_columns(ink, keep, a, b, lo=0.12, hi=0.90):
    band = ink[a:b]
    colsum = band.sum(axis=0)
    n = b - a
    ok = ((colsum > lo * n) & (colsum < hi * n) &
          (np.arange(len(colsum)) >= keep[0]) &
          (np.arange(len(colsum)) <= keep[-1]))
    return colsum, ok


def classify_boundary(colsum, left, right, wx, tol=8):
    """Return 'gap' if near a white gap, 'blob' if near a thin isolated
    ink run (marker), 'ink' if inside a wide ink run."""
    lo_i, hi_i = max(left, int(wx) - tol), min(right, int(wx) + tol)
    if hi_i < lo_i:
        return "ink"
    seg = colsum[lo_i:hi_i + 1] > 0
    # white gap covering wx?
    i = int(wx) - lo_i
    if 0 <= i < len(seg) and not seg[i]:
        return "gap"
    # isolated small ink run around wx (the marker between two gaps)?
    run = 0
    j = i
    while 0 <= j and seg[j]:
        j -= 1
    run_l = i - j
    j = i
    while j < len(seg) and seg[j]:
        j += 1
    run_r = j - i
    run = run_l + run_r
    if run <= 22:  # marker + tiny word bits, not a wide justified word block
        return "blob"
    return "ink"


def load_ayah_segs(path, page):
    con = sqlite3.connect(path)
    cur = con.cursor()
    cur.execute("""SELECT line_number, sura_number, ayah_number,
                  MIN(min_x), MAX(max_x) FROM glyphs WHERE page_number=?
                  GROUP BY line_number, sura_number, ayah_number
                  ORDER BY line_number, MIN(position)""", (page,))
    lines = {}
    for (ln, s, a, x0, x1) in cur.fetchall():
        lines.setdefault(ln, []).append((s, a, x0, x1))
    con.close()
    return lines


def score(path, page, bands, ink, keep, tol=8):
    lines = load_ayah_segs(path, page)
    stats = {"gap": 0, "blob": 0, "ink": 0}
    tot = 0
    for ln, segs in sorted(lines.items()):
        if len(segs) < 2 or not (0 < ln <= len(bands)):
            continue
        a, b = bands[ln - 1]
        colsum, ok = band_columns(ink, keep, a, b)
        if not ok.any():
            continue
        left, right = int(np.where(ok)[0].min()), int(np.where(ok)[0].max())
        dbx0 = min(x0 for (_, _, x0, _) in segs)
        dbx1 = max(x1 for (_, _, _, x1) in segs)
        if dbx1 <= dbx0:
            continue
        s_ = (right - left) / float(dbx1 - dbx0)
        t_ = left - dbx0 * s_
        xs = sorted((x0, x1) for (_, _, x0, x1) in segs)
        for (x0a, x1a), (x0b, x1b) in zip(xs, xs[1:]):
            wx = ((x1a + x0b) / 2.0) * s_ + t_
            k = classify_boundary(colsum, left, right, wx, tol)
            stats[k] += 1
            tot += 1
    return stats, tot


def main():
    pages = [int(x) for x in sys.argv[1:]] or [564]
    for page in pages:
        gray = np.array(Image.open(os.path.join(
            PAGES_DIR, "page_%04d.webp" % page)).convert("L"))
        H, W = gray.shape
        ink = gray < 205
        (c0, c1), bands, _ = page_geometry(gray, 205)
        keep = np.arange(c0, c1 + 1)
        print("p%d bands=%d" % (page, len(bands)))
        for label, path in (("classic-1405", CLASSIC),
                            ("madani-1421", V1421)):
            st, tot = score(path, page, bands, ink, keep)
            good = st["gap"] + st["blob"]
            print("  %-12s: %d boundaries -> gap %d, blob %d, ink %d"
                  "  => %.0f%% plausible"
                  % (label, tot, st["gap"], st["blob"], st["ink"],
                     100.0 * good / tot if tot else 0))


if __name__ == "__main__":
    main()
