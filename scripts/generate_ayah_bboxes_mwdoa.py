# -*- coding: utf-8 -*-
"""
Generate per-ayah bounding boxes for the `mwdoa` image mushaf
(public/assets/mushuf_mwdoa_images) via MARKER DETECTION.

Why different from madinah/tashel: the thematic mushaf has its own line
layout, so the classic DB cannot be warped onto it. Instead:

  1. The end-of-ayah sign is an ornate GOLDEN DIAMOND medallion (~53x64 px
     with a dark rosette inside) — confirmed by the user on page 300.
  2. A full-medallion template (cut from the confirmed marker) is matched on
     every page (gold-hue map, TM_CCOEFF_NORMED, NMS) -> markers.
  3. mwdoa follows the STANDARD Madani pagination (validated: detected
     marker counts equal the expected ayah ends per page), so the k-th
     marker in reading order (RTL: top band first, right-to-left within a
     band) is the end of the k-th ayah that ends on that page (ayah list
     and page boundaries from the classic 1405H DB).
  4. Segments per ayah are built from the marker chain: between two
     consecutive markers on a band, plus full intermediate bands. Their
     x-extent is the TEXT COLUMN: the ink extent between the page frame and
     the marginal FIHRIS (index) column — left on even pages, right on odd
     ones (fihrist_clip_x) — so the ayah highlight never covers the fihris.

Pages whose detected marker count != expected ends are flagged and excluded
from the app asset (graceful fallback there).

Usage:
  python scripts/generate_ayah_bboxes_mwdoa.py [--all|--pages 300,...] [--overlays]
"""
import argparse
import importlib.util
import json
import math
import os
import sqlite3

import numpy as np
from PIL import Image, ImageDraw
import cv2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
META_PATH = os.path.join(ROOT, "public", "assets", "quran-meta-data.json")
PAGES_DIR = os.path.join(ROOT, "public", "assets", "mushuf_mwdoa_images")
CACHE_DIR = os.path.join(ROOT, "temp", "bbox-research")
OUT_PATH = os.path.join(CACHE_DIR, "mwdoa_ayah_bboxes.json")

# the user-confirmed marker on page 300 (row 11, col 8 of the grid diagnostic)
CONFIRMED = dict(page=300, x=239, y=972, w=53, h=64, pad=8)

# detector parameters (validated on pages 3/50/120/300/400)
MATCH_THRESHOLD = 0.55
# second pass for pages whose markers are too faded for the primary pass
RETRY_THRESHOLD = 0.45
NMS_PX = 30


def ensure_db():
    spec = importlib.util.spec_from_file_location(
        "gen", os.path.join(ROOT, "scripts", "generate_ayah_bboxes.py"))
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    return gen.ensure_db()


# ---------------- image analysis ----------------


def _cluster_runs(flags, gap, min_len):
    """Contiguous True runs of `flags`, merging gaps < `gap`, len >= min_len."""
    out = []
    in_run = False
    gap_left = 0
    for i, v in enumerate(flags):
        if v:
            if not in_run:
                st, in_run = i, True
            gap_left = 0
        elif in_run:
            gap_left += 1
            if gap_left >= gap:
                if i - gap_left - st >= min_len:
                    out.append((st, i - gap_left))
                in_run = False
    if in_run and len(flags) - st >= min_len:
        out.append((st, len(flags)))
    return out


def uniform_bands_lh(gray, th=160):
    """Original user-validated band detection. Also returns the TEXT x-extent
    (tx0, tx1) and the FRAME geometry (fx0, fx1, vclusters): the ink extent
    over band rows with the frame's dense VERTICAL columns masked out — so
    the page border and marginal text outside it are excluded from the ayah
    boxes. vclusters (the dense column clusters incl. the frame borders and
    the fihrist rule) are returned for the fihrist clip below."""
    H, W = gray.shape
    ink = gray < th
    cold = ink.sum(axis=0) / H
    keep = np.where(cold <= 0.4)[0]
    if len(keep) < W * 0.4:
        keep = np.arange(int(W * 0.08), int(W * 0.92))
    inner = ink[:, keep]
    rowd = inner.sum(axis=1) / inner.shape[1]
    raw, in_b = [], False
    for i, v in enumerate(rowd):
        if v > 0.03 and not in_b:
            st, in_b = i, True
        elif v <= 0.03 and in_b:
            if i - st > 25:
                raw.append((st, i))
            in_b = False
    if in_b and H - st > 25:
        raw.append((st, H))
    raw = [b for b in raw if b[0] > 5 and b[1] < H - 5]
    if not raw:
        return [], 0, (0, W), (0, W, [])
    hs = [b[1] - b[0] for b in raw]
    med = float(np.median(hs))
    raw = [b for b in raw if (b[1] - b[0]) >= 0.45 * med]
    lh = float(np.median([b[1] - b[0] for b in raw]))
    bands = [(int(round((y0 + y1) / 2 - lh / 2)), int(round((y0 + y1) / 2 + lh / 2)))
             for (y0, y1) in raw]
    # clamp snapped bands into the image (a merged top band can push < 0)
    bands = [(max(0, b0), min(H, b1)) for (b0, b1) in bands]
    # text x-extent: the page's ornamental frame = the FIRST/LAST dense
    # column clusters over the band rows (>= 35% of the band-row height,
    # gaps < 15px merged). Text always sits INSIDE the frame; marginal text
    # and the border itself are excluded. The extent is then refined to the
    # actual ink inside those bounds.
    lo = min(b[0] for b in bands)
    hi = max(b[1] for b in bands)
    bandrows = ink[lo:hi]
    cold = bandrows.sum(axis=0) / float(max(1, hi - lo))
    vclusters = _cluster_runs(cold > 0.35, gap=15, min_len=2)
    if len(vclusters) >= 2:
        fx0 = vclusters[0][1] + 10
        fx1 = vclusters[-1][0] - 10
    else:
        fx0, fx1 = 0, W
    fx0 = max(0, fx0)
    fx1 = min(W, fx1)
    cols = bandrows[:, fx0:fx1].sum(axis=0)
    nz = np.where(cols > 0.05 * (hi - lo))[0]
    if len(nz):
        tx0 = fx0 + int(nz.min())
        tx1 = fx0 + int(nz.max())
    else:
        tx0, tx1 = fx0, max(fx0 + 1, fx1)
    return bands, lh, (tx0, tx1), (fx0, fx1, vclusters)


def fihrist_clip_x(a, gray, page_no, fx0, fx1, vclusters, lo, hi):
    """The mwdoa print carries a marginal FIHRIS (index) column on the OUTER
    edge of every content page: LEFT on even (left-hand) pages, RIGHT on odd
    (right-hand) pages. Layout, outside-in: page frame -> index entries ->
    ornamental rule band (thin on most pages, a wide gold/dark band on some)
    -> text column. Without this clip the full-width ayah segments reach the
    frame and the highlight covers the fihris (user-reported).

    Returns (clip_l, clip_r) — the text-column boundaries with the fihris
    excluded (None on a side without a strip, e.g. ornamental page 2);
    callers clamp tx0/tx1 to them.

    Detection, per outer side only (the inner side may legitimately hold
    pale topic-colored TEXT blocks, which must never be clipped):
      1. the entries' colored chip run adjacent to the frame border
         (saturated-color columns, dense and full-height), and/or
      2. the ornamental rule = the innermost dense ink column cluster.
    The chosen edge is then refined by walking toward the text across
    ornament/pale-margin columns, stopping at the first text-like ink
    column, so the clip lands on the true text boundary.
    """
    H, W = gray.shape
    even = (page_no % 2 == 0)
    rh = float(max(1, hi - lo))
    ink = gray < 160
    rr, gg, bb = (a[:, :, 0].astype(np.int32), a[:, :, 1].astype(np.int32),
                  a[:, :, 2].astype(np.int32))
    mx = np.maximum(np.maximum(rr, gg), bb)
    mn = np.minimum(np.minimum(rr, gg), bb)
    sat = (mx - mn) > 40
    cold = ink[lo:hi].sum(axis=0) / rh
    satd = sat[lo:hi].sum(axis=0) / rh

    zone = int(0.32 * W)

    def side_edge(side):
        """Initial fihris edge on one side, or None."""
        if side == "L":
            z_lo, z_hi = max(0, fx0), min(W, fx0 + zone)
        else:
            z_lo, z_hi = max(0, fx1 - zone), min(W, fx1)
        if z_hi - z_lo < 0.05 * W:
            return None

        # -- 1) chip run adjacent to the frame border --
        prof = satd[z_lo:z_hi]
        on = (prof > 0.55)
        if side == "R":
            on = on[::-1]
        edge = None
        if on.any():
            idx = int(np.argmax(on))
            if idx <= 0.02 * W:
                run_end, gap = idx, 0
                for i in range(idx, len(on)):
                    if on[i]:
                        run_end, gap = i, 0
                    else:
                        gap += 1
                        if gap > 0.01 * W:
                            break
                if run_end - idx + 1 >= 0.02 * W:
                    edge = (z_lo + run_end + 1) if side == "L" \
                        else (z_hi - run_end - 1)

        # -- 2) ornamental rule: innermost dense ink cluster in the zone --
        # (vclusters[0]/[-1] are the frame borders themselves)
        borders = set()
        if len(vclusters) >= 1:
            borders.add(vclusters[0])
        if len(vclusters) >= 2:
            borders.add(vclusters[-1])
        inner = [c for c in vclusters
                 if c not in borders and c[0] >= z_lo - 5 and c[1] <= z_hi + 5]
        rule = None
        if inner:
            if side == "L":
                c = max(inner, key=lambda t: t[1])
                rule = c[1]
            else:
                c = min(inner, key=lambda t: t[0])
                rule = c[0]

        # Prefer the rule edge: it is the strip's printed boundary and the
        # geometrically exact one. The chip-run edge is only a fallback (on
        # pale strips without colored entries); when a run bridges the rule
        # into topic-colored text it would clip text, so it must not win.
        if rule is not None:
            return rule
        return edge

    def refine(edge, side):
        """Walk from the edge toward the text, skipping the ornamental rule
        band and pale margin columns; stop at the first text-like column."""
        if edge is None:
            return None
        step = 2
        x = edge
        while (0 <= x < W) and (abs(x - edge) <= 0.08 * W):
            ink_d = cold[x:x + step].mean() if x + step <= W else cold[x]
            if ink_d >= 0.30:
                x += step if side == "L" else -step      # ornament band
                continue
            if ink_d < 0.06:
                x += step if side == "L" else -step      # pale margin
                continue
            return x                                     # text ink
        return edge                                      # bound hit

    clip_l = clip_r = None
    if even:
        clip_l = refine(side_edge("L"), "L")
    else:
        clip_r = refine(side_edge("R"), "R")
    return clip_l, clip_r


def band_ink_density(gray, band, x0, x1, th=160):
    """Ink fraction of a band within [x0, x1] — used to detect ornament
    bands (dense) vs text bands (sparse-moderate)."""
    b0, b1 = band
    x0 = max(0, x0)
    x1 = min(gray.shape[1], x1)
    if x1 <= x0:
        return 0.0
    ink = gray[b0:b1, x0:x1] < th
    return float(ink.mean())


def gold_map(a, sat_th=38):
    r = a[:, :, 0].astype(np.int32)
    g = a[:, :, 1].astype(np.int32)
    b = a[:, :, 2].astype(np.int32)
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    sat = mx - mn
    hue = np.where(mx == r, ((g - b) / np.maximum(mx - mn, 1) * 60 + 360) % 360,
                   np.where(mx == g, 60 * (2 + (b - r) / np.maximum(mx - mn, 1)),
                            60 * (4 + (r - g) / np.maximum(mx - mn, 1))))
    gold = ((hue >= 22) & (hue < 52) & (sat > sat_th) & (mx < 248))
    return np.where(gold, np.clip(sat, 0, 255), 0).astype(np.uint8)


def detect_markers(gm, tmpl, threshold=MATCH_THRESHOLD):
    res = cv2.matchTemplate(gm, tmpl, cv2.TM_CCOEFF_NORMED)
    loc = np.where(res >= threshold)
    pts = sorted(zip(loc[0], loc[1], res[loc[0], loc[1]]), key=lambda p: -p[2])
    kept = []
    for (py, px, s) in pts:
        if all(abs(py - ky) > NMS_PX or abs(px - kx) > NMS_PX for (ky, kx, _) in kept):
            kept.append((int(py), int(px), float(s)))
        if len(kept) >= 60:
            break
    return kept


# ---------------- db side ----------------


def db_page_data(con, page_no):
    cur = con.cursor()
    cur.execute(
        "SELECT line_number, sura_number, ayah_number, "
        "COUNT(*), MIN(position), MIN(min_x), MIN(min_y), MAX(max_x), MAX(max_y) "
        "FROM glyphs WHERE page_number=? "
        "GROUP BY line_number, sura_number, ayah_number "
        "ORDER BY line_number, MIN(position)", (page_no,))
    groups = cur.fetchall()
    cur.execute("SELECT DISTINCT sura_number, ayah_number FROM glyphs WHERE page_number=?",
                (page_no + 1,))
    nxt = set(cur.fetchall())
    return groups, nxt


# ---------------- segment construction ----------------


def build_page(con, page_no, tmpl, emit_overlays=False):
    img_path = os.path.join(PAGES_DIR, "page_%04d.webp" % page_no)
    if not os.path.exists(img_path):
        return None, {"error": "missing image"}
    im = Image.open(img_path).convert("RGB")
    a = np.array(im)
    gray = np.array(im.convert("L"))
    H, W = gray.shape
    bands, lh, (tx0, tx1), (fx0, fx1, vclusters) = uniform_bands_lh(gray)
    if not bands:
        return None, {"error": "no bands"}

    # Fihris clip: the marginal index column (left on even pages, right on
    # odd ones) stays OUT of the ayah segments, so the highlight never
    # covers it. Falls back to the plain ink extent when no strip is found.
    lo_b = min(b[0] for b in bands)
    hi_b = max(b[1] for b in bands)
    clip_l, clip_r = fihrist_clip_x(a, gray, page_no, fx0, fx1, vclusters,
                                     lo_b, hi_b)
    cx0 = tx0 if clip_l is None else max(tx0, clip_l + 2)
    cx1 = tx1 if clip_r is None else min(tx1, clip_r - 2)
    if cx1 - cx0 < 0.4 * W:                     # never trust a wild clip
        cx0, cx1 = tx0, tx1

    gm = gold_map(a)
    # the template contains a `pad` margin around the marker, so the match
    # position is offset: the marker's true box starts at (+pad, +pad).
    pad = CONFIRMED["pad"]
    w_m = CONFIRMED["w"]

    # reading order: band index, then right-to-left (x DESCENDING)
    def band_of(y):
        c = y + pad + CONFIRMED["h"] / 2.0
        best, bestd = None, None
        for k, (b0, b1) in enumerate(bands):
            if b0 - 0.30 * lh <= c <= b1 + 0.30 * lh:
                return k
            d = min(abs(c - b0), abs(c - b1))
            if bestd is None or d < bestd:
                best, bestd = k, d
        # snap to the nearest band if reasonably close
        if bestd is not None and bestd <= 0.6 * lh:
            return best
        return None

    def to_ordered(marks):
        ordered = []
        for (my, mx, s) in marks:
            k = band_of(my)
            if k is None:
                continue
            # store the marker's TRUE left edge (x + pad)
            ordered.append((k, -(mx + pad + w_m), my, mx + pad, s))
        ordered.sort()  # band asc, x desc
        return ordered

    ordered = to_ordered(detect_markers(gm, tmpl))

    groups, nxt = db_page_data(con, page_no)
    if not groups:
        return None, {"error": "no db data"}
    # ayahs on this page in reading order + their on-page WORD counts
    page_ayahs = []
    words_on_page = {}
    for (ln, s, a_no, cnt, pos, x0, y0, x1, y1) in groups:
        words_on_page[(s, a_no)] = words_on_page.get((s, a_no), 0) + cnt
        if (s, a_no) not in [p["k"] for p in page_ayahs]:
            page_ayahs.append({"k": (s, a_no), "cont": (s, a_no) in nxt})
    ending = [p for p in page_ayahs if not p["cont"]]

    info = {
        "markers": len(ordered),
        "ending_ayahs": len(ending),
        "bands": len(bands),
        # recorded for review: where the fihris clip landed on this page
        "fihris_l": None if clip_l is None else round(clip_l / float(W), 3),
        "fihris_r": None if clip_r is None else round(clip_r / float(W), 3),
    }
    # faded markers: retry once at the lower threshold when under-detected
    if 0 < len(ordered) < len(ending):
        marks2 = detect_markers(gm, tmpl, threshold=RETRY_THRESHOLD)
        ordered2 = to_ordered(marks2)
        if len(ordered2) >= len(ending):
            ordered = ordered2
            info["markers"] = len(ordered)
            info["recovered"] = True
    if len(ordered) > len(ending) and len(ending) > 0:
        # over-detection: real markers score far higher (0.8+) than
        # incidental ornament matches — keep the top `ending` by score.
        by_score = sorted(ordered, key=lambda t: -t[4])[:len(ending)]
        ordered = sorted(by_score)
        info["markers_pruned"] = len(ending)
    if len(ordered) != len(ending):
        info["count_mismatch"] = True
        return None, info

    # ---- assign markers to ending ayahs (reading order) ----
    # ordered[idx][3] holds the marker's TRUE left edge (x + pad).
    # Boundary ayahs (page-top start / page-bottom continuation) get their
    # line spans from the DB's on-page WORD counts (~9 words/line), so the
    # segments never spill into the ornamental frame bands at the extremes.
    WPL = 9.0
    segs_by_ayah = {}
    for idx, ay in enumerate(ending):
        k_end, x_end = ordered[idx][0], ordered[idx][3]
        # this ayah's text sits to the RIGHT of its end marker (RTL)
        mark_edge = x_end + 2
        # start boundary: previous marker (text resumes to ITS left); for the
        # page's first ayah, estimate its start line from its word count.
        if idx == 0:
            est = max(1, int(math.ceil(words_on_page.get(ay["k"], 9) / WPL)))
            est = min(est, k_end + 1)
            k_start = max(0, k_end - (est - 1))
            start_edge = cx1
        else:
            k_prev, x_prev = ordered[idx - 1][0], ordered[idx - 1][3]
            k_start, start_edge = k_prev, x_prev - 2
        segs = []
        if k_end == k_start:
            segs.append((k_start, mark_edge, start_edge))
        else:
            segs.append((k_start, cx0, start_edge))       # remainder of start band
            for k in range(k_start + 1, k_end):           # full intermediate bands
                segs.append((k, cx0, cx1))
            segs.append((k_end, mark_edge, cx1))          # up to the marker
        segs_by_ayah[ay["k"]] = segs

    # the continuing ayah (if any) spans after the last marker — bounded by
    # its on-page word count so the footer/frame bands stay outside.
    cont = [p for p in page_ayahs if p["cont"]]
    if cont:
        est = max(1, int(math.ceil(words_on_page.get(cont[0]["k"], 9) / WPL)))
        if ordered:
            k_last, x_last = ordered[-1][0], ordered[-1][3]
            segs = []
            for k in range(k_last, min(len(bands), k_last + est)):
                if k == k_last:
                    segs.append((k, cx0, x_last - 2))
                else:
                    segs.append((k, cx0, cx1))
        else:
            # an ayah spanning the entire page (no markers here)
            segs = [(k, cx0, cx1) for k in range(0, min(len(bands), est))]
        segs_by_ayah[cont[0]["k"]] = segs

    # ---- normalize ----
    ayahs_out = []
    for ay in page_ayahs:
        segs = segs_by_ayah.get(ay["k"])
        if not segs:
            continue
        seg_list = []
        for (k, xa, xb) in segs:
            b0, b1 = bands[k]
            x_lo, x_hi = min(xa, xb), max(xa, xb)
            seg_list.append([
                round(x_lo / W, 4), round(b0 / H, 4),
                round((x_hi - x_lo) / W, 4), round((b1 - b0) / H, 4),
            ])
        ayahs_out.append({"surah": ay["k"][0], "ayah": ay["k"][1],
                          "segments": seg_list})

    out = {"page": page_no, "width": W, "height": H,
           "ayahs": ayahs_out, "info": info}

    if emit_overlays:
        canvas = im.copy()
        dr = ImageDraw.Draw(canvas, "RGBA")
        pal = [(230, 25, 75), (60, 180, 75), (0, 130, 200), (245, 130, 48),
               (145, 30, 180), (70, 240, 240), (240, 50, 230), (210, 245, 60)]
        for (k, negx, my, mx, s) in ordered:
            # mx is the marker's TRUE left edge; my needs the pad offset
            dr.ellipse((mx - 8, my + pad - 8, mx + CONFIRMED["w"] + 8,
                        my + pad + CONFIRMED["h"] + 8),
                       outline=(255, 0, 0), width=3)
        for i, ay in enumerate(ayahs_out):
            col = pal[i % len(pal)]
            for (x, y, w, h) in ay["segments"]:
                dr.rectangle((x * W, y * H, (x + w) * W, (y + h) * H),
                             outline=col, width=3)
        os.makedirs(os.path.join(CACHE_DIR, "overlays"), exist_ok=True)
        canvas.save(os.path.join(CACHE_DIR, "overlays",
                                 "mwdoa_p%04d.png" % page_no))
    return out, info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--pages", type=str, default="")
    ap.add_argument("--overlays", action="store_true")
    args = ap.parse_args()

    db = ensure_db()
    con = sqlite3.connect(db)

    # template from the confirmed marker
    im = Image.open(os.path.join(
        PAGES_DIR, "page_%04d.webp" % CONFIRMED["page"])).convert("RGB")
    gm = gold_map(np.array(im))
    pad = CONFIRMED["pad"]
    x, y, w, h = CONFIRMED["x"], CONFIRMED["y"], CONFIRMED["w"], CONFIRMED["h"]
    tmpl = gm[max(0, y - pad):y + h + pad, max(0, x - pad):x + w + pad]
    print("template:", tmpl.shape)

    if args.all:
        targets = range(1, 605)
    elif args.pages:
        targets = [int(p) for p in args.pages.split(",")]
    else:
        targets = list(range(1, 605, 50)) + [2, 3, 50, 300, 400, 604]
        targets = sorted(set(targets))

    results = []
    mismatch = []
    for pg in targets:
        try:
            out, info = build_page(con, pg, tmpl, args.overlays)
        except Exception as e:
            out, info = None, {"error": str(e)}
        if out:
            results.append(out)
        if info.get("count_mismatch") or info.get("error"):
            mismatch.append((pg, info))
        print("page %3d: markers=%s ending=%s bands=%s%s"
              % (pg, info.get("markers"), info.get("ending_ayahs"),
                 info.get("bands"),
                 " MISMATCH" if info.get("count_mismatch") else ""))

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump({"pages": results}, f, ensure_ascii=False)
    print("\nwrote %s (%d pages OK)" % (OUT_PATH, len(results)))
    print("flagged pages (%d): %s" % (len(mismatch),
                                      [m[0] for m in mismatch[:40]]))


if __name__ == "__main__":
    main()
