# -*- coding: utf-8 -*-
"""Identify the band after each tall surah header: basmalah (full-width,
classic structure) or first-ayah line (1421 structure, ~54% centered)?

Uses CLEAN text blocks (band_text_block + strip mask) and clean profile
correlation between pages.
"""
import json
import os
import sys

import numpy as np
from PIL import Image

ROOT = r"D:\apps\quran\mushafy"
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from generate_ayah_bboxes import page_geometry, band_text_block  # noqa: E402

PAGES_DIR = os.path.join(ROOT, "public", "assets", "mushaf_madinah_images")
META = os.path.join(ROOT, "public", "assets", "quran-meta-data.json")


def band_profile(gray, ink, strip, a, b, n=100):
    tb = band_text_block(ink, a, b, exclude=strip)
    if not tb:
        return None, None
    il, ir = tb
    band = ink[a:b]
    colsum = band.sum(axis=0) / float(b - a)
    v = colsum[il:ir + 1]
    if len(v) < 40:
        return None, tb
    xs = np.linspace(0, len(v) - 1, n)
    prof = np.interp(xs, np.arange(len(v)), v)
    m = prof.max()
    return (prof / m if m > 0 else None), tb


meta = json.load(open(META, encoding="utf-8"))
starts = [i + 1 for i, p in enumerate(meta["pages"]) if p[1] == 1 and i + 1 >= 3]

profs = {}
widths = {}
positions = {}
for pg in starts:
    gray = np.array(Image.open(os.path.join(
        PAGES_DIR, "page_%04d.webp" % pg)).convert("L"))
    ink = gray < 205
    (c0, c1), bands, _, strip = page_geometry(gray, 205)
    if len(bands) < 4:
        continue
    heights = [b[1] - b[0] for b in bands]
    med = float(np.median(heights))
    if heights[0] < 1.25 * med:      # page must start with the header band
        continue
    prof, tb = band_profile(gray, ink, strip, bands[1][0], bands[1][1])
    if prof is None:
        continue
    profs[pg] = prof
    widths[pg] = tb[1] - tb[0]
    positions[pg] = tb

pgs = sorted(profs)
print("surah-start pages (header-first): %d" % len(pgs))
ws = np.array([widths[p] for p in pgs])
page_w = 1090
print("band-after-header text-block width: median=%d (%.0f%% of page)"
      "  min=%d max=%d  std=%.1f"
      % (np.median(ws), 100 * np.median(ws) / page_w, ws.min(), ws.max(),
         ws.std()))
ls = np.array([positions[p][0] for p in pgs])
rs = np.array([positions[p][1] for p in pgs])
print("  left: median=%d  right: median=%d  (text block is ~130..962 if"
      " full-width, ~250..710 if centered 54%%)" % (np.median(ls), np.median(rs)))

sims = []
for i in range(len(pgs)):
    for j in range(i + 1, len(pgs)):
        sims.append(float(np.corrcoef(profs[pgs[i]], profs[pgs[j]])[0, 1]))
sims = np.array(sims)
print("clean profile correlation between pages: median=%.3f p10=%.3f p90=%.3f"
      % (np.median(sims), np.percentile(sims, 10), np.percentile(sims, 90)))

# also: the p564 band 7 (mid-page surah start)
gray = np.array(Image.open(os.path.join(PAGES_DIR, "page_0564.webp")).convert("L"))
ink = gray < 205
(c0, c1), bands, _, strip = page_geometry(gray, 205)
prof, tb = band_profile(gray, ink, strip, bands[6][0], bands[6][1])
cors = sorted(((float(np.corrcoef(prof, profs[p])[0, 1]), p) for p in pgs),
              reverse=True)
print("\np564 band 7: text block %s (width %d, %.0f%% of page)"
      % (tb, tb[1] - tb[0], 100.0 * (tb[1] - tb[0]) / page_w))
print("  vs the 30 surah-start band-2 profiles: median corr=%.3f"
      % np.median([c for c, _ in cors]))

print("\nVERDICT:")
if np.median(ws) > 0.75 * page_w:
    print("  full-width => BASMALAH lines => classic 15-slot structure"
          " (13 text bands on p564)")
elif np.median(ws) < 0.65 * page_w:
    print("  ~54%% centered => FIRST-AYAH lines => 1421 structure"
          " (14 text bands on p564)")
else:
    print("  ambiguous - inspect widths list above")
