# -*- coding: utf-8 -*-
"""
Generate per-ayah bounding boxes for the `madinah` image mushaf
(public/assets/mushaf_madinah_images) by warping the classic 1405H Madani
ayahinfo database (quran.com / Quran Android) onto each local page.

Why this works: the local madinah images are a Madani-layout reprint with an
ornamental frame; its 15-line structure matches the classic print line-for-line
(measured residuals <= ~6px per line center on clean pages).

Pipeline per page:
  1. Detect the ornamental frame -> interior text area (their image space).
  2. Detect their text-line bands (row profile thresholding).
  3. Get the DB's line bands for the page (DB space).
  4. Tail-align their bands to DB lines, least-squares fit (sy, ty);
     fit (sx, tx) from text x-extents. Fallback: bbox fit + review flag.
  5. Group DB glyphs by (line, sura, ayah) -> one box per ayah line segment,
     warp it, normalize to 0..1 of the image, emit.
  6. Validate: DB page-start ayah must equal quran-meta-data.json's mapping;
     flag pages with large residuals / band-count mismatches / no ink.

Output: one JSON file with normalized ayah segments + a validation report.
Run with --overlays to also emit review PNGs.

Usage:
  python scripts/generate_ayah_bboxes.py --sample 5 --overlays
  python scripts/generate_ayah_bboxes.py --all
"""
import argparse
import json
import os
import sqlite3
import sys
import tempfile
import urllib.request
import zipfile

import numpy as np
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
META_PATH = os.path.join(ROOT, "assets", "quran-meta-data.json")
DB_URL = "https://files.quran.app/hafs/madani/databases/ayahinfo/ayahinfo_1260.zip"
DB_NAME = "ayahinfo_classic_1260.db"
CACHE_DIR = os.path.join(ROOT, "research", "bbox")

# Image mushafs that follow the standard Madani 15-line layout (line-for-line
# match with the classic 1405H reference DB — verified by the line-center fit).
# mwdoa is NOT here: the thematic edition has its own typesetting and needs
# the marker-detection pipeline instead.
LAYOUT_MUSHAFA = {
    "madinah": {
        "pages_dir": os.path.join(ROOT, "assets", "mushaf_madinah_images"),
        "thresh": 205,
        "out": os.path.join(CACHE_DIR, "madinah_ayah_bboxes.json"),
    },
    "tashel": {
        "pages_dir": os.path.join(ROOT, "assets", "mushaf_tashel_pages"),
        "thresh": 140,
        "out": os.path.join(CACHE_DIR, "tashel_ayah_bboxes.json"),
    },
}

# ---------------- page geometry (their image space) ----------------


def strip_columns_mask(ink, bands, trim=5, thresh=0.08):
    """Columns inked inside the inter-band gaps = vertical margin rules.

    Tashel's pages have a dotted vertical rule at x~2-25 only 13-27px from
    the text (no split threshold separates it from real text gaps), and
    madinah's faint outer border line behaves the same way. Both are inked
    BETWEEN text lines, where real text never is.
    """
    H, W = ink.shape
    if not bands:
        return np.zeros(W, bool)
    span_lo, span_hi = bands[0][0], bands[-1][1]
    covered = np.zeros(H, bool)
    for (a, b) in bands:
        covered[max(0, a - trim):min(H, b + trim)] = True
    gap_rows = np.zeros(H, bool)
    gap_rows[span_lo:span_hi] = True
    gap_rows &= ~covered
    if gap_rows.sum() < 50:
        return np.zeros(W, bool)
    gcol = ink[gap_rows].mean(axis=0)
    return gcol > thresh


def band_text_block(ink, a, b, split_gap=30, lo=0.10, exclude=None):
    """Largest connected ink run inside one band = that line's text block.

    The ornamental frame leaves side blocks (medallions, rosettes, border
    segments) that are separated from the text by wide gaps (>~30px),
    while justified text never has a white gap wider than a few px
    (kashida stretching). So splitting the band's columns on gaps >=
    split_gap and keeping the widest run yields exactly the text line,
    free of frame contamination. `exclude` drops margin-rule columns
    (strip_columns_mask) that sit too close to the text for the gap test.
    """
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
            runs.append((st, i - 1))
            st = None
    if st is not None:
        runs.append((st, len(is_ink) - 1))
    merged = []
    for r in runs:
        if merged and r[0] - merged[-1][1] - 1 < split_gap:
            merged[-1] = (merged[-1][0], r[1])
        else:
            merged.append(r)
    if not merged:
        return None
    best = max(merged, key=lambda r: r[1] - r[0])
    return (int(best[0]), int(best[1]))


def page_x_extent(ink, bands, keep_cols, exclude=None):
    """Robust page-level text x-extent.

    Old logic (colsum > 1% of band rows over all band rows) swallowed the
    frame's faint outer border lines, so the extent came out as the full
    page width and the x-fit stretched every box past the text block.
    Instead: per-band text blocks, then the MEDIAN of left/right edges
    over all bands (rosette/header lines can't tilt the median).
    """
    lefts, rights = [], []
    for (a, b) in bands:
        tb = band_text_block(ink, a, b, exclude=exclude)
        if tb and tb[1] - tb[0] > 0.25 * (keep_cols[-1] - keep_cols[0]):
            lefts.append(tb[0])
            rights.append(tb[1])
    if len(lefts) >= 4:
        return int(np.median(lefts)), int(np.median(rights))
    if lefts:
        return int(min(lefts)), int(max(rights))
    return None


def page_geometry(gray, thresh=205):
    """Frame interior + text-line bands for one local page image."""
    H, W = gray.shape
    ink = gray < thresh
    col_density = ink.sum(axis=0) / H
    # frame columns: dense over most of the page height (some pages have
    # several stacked ornament layers -> mask them ALL out, not just the edges)
    frame_mask = col_density > 0.4
    keep_cols = np.where(~frame_mask)[0]
    if len(keep_cols) < W * 0.4:
        keep_cols = np.arange(int(W * 0.08), int(W * 0.92))

    inner = ink[:, keep_cols]
    rowd = inner.sum(axis=1) / inner.shape[1]
    bands, in_b = [], False
    for i, v in enumerate(rowd):
        if v > 0.02 and not in_b:
            st, in_b = i, True
        elif v <= 0.02 and in_b:
            if i - st > 30:
                bands.append((st, i))
            in_b = False
    if in_b and H - st > 30:
        bands.append((st, H))
    # drop frame remnants (bands touching top/bottom edges)
    bands = [b for b in bands if b[0] > 5 and b[1] < H - 5]
    # drop thin divider bands (ornaments, hizb markers) - keep real text lines:
    # real lines are all similar in height; dividers are much shorter.
    if bands:
        heights = [b[1] - b[0] for b in bands]
        med = float(np.median(heights))
        if med > 0:
            bands = [b for b in bands if (b[1] - b[0]) >= 0.45 * med]

    strip_mask = strip_columns_mask(ink, bands)
    extent = page_x_extent(ink, bands, keep_cols, exclude=strip_mask)
    if extent is None:
        # last resort (sparse/ornamental pages): old naive scan
        if bands:
            lo = min(a for a, _ in bands)
            hi = max(b for _, b in bands)
            band_rows = inner[lo:hi]
            colsum = band_rows.sum(axis=0)
            nz = np.where(colsum > 0.01 * band_rows.shape[0])[0]
            if len(nz):
                extent = (int(keep_cols[nz.min()]), int(keep_cols[nz.max()]))
            else:
                extent = (int(keep_cols[0]), int(keep_cols[-1]))
        else:
            extent = (int(keep_cols[0]), int(keep_cols[-1]))
    strip_mask = strip_columns_mask(ink, bands)
    return (int(keep_cols[0]), int(keep_cols[-1])), bands, extent, strip_mask


# ---------------- DB side ----------------


def ensure_db(cache_dir=CACHE_DIR):
    os.makedirs(cache_dir, exist_ok=True)
    db = os.path.join(cache_dir, DB_NAME)
    if not os.path.exists(db):
        zpath = os.path.join(cache_dir, "ayahinfo_classic.zip")
        print("downloading classic madani ayahinfo db ...")
        urllib.request.urlretrieve(DB_URL, zpath)
        with zipfile.ZipFile(zpath) as z:
            extracted = z.namelist()
            z.extractall(cache_dir)
        os.remove(zpath)
        # normalize the extracted filename
        for cand in extracted:
            if cand.endswith(".db"):
                got = os.path.join(cache_dir, cand)
                if os.path.abspath(got) != os.path.abspath(db):
                    os.replace(got, db)
    return db


def db_page(con, page_no):
    cur = con.cursor()
    cur.execute(
        "SELECT line_number, MIN(min_y), MAX(max_y) FROM glyphs "
        "WHERE page_number=? GROUP BY line_number ORDER BY line_number",
        (page_no,))
    lines = [(r[0], r[1], r[2]) for r in cur.fetchall()]
    cur.execute(
        "SELECT line_number, sura_number, ayah_number, "
        "MIN(min_x), MIN(min_y), MAX(max_x), MAX(max_y) "
        "FROM glyphs WHERE page_number=? "
        "GROUP BY line_number, sura_number, ayah_number "
        "ORDER BY line_number, MIN(position)",
        (page_no,))
    groups = cur.fetchall()
    cur.execute(
        "SELECT MIN(min_x), MAX(max_x) FROM glyphs WHERE page_number=?",
        (page_no,))
    extent = cur.fetchone()
    cur.execute(
        "SELECT sura_number, ayah_number, line_number, position "
        "FROM glyphs WHERE page_number=? "
        "ORDER BY line_number, position LIMIT 1", (page_no,))
    first = cur.fetchone()
    return lines, groups, extent, first


# ---------------- fitting ----------------


def fit_axis(src_pts, dst_pts):
    """Least-squares dst = a*src + b."""
    A = np.vstack([src_pts, np.ones(len(src_pts))]).T
    sol, *_ = np.linalg.lstsq(A, dst_pts, rcond=None)
    return float(sol[0]), float(sol[1])


def fit_page(db_lines, groups, db_extent, bands, their_x_extent, H, W,
             band_blocks=None, x_prior=None):
    """Return (sx, sy, tx, ty, info).

    Preferred: index pairing - the DB's line numbers count every physical
    line (gaps where surah headers / basmalahs sit), so when the number of
    detected bands equals the DB's max line number, band i <-> DB line i and
    only lines that have glyphs participate in the least-squares fit.
    Fallback: tail-aligned fit on the last min(count) lines.

    X axis: paired-line fit - map the DB's full-width lines onto their
    bands' text blocks (band_text_block, frame-free) and take the median
    edges. Falls back to the page-level extent.
    """
    flags = []
    db_by_no = {ln: (lo, hi) for (ln, lo, hi) in db_lines}
    max_line_no = max(db_by_no) if db_by_no else 0
    band_centers = np.array([(a + b) / 2.0 for (a, b) in bands], np.float64)
    sy = ty = None
    resid = None
    method = None

    if len(bands) == max_line_no and max_line_no >= 4:
        src, dst = [], []
        for (ln, lo, hi) in db_lines:
            if 0 < ln <= len(bands):
                src.append((lo + hi) / 2.0)
                dst.append(band_centers[ln - 1])
        if len(src) >= 4 and np.std(src) > 1e-6:
            sy, ty = fit_axis(np.array(src, np.float64), np.array(dst, np.float64))
            resid = np.abs(sy * np.array(src) + ty - np.array(dst))
            method = "index"
            if resid.max() > 0.30 * (H / 15.0):
                flags.append("y_residual_high")

    if sy is None:
        # hypothesis repair: band count off by one - try band splits / drops
        cands = []
        if len(bands) == max_line_no - 1 and len(bands) >= 4:
            med = float(np.median([b[1] - b[0] for b in bands])) if bands else 0
            # A) a tall band likely swallowed two lines: split it at its middle
            for i, b in enumerate(bands):
                if (b[1] - b[0]) > 1.4 * med:
                    mid = (b[0] + b[1]) // 2
                    cands.append(bands[:i] + [(b[0], mid), (mid, b[1])] + bands[i + 1:])
            # B) a line fell under the density threshold: insert in a gap
            for i in range(len(bands) - 1):
                g0, g1 = bands[i][1], bands[i + 1][0]
                if g1 - g0 > 0.5 * med:
                    cands.append(bands[:i + 1] + [(g0, g1)] + bands[i + 1:])
        elif len(bands) == max_line_no + 1 and len(bands) >= 5:
            # one extra band (divider / ornament): try dropping each
            cands = [bands[:i] + bands[i + 1:] for i in range(len(bands))]

        best = None
        for cb in cands:
            if len(cb) != max_line_no:
                continue
            src, dst = [], []
            ok = True
            for (ln, lo, hi) in db_lines:
                if not (0 < ln <= len(cb)):
                    ok = False
                    break
                src.append((lo + hi) / 2.0)
                dst.append((cb[ln - 1][0] + cb[ln - 1][1]) / 2.0)
            if not ok or len(src) < 4 or np.std(src) < 1e-6:
                continue
            sy2, ty2 = fit_axis(np.array(src, np.float64), np.array(dst, np.float64))
            r2 = np.abs(sy2 * np.array(src) + ty2 - np.array(dst))
            if best is None or r2.max() < best[0].max():
                best = (r2, sy2, ty2)
        if best is not None and best[0].max() <= 0.30 * (H / 15.0):
            resid, sy, ty = best
            method = "index_repair"
            flags.append("band_repaired_%d_vs_%d" % (len(bands), max_line_no))

    if sy is None:
        # tail-aligned fallback
        db_centers = np.array([(lo + hi) / 2.0 for (_, lo, hi) in db_lines],
                               np.float64)
        n_db, n_b = len(db_centers), len(band_centers)
        if n_db and n_b:
            n = min(n_db, n_b)
            pairs_db = db_centers[-n:]
            pairs_th = band_centers[-n:]
            if n >= 4 and np.std(pairs_db) > 1e-6:
                sy, ty = fit_axis(pairs_db, pairs_th)
                resid = np.abs(sy * pairs_db + ty - pairs_th)
                method = "tail"
                if resid.max() > 0.30 * (H / 15.0):
                    flags.append("y_residual_high")
                if n_db != n_b:
                    flags.append("band_count_%d_vs_db_%d" % (n_b, n_db))
            else:
                flags.append("too_few_lines_for_y_fit")
        if sy is None:
            if db_lines and bands:
                sy = (bands[-1][1] - bands[0][0]) / float(db_lines[-1][2] - db_lines[0][1])
                ty = bands[0][0] - db_lines[0][1] * sy
                flags.append("y_bbox_fallback")
                method = "bbox"
            else:
                sy, ty = H / 2038.0, 0.0
                flags.append("y_default")
                method = "default"

    # ---- x axis ----
    x_method = None
    their_x = None
    paired_l = paired_r = None
    if x_prior is not None:
        # global consensus text block (median over all pages' paired fits):
        # used for pages whose own paired fit is displaced (different
        # line-fill vs the classic print - the block itself is fixed).
        their_x = (int(x_prior[0]), int(x_prior[1]))
        x_method = "global_prior"
    elif band_blocks and db_extent and db_extent[0] is not None:
        db_w = float(db_extent[1] - db_extent[0])
        per_line_x = {}
        for (ln, s, a, x0, y0, x1, y1) in groups:
            if ln not in per_line_x:
                per_line_x[ln] = [1e9, -1e9]
            per_line_x[ln][0] = min(per_line_x[ln][0], x0)
            per_line_x[ln][1] = max(per_line_x[ln][1], x1)
        full_pairs = []
        for ln, (x0, x1) in per_line_x.items():
            if ln in band_blocks and (x1 - x0) >= 0.85 * db_w:
                full_pairs.append(band_blocks[ln])
        if len(full_pairs) >= 3:
            their_x = (int(np.median([p[0] for p in full_pairs])),
                       int(np.median([p[1] for p in full_pairs])))
            x_method = "paired(%d)" % len(full_pairs)
            paired_l = float(np.median([p[0] for p in full_pairs]))
            paired_r = float(np.median([p[1] for p in full_pairs]))

    if their_x is not None and their_x[1] > their_x[0]:
        sx = (their_x[1] - their_x[0]) / float(db_extent[1] - db_extent[0])
        tx = their_x[0] - db_extent[0] * sx
        if x_method is None:
            x_method = "extent"
    elif their_x_extent[1] > their_x_extent[0]:
        sx = (their_x_extent[1] - their_x_extent[0]) / float(db_extent[1] - db_extent[0])
        tx = their_x_extent[0] - db_extent[0] * sx
        x_method = "page_extent"
        flags.append("x_page_extent_fallback")
    else:
        sx, tx = W / 1260.0, 0.0
        x_method = "default"
        flags.append("x_default")

    info = {
        "fit": method,
        "x_fit": x_method,
        "flags": flags,
        "max_line_residual_px": None if resid is None else round(float(resid.max()), 1),
        "db_lines": len(db_lines),
        "their_bands": len(bands),
    }
    if x_method.startswith("paired"):
        # for the global-consensus pass: this page's own paired text block
        info["x_paired"] = [round(paired_l, 1), round(paired_r, 1)]
    return sx, sy, tx, ty, info


# ---------------- main generation ----------------


def meta_pages():
    meta = json.load(open(META_PATH, encoding="utf-8"))
    return meta["pages"]  # 604 entries [surah, ayah] = start of page


def process_page(con, page_no, pages_meta, emit_overlays, out_dir, cfg,
                 x_prior=None):
    pages_dir = cfg["pages_dir"]
    img_path = os.path.join(pages_dir, "page_%04d.webp" % page_no)
    if not os.path.exists(img_path):
        return None, {"error": "missing image"}
    gray = np.array(Image.open(img_path).convert("L"))
    H, W = gray.shape
    ink = gray < cfg["thresh"]
    interior, bands, their_x_extent, strip_mask = \
        page_geometry(gray, thresh=cfg["thresh"])
    db_lines, groups, db_extent, db_first = db_page(con, page_no)
    if not groups:
        return None, {"error": "no db data"}

    # per-band text blocks (frame-free) for the paired-line x-fit
    band_blocks = {}
    for ln in {g[0] for g in groups}:
        if 0 < ln <= len(bands):
            tb = band_text_block(ink, bands[ln - 1][0], bands[ln - 1][1],
                                 exclude=strip_mask)
            if tb:
                band_blocks[ln] = tb

    sx, sy, tx, ty, info = fit_page(db_lines, groups, db_extent, bands,
                                    their_x_extent, H, W,
                                    band_blocks=band_blocks, x_prior=x_prior)

    # pagination cross-check: db reading-order first (sura, ayah) vs app meta
    if db_first and db_first[0] is not None:
        expected = pages_meta[page_no - 1]
        if [db_first[0], db_first[1]] != list(expected):
            info["pagination_mismatch"] = {
                "db": [db_first[0], db_first[1]], "app_meta": list(expected)}

    ayahs = []
    for (ln, s, a, x0, y0, x1, y1) in groups:
        bx0, by0 = x0 * sx + tx, y0 * sy + ty
        bx1, by1 = x1 * sx + tx, y1 * sy + ty
        ayahs.append({
            "surah": s, "ayah": a, "line": ln,
            "x": round(bx0 / W, 5), "y": round(by0 / H, 5),
            "w": round((bx1 - bx0) / W, 5), "h": round((by1 - by0) / H, 5),
        })
    # merge ayah segments per ayah
    merged = {}
    for seg in ayahs:
        key = (seg["surah"], seg["ayah"])
        merged.setdefault(key, []).append([seg["x"], seg["y"], seg["w"], seg["h"]])
    out = {
        "page": page_no,
        "width": W, "height": H,
        "transform": {"sx": round(sx, 5), "sy": round(sy, 5),
                      "tx": round(tx, 1), "ty": round(ty, 1)},
        "ayahs": [{"surah": k[0], "ayah": k[1], "segments": v}
                  for k, v in merged.items()],
        "info": info,
    }

    if emit_overlays:
        im = Image.open(img_path).convert("RGB")
        dr = ImageDraw.Draw(im, "RGBA")
        pal = [(230, 25, 75), (60, 180, 75), (0, 130, 200), (245, 130, 48),
               (145, 30, 180), (70, 240, 240), (240, 50, 230), (210, 245, 60)]
        for i, (k, segs) in enumerate(merged.items()):
            for (x, y, w, h) in segs:
                dr.rectangle((x * W, y * H, (x + w) * W, (y + h) * H),
                             outline=pal[i % len(pal)], width=3)
        os.makedirs(os.path.join(out_dir, "overlays"), exist_ok=True)
        im.save(os.path.join(out_dir, "overlays",
                             "%s_p%04d.png" % (cfg["name"], page_no)))
    return out, info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mushaf", type=str, default="madinah",
                    choices=sorted(LAYOUT_MUSHAFA.keys()),
                    help="image mushaf to process (standard-layout ones)")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--sample", type=int, default=0,
                    help="process every Nth page")
    ap.add_argument("--pages", type=str, default="",
                    help="comma-separated page numbers")
    ap.add_argument("--overlays", action="store_true")
    ap.add_argument("--out", type=str, default=None)
    args = ap.parse_args()

    cfg = dict(LAYOUT_MUSHAFA[args.mushaf], name=args.mushaf)
    out_path = args.out or cfg["out"]

    db = ensure_db()
    con = sqlite3.connect(db)
    pages_meta = meta_pages()

    if args.all:
        targets = range(1, 605)
    elif args.sample:
        targets = range(1, 605, args.sample)
    elif args.pages:
        targets = [int(x) for x in args.pages.split(",")]
    else:
        targets = list(range(1, 605, 50)) + [2, 3, 50, 300, 604]
        targets = sorted(set(targets))

    results = []
    failed = []
    for pg in targets:
        try:
            out, info = process_page(con, pg, pages_meta, args.overlays,
                                     os.path.dirname(out_path) or ".", cfg)
        except Exception as e:
            out, info = None, {"error": str(e)}
        if out:
            results.append(out)
        else:
            failed.append((pg, info))

    def describe(pg, info):
        fl = info.get("flags") or []
        msg = ""
        if "pagination_mismatch" in info:
            msg += " PAGINATION-MISMATCH:%s" % info["pagination_mismatch"]
        if info.get("error"):
            msg += " ERROR:%s" % info["error"]
        if fl:
            msg += " flags=%s" % ",".join(fl)
        if info.get("max_line_residual_px") is not None:
            msg += " resid=%.1fpx" % info["max_line_residual_px"]
        if info.get("x_fit"):
            msg += " x=%s" % info["x_fit"]
        print("%s page %3d: lines db=%s theirs=%s%s"
              % (args.mushaf, pg, info.get("db_lines"),
                 info.get("their_bands"), msg))

    for r in results:
        describe(r["page"], r["info"])
    for pg, info in failed:
        describe(pg, info)

    # ---- global-consensus pass (x axis) ----
    # The print's text block is fixed across pages. Pages whose own paired
    # fit is displaced (line-fill differs from the classic print, e.g.
    # madinah p191/p339) get the consensus block instead - their boxes then
    # cover the true text (superset) with correct edges.
    paired = [r["info"]["x_paired"] for r in results
              if str(r["info"].get("x_fit", "")).startswith("paired")
              and not r["info"].get("flags")]
    if len(paired) >= 50:
        prior = (float(np.median([p[0] for p in paired])),
                 float(np.median([p[1] for p in paired])))
        redo = [i for i, r in enumerate(results)
                if r["info"].get("x_paired") and
                (abs(r["info"]["x_paired"][0] - prior[0]) > 45 or
                 abs(r["info"]["x_paired"][1] - prior[1]) > 45)]
        if redo:
            print("\nconsensus text block: (%.0f, %.0f); re-fitting %d "
                  "displaced pages with it" % (prior[0], prior[1], len(redo)))
            for i in redo:
                pg = results[i]["page"]
                try:
                    out, info = process_page(con, pg, pages_meta,
                                              args.overlays,
                                              os.path.dirname(out_path) or ".",
                                              cfg, x_prior=prior)
                    if out:
                        results[i] = out
                        describe(pg, out["info"])
                except Exception as e:
                    print("  re-fit p%d failed: %s" % (pg, e))

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"pages": results}, f, ensure_ascii=False)
    print("\nwrote %s (%d pages)" % (out_path, len(results)))


if __name__ == "__main__":
    main()
