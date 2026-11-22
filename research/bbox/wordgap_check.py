# -*- coding: utf-8 -*-
"""Per-line word-gap alignment check with CLEAN extents.

Maps each classic DB line onto its image band (extent-to-extent affine,
using uncontaminated extents), then counts how many DB word boundaries
land on real white gaps in the image. High hit-rate => the local print's
within-line justification matches the classic DB => per-ayah boxes will
be accurate once the page fit is fixed.
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


def clean_extent(ink, keep, a, b, lo=0.10, hi=0.90):
    band = ink[a:b]
    colsum = band.sum(axis=0)
    n = b - a
    ok = ((colsum > lo * n) & (colsum < hi * n) &
          (np.arange(len(colsum)) >= keep[0]) &
          (np.arange(len(colsum)) <= keep[-1]))
    idx = np.where(ok)[0]
    if not len(idx):
        return None
    left, right = int(idx.min()), int(idx.max())
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


def main():
    pages = [int(x) for x in sys.argv[1:]] or [564]
    con = sqlite3.connect(DB)
    for page in pages:
        gray = np.array(Image.open(os.path.join(
            PAGES_DIR, "page_%04d.webp" % page)).convert("L"))
        H, W = gray.shape
        ink = gray < 205
        (c0, c1), bands, naive = page_geometry(gray, 205)
        keep = np.arange(c0, c1 + 1)
        print("p%d: naive_extent=%s" % (page, naive))

        cur = con.cursor()
        cur.execute("""SELECT line_number, position, min_x, max_x
                       FROM glyphs WHERE page_number=?
                       ORDER BY line_number, position""", (page,))
        words = {}
        for (ln, pos, x0, x1) in cur.fetchall():
            words.setdefault(ln, []).append((x0, x1))

        tot = hit = 0
        for ln, wx in sorted(words.items()):
            if not (0 < ln <= len(bands)):
                continue
            a, b = bands[ln - 1]
            ext = clean_extent(ink, keep, a, b)
            if not ext:
                continue
            left, right, gaps = ext
            dbx0 = min(x0 for x0, _ in wx)
            dbx1 = max(x1 for _, x1 in wx)
            if dbx1 <= dbx0 or right <= left:
                continue
            s_ = (right - left) / float(dbx1 - dbx0)
            t_ = left - dbx0 * s_
            xs = sorted(wx)
            for (x0a, x1a), (x0b, x1b) in zip(xs, xs[1:]):
                wpos = ((x1a + x0b) / 2.0) * s_ + t_
                tot += 1
                if any(g[0] - 4 <= wpos <= g[1] + 4 for g in gaps):
                    hit += 1
        print("  word boundaries on real gaps: %d/%d (%.0f%%)"
              % (hit, tot, 100.0 * hit / tot if tot else 0))
    con.close()


if __name__ == "__main__":
    main()
