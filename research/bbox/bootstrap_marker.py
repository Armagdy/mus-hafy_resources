# -*- coding: utf-8 -*-
"""Bootstrap the madinah end-of-ayah marker template.

1. Collect candidate blob crops from predicted-boundary windows.
2. Cross-validate: the true marker template matches the OTHER windows'
   peaks far better than any word-fragment crop.
3. Save the best crop as the template + report full-page detection counts
   on validation pages (expected = ayahs ending on the page).
"""
import json
import os
import sqlite3
import sys

import cv2
import numpy as np
from PIL import Image

ROOT = r"D:\apps\quran\mushafy"
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from generate_ayah_bboxes import page_geometry, db_page, ensure_db  # noqa: E402

PAGES_DIR = os.path.join(ROOT, "public", "assets", "mushaf_madinah_images")
con = sqlite3.connect(ensure_db(os.path.join(ROOT, "temp", "bbox-research")))

res = json.load(open(os.path.join(ROOT, "temp", "bbox-research",
                                  "madinah_ayah_bboxes.json"), encoding="utf-8"))
by_page = {p["page"]: p for p in res["pages"]}

WIN = 55
PAD = 6


def page_windows(pg):
    """(strip, wx, band, page) for every internal ayah boundary."""
    p = by_page[pg]
    tr = p["transform"]
    sx, tx = tr["sx"], tr["tx"]
    gray = np.array(Image.open(os.path.join(
        PAGES_DIR, "page_%04d.webp" % pg)).convert("L"))
    ink = (gray < 205).astype(np.uint8) * 255
    (c0, c1), bands, _, strip = page_geometry(gray, 205)
    db_lines, groups, db_extent, first = db_page(con, pg)
    per_line = {}
    for (ln, s, ay, x0, y0, x1, y1) in groups:
        per_line.setdefault(ln, []).append((x0, x1))
    out = []
    for ln, segs in per_line.items():
        if len(segs) < 2 or not (0 < ln <= len(bands)):
            continue
        a, b = bands[ln - 1]
        segs = sorted(segs)
        for (x0a, x1a), (x0b, x1b) in zip(segs, segs[1:]):
            wx = ((x1a + x0b) / 2.0) * sx + tx
            lo_i = int(max(0, wx - WIN))
            hi_i = int(min(gray.shape[1], wx + WIN))
            if hi_i - lo_i < 40:
                continue
            out.append((ink[a:b, lo_i:hi_i], wx, (a, b), lo_i, pg, ln))
    return out


def runs_in(strip_img, lo_n):
    colsum = strip_img.sum(axis=0) / 255.0
    is_ink = colsum > 0.08 * strip_img.shape[0]
    runs, st = [], None
    for i, v in enumerate(is_ink):
        if v and st is None:
            st = i
        elif not v and st is not None:
            runs.append((st, i - 1))
            st = None
    if st is not None:
        runs.append((st, len(is_ink) - 1))
    merged = []
    for r in runs:
        if merged and r[0] - merged[-1][1] - 1 < 4:
            merged[-1] = (merged[-1][0], r[1])
        else:
            merged.append(r)
    return [(r0, r1) for (r0, r1) in merged if 16 <= r1 - r0 + 1 <= 60]


def crop_candidate(strip_img, r0, r1):
    cols = strip_img[:, r0:r1 + 1]
    rows = np.where(cols.any(axis=1))[0]
    y0, y1 = rows[0], rows[-1]
    y0 = max(0, y0 - PAD)
    y1 = min(strip_img.shape[0] - 1, y1 + PAD)
    x0 = max(0, r0 - PAD)
    x1 = min(strip_img.shape[1] - 1, r1 + PAD)
    return strip_img[y0:y1 + 1, x0:x1 + 1]


# ---- gather windows + candidates across sample pages ----
windows = []
for pg in [564, 300, 50, 106, 400, 200, 500, 250, 456, 555]:
    windows.extend(page_windows(pg))
print("windows: %d" % len(windows))

cands = []  # (crop, window_idx)
for wi, (strip_img, wx, band, lo_i, pg, ln) in enumerate(windows):
    for (r0, r1) in runs_in(strip_img, band[1] - band[0]):
        cands.append((crop_candidate(strip_img, r0, r1), wi, lo_i + (r0 + r1) / 2.0))
print("candidates: %d" % len(cands))
if not cands:
    sys.exit(1)

# ---- cross-validate candidates ----
# score(crop) = # other windows whose best match >= 0.78
def cross_score(idx):
    crop = cands[idx][0]
    if crop.shape[0] < 20 or crop.shape[1] < 20:
        return 0
    hits = 0
    for wj, (strip_img, wx, band, lo_i, pg, ln) in enumerate(windows):
        if wj == cands[idx][1]:
            continue
        if strip_img.shape[0] < crop.shape[0] or strip_img.shape[1] < crop.shape[1]:
            continue
        r = cv2.matchTemplate(strip_img, crop, cv2.TM_CCOEFF_NORMED)
        if r.max() >= 0.78:
            hits += 1
    return hits


scores = []
for i in range(len(cands)):
    s = cross_score(i)
    scores.append(s)
    if s > len(windows) * 0.5:
        print("  strong candidate #%d: hits=%d/%d shape=%s"
              % (i, s, len(windows) - 1, cands[i][0].shape))

best = int(np.argmax(scores))
print("\nBEST candidate #%d: cross-hits %d/%d  shape=%s  at page-window %s"
      % (best, scores[best], len(windows) - 1, cands[best][0].shape,
          cands[best][1]))
tmpl = cands[best][0]
out_path = os.path.join(ROOT, "temp", "bbox-research", "madinah_marker_tmpl.png")
Image.fromarray(tmpl).save(out_path)
print("saved %s" % out_path)

# ---- validate: full-page detection on p564 vs expected count ----
def expected_ends(pg):
    cur = con.cursor()
    cur.execute("SELECT DISTINCT sura_number, ayah_number FROM glyphs WHERE page_number=?",
                (pg + 1,))
    nxt = set(cur.fetchall())
    cur.execute("SELECT DISTINCT sura_number, ayah_number FROM glyphs WHERE page_number=?",
                (pg,))
    here = [tuple(r) for r in cur.fetchall()]
    return [k for k in here if k not in nxt]

def detect_page(pg, tmpl, th=0.70):
    gray = np.array(Image.open(os.path.join(
        PAGES_DIR, "page_%04d.webp" % pg)).convert("L"))
    ink = (gray < 205).astype(np.uint8) * 255
    r = cv2.matchTemplate(ink, tmpl, cv2.TM_CCOEFF_NORMED)
    loc = np.where(r >= th)
    pts = sorted(zip(loc[1], loc[0], r[loc[0], loc[1]]), key=lambda p: -p[2])
    kept = []
    for (x, y, s) in pts:
        if all(abs(x - kx) > 25 or abs(y - ky) > 25 for (kx, ky, _) in kept):
            kept.append((int(x), int(y), float(s)))
    return kept

for pg in [564, 300, 50]:
    exp = expected_ends(pg)
    det = detect_page(pg, tmpl)
    print("p%d: expected ends=%d  detected=%d" % (pg, len(exp), len(det)))
con.close()
