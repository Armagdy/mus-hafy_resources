# -*- coding: utf-8 -*-
"""Extract candidate marker blobs around predicted ayah boundaries.

Around each predicted internal boundary (DB-mapped, +-50px), find compact
ink runs in the band, isolated by gaps on both sides. The true ۝ marker
should appear as a consistent size/shape cluster across hundreds of
windows; word fragments vary.
"""
import json
import os
import sqlite3
import sys

import numpy as np
from PIL import Image

ROOT = r"D:\apps\quran\mushafy"
sys.path.insert(0, r"D:\apps\quran\mushafy\scripts")
from generate_ayah_bboxes import page_geometry, db_page, ensure_db  # noqa: E402

PAGES_DIR = os.path.join(ROOT, "public", "assets", "mushaf_madinah_images")
con = sqlite3.connect(ensure_db(os.path.join(ROOT, "temp", "bbox-research")))

res = json.load(open(os.path.join(ROOT, "temp", "bbox-research",
                                  "madinah_ayah_bboxes.json"), encoding="utf-8"))
by_page = {p["page"]: p for p in res["pages"]}


def band_runs(ink, a, b, exclude=None, lo=0.08, gap=4):
    """ink runs (columns with >= lo of band rows inked, split on >= gap)."""
    band = ink[a:b]
    colsum = band.sum(axis=0)
    n = max(1, b - a)
    is_ink = colsum > lo * n
    if exclude is not None:
        is_ink = is_ink & ~exclude
    runs, st = [], None
    for i, v in enumerate(is_ink):
        if v and st is None:
            st = i
        elif not v and st is not None:
            if i - st >= 2 and (st == 0 or i - st >= 2):
                runs.append((st, i - 1))
            st = None
    if st is not None:
        runs.append((st, len(is_ink) - 1))
    # merge runs separated by < gap
    merged = []
    for r in runs:
        if merged and r[0] - merged[-1][1] - 1 < gap:
            merged[-1] = (merged[-1][0], r[1])
        else:
            merged.append(r)
    return merged


def candidates_for_page(pg, win=50):
    p = by_page[pg]
    tr = p["transform"]
    sx, tx = tr["sx"], tr["tx"]
    gray = np.array(Image.open(os.path.join(
        PAGES_DIR, "page_%04d.webp" % pg)).convert("L"))
    ink = gray < 205
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
        band = ink[a:b]
        n = b - a
        segs = sorted(segs)
        for (x0a, x1a), (x0b, x1b) in zip(segs, segs[1:]):
            wx = ((x1a + x0b) / 2.0) * sx + tx
            lo_i, hi_i = int(max(0, wx - win)), int(min(gray.shape[1], wx + win))
            colsum = band[:, lo_i:hi_i].sum(axis=0)
            is_ink = colsum > 0.08 * n
            # runs in the window with gaps >= 4
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
            for (r0, r1) in merged:
                w = r1 - r0 + 1
                if not (16 <= w <= 60):
                    continue
                # blob vertical stats
                cols = band[:, lo_i + r0:lo_i + r1 + 1]
                rows_ink = np.where(cols.any(axis=1))[0]
                if len(rows_ink) == 0:
                    continue
                h = rows_ink[-1] - rows_ink[0] + 1
                fill = cols.mean()
                # internal whitespace (the number inside the rosette)
                row_any = cols.any(axis=1)
                has_hole = False
                in_hole = False
                for v in row_any[rows_ink[0]:rows_ink[-1] + 1]:
                    if not v:
                        in_hole = True
                    elif in_hole:
                        has_hole = True
                        in_hole = False
                out.append(dict(page=pg, ln=ln, x=int(lo_i + r0),
                                w=int(w), h=int(h), fill=round(float(fill), 2),
                                hole=has_hole,
                                d_from_pred=round(float(lo_i + r0 + w / 2 - wx), 1)))
    return out


allc = []
for pg in [564, 300, 50, 106, 400, 200, 500]:
    allc.extend(candidates_for_page(pg))

print("candidates: %d from 7 pages" % len(allc))
hole = [c for c in allc if c["hole"]]
word = [c for c in allc if not c["hole"]]
print("hole blobs: %d   non-hole: %d" % (len(hole), len(word)))
for name, grp in (("HOLE", hole), ("WORD", word)):
    if not grp:
        continue
    d = np.array([c["d_from_pred"] for c in grp])
    w = np.array([c["w"] for c in grp])
    h = np.array([c["h"] for c in grp])
    f = np.array([c["fill"] for c in grp])
    print("\n%s: n=%d" % (name, len(grp)))
    print("  d: median=%+.0f p25=%+.0f p75=%+.0f" % (np.median(d),
          np.percentile(d, 25), np.percentile(d, 75)))
    print("  w: median=%d   h: median=%d   fill: median=%.2f"
          % (np.median(w), np.median(h), np.median(f)))
    hist = {}
    for v in d:
        hist[int(v) // 10 * 10] = hist.get(int(v) // 10 * 10, 0) + 1
    for k in sorted(hist):
        print("    d %+4d..: %s (%d)" % (k, "#" * hist[k], hist[k]))

print("\nfirst 12 hole blobs:")
for c in hole[:12]:
    print("   p%d ln%d x=%d w=%d h=%d fill=%.2f d=%+.1f"
          % (c["page"], c["ln"], c["x"], c["w"], c["h"], c["fill"],
             c["d_from_pred"]))
con.close()

