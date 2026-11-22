# -*- coding: utf-8 -*-
"""
Generate per-ayah bounding boxes for the `madinah` image mushaf from the
1421H ayah-line database — the edition these pages actually are.

Why a separate generator (2026-11-22): the local madinah images (the
archive.org "Quran Mushaf Almadinah Hafs" scan) share the classic 1405H
LINE/PAGINATION structure (separate basmalah lines, verified y-wise), but
their WITHIN-LINE word layout follows the 1421H typesetting:

  - 1421 ayah boundaries land on the print's real inter-word gaps at
    ~63% vs the classic's ~13% on plain pages;
  - per-band content checks (e.g. madinah p564 band 8/15) confirm the
    1421's line content — including ayahs the classic DB places
    elsewhere (68:3 starts on band 8; 68:16 starts on band 15).

1421 DB conventions (measured):
  - same line grid as the classic (header slots are line-number gaps);
  - basmalah slots carry a row MISLABELED as the following ayah with the
    basmalah's centered ~54% extent -> detected via "classic has no
    glyphs on that line" + a narrow (~220px) band text block -> skipped;
  - compact surah-start lines (basmalah + first ayah merged, e.g. p604)
    have WIDE band blocks -> the row is kept (slight over-cover).

Per page:
  1. bands + margin-rule mask + per-band text blocks (shared machinery
     from generate_ayah_bboxes: page_geometry / band_text_block);
  2. line l <-> band l (the classic grid, verified by the y-fit there);
  3. per-line affine: the 1421 line extent -> the band's text block;
  4. y from the band itself; x from the 1421 segments; emit per-ayah
     per-line rects normalized 0..1;
  5. validate: reading-order first ayah == app meta; every segment inside
     the band's text block (+ tolerance); every text band covered.

Pages failing validation are flagged (fit=bbox) so emit_app_bboxes
excludes them (graceful fallback in the app). Pages 1-2 are ornamental
front matter and are skipped.

Usage:
  python scripts/generate_ayah_bboxes_madinah_1421.py [--all]
  python scripts/generate_ayah_bboxes_madinah_1421.py --pages 564,300
  python scripts/generate_ayah_bboxes_madinah_1421.py --overlays
"""
import argparse
import json
import os
import sqlite3
import sys

import numpy as np
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from generate_ayah_bboxes import (page_geometry, ensure_db,
                                  band_text_block)  # noqa: E402

META_PATH = os.path.join(ROOT, "public", "assets", "quran-meta-data.json")
PAGES_DIR = os.path.join(ROOT, "public", "assets", "mushaf_madinah_images")
CACHE_DIR = os.path.join(ROOT, "temp", "bbox-research")
CLASSIC = ensure_db(CACHE_DIR)
V1421 = os.path.join(CACHE_DIR, "ayahinfo_1421_1260.db")
OUT_PATH = os.path.join(CACHE_DIR, "madinah_ayah_bboxes_1421.json")

THRESH = 205
# a band narrower than this after a surah header is a pure basmalah line
BASMALAH_MAX_W = 350
# emitted segments must stay inside the band's text block (+ tolerance)
EDGE_TOL = 20


def classic_text_lines(con, pg):
    """line numbers on this page that carry TEXT (glyphs) in the classic."""
    cur = con.cursor()
    cur.execute("SELECT DISTINCT line_number FROM glyphs WHERE page_number=?",
                (pg,))
    return set(r[0] for r in cur.fetchall())


def rows_1421(con, pg):
    """[(line, s, a, x0, x1)] in reading order for the page."""
    cur = con.cursor()
    cur.execute("""SELECT line_number, sura_number, ayah_number,
                   MIN(min_x), MAX(max_x), MIN(position)
                   FROM glyphs WHERE page_number=?
                   GROUP BY line_number, sura_number, ayah_number""",
                (pg,))
    rows = cur.fetchall()
    # reading order: line asc, then min position asc
    rows = sorted(rows, key=lambda r: (r[0], r[5]))
    return [(r[0], r[1], r[2], r[3], r[4]) for r in rows]


def process_page(con, con2, pg, pages_meta, emit_overlays, out_dir):
    img_path = os.path.join(PAGES_DIR, "page_%04d.webp" % pg)
    if not os.path.exists(img_path):
        return None, {"error": "missing image"}
    gray = np.array(Image.open(img_path).convert("L"))
    H, W = gray.shape
    ink = gray < THRESH
    (c0, c1), bands, _, strip = page_geometry(gray, THRESH)
    if not bands:
        return None, {"error": "no bands"}

    text_lines = classic_text_lines(con, pg)
    rows = rows_1421(con2, pg)
    if not rows:
        return None, {"error": "no 1421 data"}

    # per-band text blocks
    blocks = {}
    for ln in {r[0] for r in rows} | {ln for ln in text_lines
                                      if 0 < ln <= len(bands)}:
        if 0 < ln <= len(bands):
            tb = band_text_block(ink, bands[ln - 1][0], bands[ln - 1][1],
                                 exclude=strip)
            if tb:
                blocks[ln] = tb

    # group rows per line, decide which to keep
    by_line = {}
    skipped_basmalah = []
    for (ln, s, a, x0, x1) in rows:
        if ln not in blocks:
            continue
        if ln not in text_lines:
            # classic has no glyphs here: header or basmalah slot.
            il, ir = blocks[ln]
            if ir - il <= BASMALAH_MAX_W:
                skipped_basmalah.append((ln, s, a))
                continue  # pure basmalah row (mislabeled) -> skip
            # compact surah-start line (basmalah + first ayah merged):
            # keep the row (it covers the ayah's real text too).
        by_line.setdefault(ln, []).append((s, a, x0, x1))

    # emit segments per (line, ayah)
    ayah_segs = {}
    flags = []
    covered_bands = set()
    for ln in sorted(by_line):
        il, ir = blocks[ln]
        lrows = by_line[ln]
        dbx0 = min(r[2] for r in lrows)
        dbx1 = max(r[3] for r in lrows)
        if dbx1 <= dbx0:
            continue
        s_ = (ir - il) / float(dbx1 - dbx0)
        t_ = il - dbx0 * s_
        a, b = bands[ln - 1]
        for (s, ay, x0, x1) in lrows:
            rx0 = x0 * s_ + t_
            rx1 = x1 * s_ + t_
            if rx1 - rx0 < 4:
                continue
            # physical sanity: inside the band's text block (+tolerance)
            if rx0 < il - EDGE_TOL or rx1 > ir + EDGE_TOL:
                flags.append("seg_out_of_block_p%d_l%d" % (pg, ln))
                continue
            seg = [round(rx0 / W, 5), round(a / H, 5),
                   round((rx1 - rx0) / W, 5), round((b - a) / H, 5)]
            ayah_segs.setdefault((s, ay), []).append(seg)
            covered_bands.add(ln)

    # Validation: PHYSICAL only. The reading-order first ayah is NOT
    # compared to the app meta: this print follows the 1421H pagination,
    # which cuts ~50 page boundaries one ayah earlier/later than the
    # classic/meta (e.g. 68:16 starts on p564's last line - physically
    # verified). That costs at most one ayah's head-words per occurrence.
    first = None
    for ln in sorted(covered_bands):
        lrows = by_line.get(ln, [])
        if lrows:
            rightmost = max(lrows, key=lambda r: (r[2] + r[3]) / 2.0)
            first = (rightmost[0], rightmost[1])
            break
    expected = pages_meta[pg - 1]

    # every classic text band should get segments (missing ones are
    # informational: the 1421 re-typesets juz-30 short surahs freely)
    missing = [ln for ln in sorted(text_lines)
               if 0 < ln <= len(bands) and ln not in covered_bands]

    info = {
        "fit": "1421",
        "flags": flags,
        "bands": len(bands),
        "rows": len(rows),
        "segs": sum(len(v) for v in ayah_segs.values()),
        "skipped_basmalah_rows": len(skipped_basmalah),
        "first_ayah": first,
        "meta_first": list(expected),
        "missing_text_bands": missing,
    }
    if missing:
        info["flags"] = flags + ["partial_missing_bands_%s" % missing[:4]]
        info["partial"] = True
    # physical failures (segments outside their band's block) exclude the
    # page from the emitted asset; partial pages are still emitted.
    if flags:
        info["fit"] = "bbox"
        info["flags"] = info["flags"] + ["physical_mismatch"]

    # reference transform: median per-line scale (x) — informational
    scales = []
    for ln, lrows in by_line.items():
        if ln not in blocks:
            continue
        dbw = max(r[3] for r in lrows) - min(r[2] for r in lrows)
        if dbw > 0:
            scales.append((blocks[ln][1] - blocks[ln][0]) / float(dbw))
    out = {
        "page": pg,
        "width": W, "height": H,
        "transform": {"sx": round(float(np.median(scales)), 5)
                      if scales else 0.0},
        "ayahs": [{"surah": k[0], "ayah": k[1], "segments": v}
                  for k, v in ayah_segs.items()],
        "info": info,
    }

    if emit_overlays and out["ayahs"]:
        im = Image.open(img_path).convert("RGB")
        dr = ImageDraw.Draw(im, "RGBA")
        pal = [(230, 25, 75), (60, 180, 75), (0, 130, 200), (245, 130, 48),
               (145, 30, 180), (70, 240, 240), (240, 50, 230), (210, 245, 60)]
        for i, ay in enumerate(out["ayahs"]):
            for (x, y, w, h) in ay["segments"]:
                dr.rectangle((x * W, y * H, (x + w) * W, (y + h) * H),
                             outline=pal[i % len(pal)], width=3)
        os.makedirs(os.path.join(out_dir, "overlays"), exist_ok=True)
        im.save(os.path.join(out_dir, "overlays",
                             "m1421_p%04d.png" % pg))
    return out, info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--pages", type=str, default="")
    ap.add_argument("--overlays", action="store_true")
    ap.add_argument("--out", type=str, default=None)
    args = ap.parse_args()

    if args.all:
        targets = range(1, 605)
    elif args.pages:
        targets = [int(x) for x in args.pages.split(",")]
    else:
        targets = [564, 300, 3, 50, 106, 604]
    out_path = args.out or OUT_PATH

    con = sqlite3.connect(CLASSIC)
    con2 = sqlite3.connect(V1421)
    meta = json.load(open(META_PATH, encoding="utf-8"))
    pages_meta = meta["pages"]

    results = []
    flagged = []
    for pg in targets:
        if pg in (1, 2):
            continue  # ornamental front matter
        try:
            out, info = process_page(con, con2, pg, pages_meta,
                                     args.overlays,
                                     os.path.dirname(out_path) or ".")
        except Exception as e:
            out, info = None, {"error": str(e)}
        if out:
            results.append(out)
        line = "p%-3d bands=%2d rows=%2d segs=%3d basm=%d first=%s meta=%s" \
               % (pg, info.get("bands", 0), info.get("rows", 0),
                  info.get("segs", 0), info.get("skipped_basmalah_rows", 0),
                  info.get("first_ayah"), info.get("meta_first"))
        if info.get("partial"):
            line += "  PARTIAL"
        if info.get("fit") != "1421":
            line += "  FLAGS=%s" % (info.get("flags"),)
            flagged.append(pg)
        print(line)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"pages": results}, f, ensure_ascii=False)
    print("\nwrote %s (%d pages, %d flagged: %s)"
          % (out_path, len(results), len(flagged), flagged[:20]))
    con.close()
    con2.close()


if __name__ == "__main__":
    main()
