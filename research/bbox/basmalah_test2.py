# -*- coding: utf-8 -*-
"""Basmalah fingerprint, take 2.

Only pages whose FIRST band is the tall surah header (surah starts the
page). Candidate basmalah = the band right after it. Profile = column ink
density restricted to the ink extent (not the edge ornaments). If those
profiles match across pages (and match p564's band 7), the print has
separate basmalah lines => CLASSIC 1405H layout.
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


def band_prof(ink, a, b, n=140):
    band = ink[a:b]
    colsum = band.sum(axis=0) / max(1, b - a)
    ok = (colsum > 0.10) & (colsum < 0.92)
    idx = np.where(ok)[0]
    if len(idx) < 30:
        return None
    left, right = int(idx.min()), int(idx.max())
    # keep a small inward margin to drop rosettes/ornaments hugging the edge
    v = colsum[left + 6:right - 5]
    if len(v) < 40:
        return None
    xs = np.linspace(0, len(v) - 1, n)
    prof = np.interp(xs, np.arange(len(v)), v)
    m = prof.max()
    return prof / m if m > 0 else None, right - left


def get_bands(pg):
    path = os.path.join(PAGES_DIR, "page_%04d.webp" % pg)
    gray = np.array(Image.open(path).convert("L"))
    ink = gray < 205
    (c0, c1), bands, _ = page_geometry(gray, 205)
    return ink, bands


def main():
    meta = json.load(open(META, encoding="utf-8"))
    pages = meta["pages"]
    starts = [i + 1 for i, p in enumerate(pages) if p[1] == 1 and i + 1 >= 3]

    profs, widths = {}, {}
    for pg in starts:
        ink, bands = get_bands(pg)
        if len(bands) < 4:
            continue
        heights = [b[1] - b[0] for b in bands]
        med = float(np.median(heights))
        # page must START with the tall header band
        if heights[0] < 1.25 * med:
            continue
        a, b = bands[1]  # band right after the header = candidate basmalah
        res = band_prof(ink, a, b)
        if res[0] is None:
            continue
        profs[pg], widths[pg] = res

    pgs = sorted(profs)
    print("surah-start pages with header-first: %d profiled" % len(pgs))
    sims = []
    for i in range(len(pgs)):
        for j in range(i + 1, len(pgs)):
            sims.append(float(np.corrcoef(profs[pgs[i]], profs[pgs[j]])[0, 1]))
    sims = np.array(sims)
    ws = np.array([widths[p] for p in pgs])
    print("basmalah-band ink widths: median=%.0f std=%.0f" % (np.median(ws), ws.std()))
    print("pairwise corr: median=%.3f p10=%.3f p90=%.3f min=%.3f"
          % (np.median(sims), np.percentile(sims, 10),
             np.percentile(sims, 90), sims.min()))

    # now the money test: p564 band 7 vs these basmalah profiles
    ink564, bands564 = get_bands(564)
    heights = [b[1] - b[0] for b in bands564]
    med = float(np.median(heights))
    print("\np564 band heights:", [h for h in heights], "median=%.0f" % med)
    res, w = band_prof(ink564, bands564[6][0], bands564[6][1])
    print("p564 band 7 ink width=%s" % w)
    if res is not None:
        cors = sorted(((float(np.corrcoef(res, profs[p])[0, 1]), p)
                       for p in pgs), reverse=True)
        top = cors[:8]
        print("p564 band7 vs basmalah profiles, top matches:")
        for c, p in top:
            print("   vs p%d: corr=%.3f (band width %d)" % (p, c, widths[p]))
        med_c = np.median([c for c, _ in cors])
        print("   median corr over all %d basmalah pages: %.3f"
              % (len(cors), med_c))

    print("\nverdict:")
    if len(sims) and np.median(sims) > 0.85:
        print("  surah-start pages share ONE identical band => separate"
              " basmalah lines => CLASSIC 1405H layout")
    else:
        print("  bands after headers differ => 1421-style layout?")


if __name__ == "__main__":
    main()
