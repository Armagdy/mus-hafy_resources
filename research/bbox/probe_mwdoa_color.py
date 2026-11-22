# -*- coding: utf-8 -*-
"""
mwdoa retry: binarize by COLOR distance from the paper background (the
thematic mushaf's colored text collapses to mid-gray in luminance, breaking
gray thresholds). Then rerun the classic-DB line-center fit probe.

If residuals drop to madinah/tashel levels (~4-8 px), mwdoa follows the
standard layout too and the SAME pipeline covers all three mushafs.
"""
import importlib.util
import os
import sqlite3

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
spec = importlib.util.spec_from_file_location(
    "gen", os.path.join(ROOT, "scripts", "generate_ayah_bboxes.py"))
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)

PAGES_DIR = os.path.join(ROOT, "public", "assets", "mushuf_mwdoa_images")
PAGES = [2, 3, 50, 106, 300, 551, 604]


def color_mask(a, frac=0.95):
    """Ink mask = pixels far (Euclidean, RGB) from the dominant background."""
    H, W, _ = a.shape
    small = a[::8, ::8].reshape(-1, 3).astype(np.int32)
    # background = median color of the brightest 20% of pixels (paper)
    lum = small.sum(axis=1)
    top = small[np.argsort(lum)[-max(1, len(sum([])) if False else int(len(small) * 0.2))]]
    bg = np.median(top, axis=0)
    dist = np.sqrt(((a.astype(np.int32) - bg) ** 2).sum(axis=2))
    return dist, bg


def probe():
    db = gen.ensure_db()
    con = sqlite3.connect(db)
    print("mwdoa with COLOR-distance masking:")
    for pg in PAGES:
        a = np.array(Image.open(os.path.join(
            PAGES_DIR, "page_%04d.webp" % pg)).convert("RGB"))
        H, W, _ = a.shape
        dist, bg = color_mask(a)
        db_lines, groups, extent, first = gen.db_page(con, pg)
        if not db_lines:
            print("page %3d: no db lines" % pg)
            continue
        max_line = max(l[0] for l in db_lines)

        best = None
        for th in (28, 34, 40, 46, 52, 60, 70):
            ink = (dist > th).astype(np.uint8) * 255
            grayish = ink  # page_geometry expects a gray image (dark = ink)
            interior, bands, xext = gen.page_geometry(grayish, thresh=127)
            score = abs(len(bands) - max_line)
            if best is None or score < best[0]:
                best = (score, th, bands, xext)
        score, th, bands, xext = best
        sx, sy, tx, ty, info = gen.fit_page(
            db_lines, groups, extent, bands, xext, H, W)
        print("page %3d: bg=%s th=%2d bands=%2d/%2d fit=%-12s resid=%s flags=%s"
              % (pg, bg.astype(int).tolist(), th, len(bands), max_line,
                 info.get("fit"), info.get("max_line_residual_px"),
                 ",".join(info.get("flags", []))))


probe()
