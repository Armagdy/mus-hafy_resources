# -*- coding: utf-8 -*-
"""Basmalah fingerprint test — needs no DB.

Classic 1405H: every surah start prints a separate basmalah line; its ink
profile is the SAME on every surah-start page.
1421H: basmalahs share the header line, so the band after the header holds
the surah's FIRST AYAH — different text every page.

So: take the band right after the tall surah-header band on many
surah-start pages and cross-correlate their column ink profiles.
High pairwise similarity  => classic layout.
Wildly different profiles  => 1421 layout.
"""
import json
import os
import sys

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from generate_ayah_bboxes import page_geometry  # noqa: E402

PAGES_DIR = os.path.join(ROOT, "public", "assets", "mushaf_madinah_images")
META = os.path.join(ROOT, "public", "assets", "quran-meta-data.json")


def band_profile_vec(ink, keep, a, b, n=120):
    """Column ink density of one band, resampled to n values, and its
    extent (left, right)."""
    band = ink[a:b]
    colsum = band.sum(axis=0) / max(1, b - a)
    n_rows = b - a
    # exclude full-height vertical lines (frame remnants): colsum ~ 1.0
    ok = (colsum > 0.05) & (colsum < 0.9) & \
         (np.arange(len(colsum)) >= keep[0]) & (np.arange(len(colsum)) <= keep[-1])
    idx = np.where(ok)[0]
    if not len(idx):
        return None, None
    left, right = int(idx.min()), int(idx.max())
    v = colsum[left:right + 1]
    if len(v) < 10:
        return None, None
    xs = np.linspace(0, len(v) - 1, n)
    prof = np.interp(xs, np.arange(len(v)), v)
    prof = prof / max(1e-9, prof.max())
    return prof, (left, right)


def find_header_gap_bands(bands):
    """For a page whose surah starts at top: band1=header, band2=?
    returns (band2_range, band3_range)"""
    if len(bands) < 4:
        return None, None
    return bands[1], bands[2]


def main():
    meta = json.load(open(META, encoding="utf-8"))
    pages = meta["pages"]

    # surah-start pages where the surah starts the page (first ayah = 1)
    starts = [i + 1 for i, p in enumerate(pages) if p[1] == 1]
    print("surah-start pages: %d" % len(starts))

    profiles = {}
    widths = {}
    for pg in starts:
        if pg < 3:  # skip ornamental front-matter (user said ignore p1-2)
            continue
        path = os.path.join(PAGES_DIR, "page_%04d.webp" % pg)
        if not os.path.exists(path):
            continue
        gray = np.array(Image.open(path).convert("L"))
        ink = gray < 205
        (c0, c1), bands, _ = page_geometry(gray, 205)
        keep = np.arange(c0, c1 + 1)
        b2, b3 = find_header_gap_bands(bands)
        if b2 is None:
            continue
        prof, ext = band_profile_vec(ink, keep, b2[0], b2[1])
        if prof is None:
            continue
        profiles[pg] = prof
        widths[pg] = ext[1] - ext[0]

    pgs = sorted(profiles)
    print("profiled %d pages" % len(pgs))

    # pairwise correlation
    sims = []
    for i in range(len(pgs)):
        for j in range(i + 1, len(pgs)):
            a, b = profiles[pgs[i]], profiles[pgs[j]]
            if len(a) == len(b):
                c = float(np.corrcoef(a, b)[0, 1])
                sims.append(c)
    sims = np.array(sims)
    print("pairwise profile correlation after header band:")
    print("  median=%.3f  mean=%.3f  min=%.3f  p10=%.3f  p90=%.3f"
          % (np.median(sims), sims.mean(), sims.min(),
             np.percentile(sims, 10), np.percentile(sims, 90)))

    # width consistency
    ws = np.array([widths[p] for p in pgs])
    print("band-after-header widths: median=%.0f  std=%.0f  min=%d max=%d"
          % (np.median(ws), ws.std(), ws.min(), ws.max()))

    # interpretation
    med = float(np.median(sims))
    if med > 0.8 and ws.std() < 0.15 * np.median(ws):
        print("\n=> IDENTICAL profiles: these bands are BASMALAH lines"
              " => the local print follows the CLASSIC 1405H layout.")
    elif med < 0.5:
        print("\n=> DIFFERENT profiles: these bands hold each surah's first"
              " ayah => the local print follows the 1421H layout.")
    else:
        print("\n=> ambiguous, inspect individual pairs below")

    # show a few individual pairs
    print("\nexamples:")
    for i in range(min(6, len(pgs) - 1)):
        a, b = profiles[pgs[i]], profiles[pgs[i + 1]]
        c = float(np.corrcoef(a, b)[0, 1])
        print("  p%d vs p%d: corr=%.3f  widths %d/%d"
              % (pgs[i], pgs[i + 1], c, widths[pgs[i]], widths[pgs[i + 1]]))


if __name__ == "__main__":
    main()
