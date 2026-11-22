# -*- coding: utf-8 -*-
"""Discriminate classic-1405H vs 1421H line layout on the local madinah
images. Bands from the proven page_geometry(); per-band ink profile with
vertical-line columns (inked ~100% of the band) excluded.
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


def band_profile(ink, keep, a, b, lo=0.12, hi=0.90):
    """Extent + white gaps of one band over `keep` columns.

    Columns inked > hi of the band rows are vertical lines (frame remnants)
    and are ignored; columns below lo are noise.
    """
    band = ink[a:b]
    colsum = band.sum(axis=0)
    n = b - a
    txt_lo = np.where((colsum > lo * n) & (colsum < hi * n) &
                      (np.arange(len(colsum)) >= keep[0]) &
                      (np.arange(len(colsum)) <= keep[-1]))[0]
    if not len(txt_lo):
        return None
    left, right = int(txt_lo.min()), int(txt_lo.max())
    inside = (colsum[left:right + 1] == 0)
    gaps, st = [], None
    for i, v in enumerate(inside):
        if v and st is None:
            st = i
        elif not v and st is not None:
            if i - st >= 5:
                gaps.append((left + st, left + i - 1))
            st = None
    if st is not None and len(inside) - st >= 5:
        gaps.append((left + st, right))
    return left, right, gaps


def load_lines(path, page, word_level):
    con = sqlite3.connect(path)
    cur = con.cursor()
    if word_level:
        cur.execute("""SELECT line_number, sura_number, ayah_number,
                      min_x, max_x FROM glyphs WHERE page_number=?
                      ORDER BY line_number, position""", (page,))
    else:
        cur.execute("""SELECT line_number, sura_number, ayah_number,
                      MIN(min_x), MAX(max_x) FROM glyphs WHERE page_number=?
                      GROUP BY line_number, sura_number, ayah_number
                      ORDER BY line_number, MIN(position)""", (page,))
    lines = {}
    for (ln, s, a, x0, x1) in cur.fetchall():
        lines.setdefault(ln, []).append((s, a, x0, x1))
    con.close()
    return lines


def score(lines, bands, ink, keep, tol=5, verbose=False):
    hits = tot = 0
    detail = []
    for ln, segs in sorted(lines.items()):
        if not (0 < ln <= len(bands)):
            continue
        a, b = bands[ln - 1]
        prof = band_profile(ink, keep, a, b)
        if not prof:
            continue
        left, right, gaps = prof
        dbx0 = min(x0 for (_, _, x0, _) in segs)
        dbx1 = max(x1 for (_, _, _, x1) in segs)
        if dbx1 <= dbx0 or right <= left:
            continue
        s_ = (right - left) / float(dbx1 - dbx0)
        t_ = left - dbx0 * s_
        if len(segs) > 1:
            xs = sorted((x0, x1) for (_, _, x0, x1) in segs)
            for (x0a, x1a), (x0b, x1b) in zip(xs, xs[1:]):
                wx = ((x1a + x0b) / 2.0) * s_ + t_
                tot += 1
                ok = any(g[0] - tol <= wx <= g[1] + tol for g in gaps)
                hits += ok
                detail.append((ln, (x1a + x0b) / 2.0, wx, ok))
    if verbose:
        for d in detail:
            print("      line %2d  db_bound=%7.1f -> img_x=%7.1f  %s"
                  % (d[0], d[1], d[2], "HIT" if d[3] else "MISS"))
    return hits, tot


def run_page(page, verbose=False):
    gray = np.array(Image.open(os.path.join(
        PAGES_DIR, "page_%04d.webp" % page)).convert("L"))
    H, W = gray.shape
    ink = gray < 205
    (c0, c1), bands, naive_x = page_geometry(gray, 205)
    keep = np.arange(c0, c1 + 1)
    print("p%d: bands=%d naive_extent=%s" % (page, len(bands), naive_x))

    results = {}
    for label, path, wl in (("classic-1405", CLASSIC, True),
                            ("madani-1421", V1421, False)):
        lines = load_lines(path, page, wl)
        hits, tot = score(lines, bands, ink, keep, verbose=verbose)
        pct = 100.0 * hits / tot if tot else 0.0
        results[label] = pct
        print("  %-12s: %2d lines  boundaries on real gaps: %d/%d (%.0f%%)"
              % (label, len(lines), hits, tot, pct))
    return results


if __name__ == "__main__":
    args = [a for a in sys.argv[1:]]
    verbose = "-v" in args
    pages = [int(a) for a in args if a.isdigit()]
    if not pages:
        pages = [564]
    for pg in pages:
        run_page(pg, verbose=verbose)
        print()
