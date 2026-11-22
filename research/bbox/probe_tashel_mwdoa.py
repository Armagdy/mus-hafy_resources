# -*- coding: utf-8 -*-
"""
Probe: do tashel / mwdoa follow the classic Madani 15-line layout
line-for-line (like the madinah set does)?

For a sample of pages: try several binarization thresholds, pick the one whose
detected band count best matches the classic DB's line count, then run the
same index-pairing line fit used for madinah and report residuals.

Small residuals (like madinah's 4-8 px) => same layout => the same pipeline
can generate their ayah boxes directly from the classic DB.
"""
import importlib.util
import os
import sqlite3
import sys

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
spec = importlib.util.spec_from_file_location(
    "gen", os.path.join(ROOT, "scripts", "generate_ayah_bboxes.py"))
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)

SETS = [
    ("tashel", os.path.join(ROOT, "public", "assets", "mushaf_tashel_pages")),
    ("mwdoa", os.path.join(ROOT, "public", "assets", "mushuf_mwdoa_images")),
]
PAGES = [2, 3, 50, 106, 300, 551, 604]
THRESHOLDS = [140, 160, 180, 200, 205, 220]


def probe(mushaf, folder):
    db = gen.ensure_db()
    con = sqlite3.connect(db)
    print("\n" + "=" * 70)
    print("%s  (%s)" % (mushaf, os.path.basename(folder)))
    print("=" * 70)
    for pg in PAGES:
        path = os.path.join(folder, "page_%04d.webp" % pg)
        if not os.path.exists(path):
            print("page %3d: MISSING image" % pg)
            continue
        gray = np.array(Image.open(path).convert("L"))
        H, W = gray.shape
        db_lines, groups, extent, first = gen.db_page(con, pg)
        max_line = max(l[0] for l in db_lines) if db_lines else 0

        best = None
        for th in THRESHOLDS:
            try:
                interior, bands, xext = gen.page_geometry(gray, thresh=th)
            except Exception as e:
                continue
            if not db_lines:
                continue
            score = abs(len(bands) - max_line)
            if best is None or score < best[0]:
                best = (score, th, bands, xext)
        if not db_lines or best is None:
            print("page %3d: no db lines" % pg)
            continue
        _, th, bands, xext = best
        sx, sy, tx, ty, info = gen.fit_page(
            db_lines, groups, extent, bands, xext, H, W)
        print("page %3d: mean=%3.0f db_lines=%2d/%2d th=%3d bands=%2d "
              "fit=%-12s resid=%s flags=%s"
              % (pg, float(gray.mean()), len(db_lines), max_line, th,
                 len(bands), info.get("fit"),
                 info.get("max_line_residual_px"), ",".join(info.get("flags", []))))


for m, f in SETS:
    probe(m, f)
