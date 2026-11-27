# -*- coding: utf-8 -*-
"""Render review overlays (marker ellipses + segment rects) for specific
mwdoa pages WITHOUT touching the full-run research JSON — the generator's
--overlays mode rewrites OUT_PATH with only the requested pages, which
would clobber the 604-page output. This runs build_page per page and keeps
only the overlay PNGs."""
import importlib.util
import os
import sqlite3
import sys

import numpy as np
import cv2
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GEN = os.path.join(ROOT, "scripts", "generate_ayah_bboxes_mwdoa.py")

spec = importlib.util.spec_from_file_location("genm", GEN)
genm = importlib.util.module_from_spec(spec)
sys.modules["genm"] = genm
spec.loader.exec_module(genm)

db = genm.ensure_db()
con = sqlite3.connect(db)

im = Image.open(os.path.join(
    genm.PAGES_DIR, "page_%04d.webp" % genm.CONFIRMED["page"])).convert("RGB")
gm = genm.gold_map(np.array(im))
pad = genm.CONFIRMED["pad"]
x, y, w, h = genm.CONFIRMED["x"], genm.CONFIRMED["y"], genm.CONFIRMED["w"], genm.CONFIRMED["h"]
tmpl = gm[max(0, y - pad):y + h + pad, max(0, x - pad):x + w + pad]
templates = []
for k in genm.TEMPLATE_SCALES:
    tk = cv2.resize(tmpl, None, fx=k, fy=k,
                    interpolation=cv2.INTER_AREA if k < 1.0 else cv2.INTER_LINEAR)
    templates.append((k, tk))

raw = sys.argv[1:]
pages = [int(p) for chunk in raw for p in chunk.split(",") if p.strip()]
for pg in pages:
    out, info = genm.build_page(con, pg, templates, emit_overlays=True)
    print("page %3d: markers=%s ending=%s%s%s%s" % (
        pg, info.get("markers"), info.get("ending_ayahs"),
        " MULTISCALE" if info.get("multiscale") else "",
        " GAPFILLED" if info.get("gap_filled") else "",
        " MISMATCH" if info.get("count_mismatch") else ""))
print("overlays in %s" % os.path.join(genm.CACHE_DIR, "overlays"))
