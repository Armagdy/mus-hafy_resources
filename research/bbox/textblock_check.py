# -*- coding: utf-8 -*-
"""Per-line text-block extraction (largest connected ink run between wide
gaps), then within-line alignment test vs the classic DB word boxes.
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
DB = os.path.join(ROOT, "temp", "bbox-research", "ayahinfo_classic_1260.db")


def text_block(ink, a, b, split_gap=15, lo=0.10):
    """Largest connected ink run in a band, splitting on gaps >= split_gap.

    Returns (left, right, gaps_inside) over the ORIGINAL column indices,
    where gaps_inside are the white gaps (>=3px) within the run.
    """
    band = ink[a:b]
    colsum = band.sum(axis=0)
    n = max(1, b - a)
    is_ink = colsum > lo * n
    runs, st = [], None
    for i, v in enumerate(is_ink):
        if v and st is None:
            st = i
        elif not v and st is not None:
            runs.append((st, i - 1))
            st = None
    if st is not None:
        runs.append((st, len(is_ink) - 1))
    # merge runs separated by < split_gap
    merged = []
    for r in runs:
        if merged and r[0] - merged[-1][1] - 1 < split_gap:
            merged[-1] = (merged[-1][0], r[1])
        else:
            merged.append(r)
    if not merged:
        return None
    best = max(merged, key=lambda r: r[1] - r[0])
    left, right = best
    inside = colsum[left:right + 1] == 0
    gaps, st = [], None
    for i, v in enumerate(inside):
        if v and st is None:
            st = i
        elif not v and st is not None:
            if i - st >= 3:
                gaps.append((left + st, left + i - 1))
            st = None
    return left, right, gaps


def analyze(page, verbose=False):
    gray = np.array(Image.open(os.path.join(
        PAGES_DIR, "page_%04d.webp" % page)).convert("L"))
    H, W = gray.shape
    ink = gray < 205
    (c0, c1), bands, naive = page_geometry(gray, 205)

    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.execute("""SELECT line_number, position, min_x, max_x
                   FROM glyphs WHERE page_number=?
                   ORDER BY line_number, position""", (page,))
    words = {}
    for (ln, pos, x0, x1) in cur.fetchall():
        words.setdefault(ln, []).append((x0, x1))
    con.close()

    tot = hit = 0
    best_dxs, ratios = [], []
    for ln, wx in sorted(words.items()):
        if not (0 < ln <= len(bands)) or len(wx) < 2:
            continue
        a, b = bands[ln - 1]
        tb = text_block(ink, a, b)
        if not tb:
            continue
        left, right, gaps = tb
        dbx0 = min(x for x, _ in wx)
        dbx1 = max(x1 for _, x1 in wx)
        if dbx1 <= dbx0 or right <= left:
            continue
        s_ = (right - left) / float(dbx1 - dbx0)
        t_ = left - dbx0 * s_
        xs = sorted(wx)
        if verbose:
            print("  line %2d text %4d..%4d  db %4d..%4d  s=%.4f t=%.1f"
                  % (ln, left, right, dbx0, dbx1, s_, t_))
        for (x0a, x1a), (x0b, x1b) in zip(xs, xs[1:]):
            wpos = ((x1a + x0b) / 2.0) * s_ + t_
            tot += 1
            if any(g[0] - 5 <= wpos <= g[1] + 5 for g in gaps):
                hit += 1
        # cross-correlation
        band = ink[a:b]
        colsum = band.sum(axis=0) / float(b - a)
        xs_img = np.arange(left, right + 1)
        db_at = (xs_img - t_) / s_
        p = np.zeros(len(db_at), bool)
        for (x0, x1) in wx:
            p = p | ((db_at >= x0) & (db_at <= x1))
        cors = {}
        for dx in range(-40, 41):
            l2, r2 = left + dx, right + dx
            if l2 < 0 or r2 >= W:
                continue
            mm = (colsum[l2:r2 + 1] > 0.06).astype(float)
            if mm.std() < 1e-9:
                continue
            cc = np.corrcoef(p.astype(float), mm)[0, 1]
            if not np.isnan(cc):
                cors[dx] = cc
        if 0 in cors and len(cors) >= 20:
            bdx = max(cors, key=cors.get)
            best_dxs.append(bdx)
            ratios.append(cors[0] / max(1e-9, cors[bdx]))
    print("p%d: word-gap hits %d/%d (%.0f%%)"
          % (page, hit, tot, 100.0 * hit / tot if tot else 0))
    if best_dxs:
        best_dxs = np.array(best_dxs)
        print("     xcorr: best-dx median=%+.1f (p10 %+.0f, p90 %+.0f)"
              "  corr(0)/corr(best) median=%.3f"
              % (np.median(best_dxs), np.percentile(best_dxs, 10),
                 np.percentile(best_dxs, 90), np.median(ratios)))


if __name__ == "__main__":
    args = sys.argv[1:]
    verbose = "-v" in args
    for pg in [int(a) for a in args if a.isdigit()] or [564]:
        analyze(pg, verbose)
