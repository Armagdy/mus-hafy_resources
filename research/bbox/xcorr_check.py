# -*- coding: utf-8 -*-
"""Within-line alignment: cross-correlate the DB's predicted ink profile
(word boxes) with the image's measured ink profile per line.

If the local print's justification matches the classic DB, the best
per-line shift dx should cluster around 0 and corr(0) ~= corr(best).
"""
import os
import sqlite3
import sys

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from generate_ayah_bboxes import page_geometry  # noqa: E402
from wordgap_check import clean_extent  # noqa: E402

PAGES_DIR = os.path.join(ROOT, "public", "assets", "mushaf_madinah_images")
DB = os.path.join(ROOT, "temp", "bbox-research", "ayahinfo_classic_1260.db")


def main():
    pages = [int(x) for x in sys.argv[1:]] or [564]
    con = sqlite3.connect(DB)
    for page in pages:
        gray = np.array(Image.open(os.path.join(
            PAGES_DIR, "page_%04d.webp" % page)).convert("L"))
        H, W = gray.shape
        ink = gray < 205
        (c0, c1), bands, _ = page_geometry(gray, 205)
        keep = np.arange(c0, c1 + 1)

        cur = con.cursor()
        cur.execute("""SELECT line_number, position, min_x, max_x
                       FROM glyphs WHERE page_number=?
                       ORDER BY line_number, position""", (page,))
        words = {}
        for (ln, pos, x0, x1) in cur.fetchall():
            words.setdefault(ln, []).append((x0, x1))

        best_dxs, ratios = [], []
        for ln, wx in sorted(words.items()):
            if not (0 < ln <= len(bands)) or len(wx) < 3:
                continue
            a, b = bands[ln - 1]
            ext = clean_extent(ink, keep, a, b)
            if not ext:
                continue
            left, right, _ = ext
            dbx0 = min(x for x, _ in wx)
            dbx1 = max(x1 for _, x1 in wx)
            if dbx1 <= dbx0 or right <= left:
                continue
            s_ = (right - left) / float(dbx1 - dbx0)
            t_ = left - dbx0 * s_
            # measured ink profile over the line
            band = ink[a:b]
            colsum = band.sum(axis=0) / float(b - a)
            xs_img = np.arange(left, right + 1)
            m = (colsum[left:right + 1] > 0.06).astype(float)
            # predicted profile sampled at image xs
            db_at = (xs_img - t_) / s_
            p = np.zeros(len(db_at), bool)
            for (x0, x1) in wx:
                p = p | ((db_at >= x0) & (db_at <= x1))
            # scan shifts
            span = 40
            cors = {}
            for dx in range(-span, span + 1):
                if 0 <= left + dx and right + dx < W:
                    mm = (colsum[left + dx:right + 1 + dx] > 0.06).astype(float)
                    cc = np.corrcoef(p, mm)[0, 1]
                    if not np.isnan(cc):
                        cors[dx] = cc
            if 0 not in cors or len(cors) < 20:
                continue
            best_dx = max(cors, key=cors.get)
            best_dxs.append(best_dx)
            ratios.append(cors[0] / max(1e-9, cors[best_dx]))
        best_dxs = np.array(best_dxs)
        ratios = np.array(ratios)
        print("p%d: lines=%d  best-dx median=%+.1f px (p10 %+.0f, p90 %+.0f)"
              "  corr(0)/corr(best) median=%.3f"
              % (page, len(best_dxs), np.median(best_dxs),
                 np.percentile(best_dxs, 10), np.percentile(best_dxs, 90),
                 np.median(ratios)))
    con.close()


if __name__ == "__main__":
    main()
