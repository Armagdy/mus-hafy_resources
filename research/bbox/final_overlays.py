# -*- coding: utf-8 -*-
"""
Final overlay generator: draw each candidate dataset's ayah boxes on the local
madinah pages using a sane, frame-aware bbox-fit, and report ink-coverage stats.

Candidates:
  A. quran-ayah-coords          (classic Madani scan, ayah boxes)
  B. old-1405 ayahinfo_1260.db  (classic Madani scan, glyph boxes grouped
                                 per ayah-line)
  C. quran-ws hafs-kfqc         (1441H print, ayah polygons)

Output: overlay PNGs in temp/bbox-research + coverage numbers.
The user eyeballs which overlay locks onto the text.
"""
import json
import re
import sqlite3
import numpy as np
from PIL import Image, ImageDraw
import cv2

LOCAL = r"D:\apps\quran\mushafy\public\assets\mushaf_madinah_images"
WORK = r"D:\apps\quran\mushafy\temp\bbox-research"

PALETTE = [
    (230, 25, 75), (60, 180, 75), (0, 130, 200), (245, 130, 48),
    (145, 30, 180), (70, 240, 240), (240, 50, 230), (210, 245, 60),
    (255, 215, 180), (0, 128, 128), (220, 190, 255), (170, 110, 40),
]


def text_block(gray, thresh=205):
    """Detect the text block: ink bands that do NOT touch the image edges
    (edge-touching dense bands = ornamental frame)."""
    ink = (gray < thresh).astype(np.float32)
    H, W = ink.shape
    rowd = ink.sum(axis=1) / W
    cold = ink.sum(axis=0) / H

    def bands(profile, limit, min_frac, edge_guard):
        out = []
        in_b = False
        for i, v in enumerate(profile):
            if v > min_frac and not in_b:
                st = i; in_b = True
            elif v <= min_frac and in_b:
                out.append((st, i)); in_b = False
        if in_b:
            out.append((st, len(profile)))
        keep = []
        for (st, en) in out:
            # drop only *thin* dense edge bands (ornamental frame strips)
            if (en - st) < 0.06 * len(profile) and (st < edge_guard or en > len(profile) - edge_guard):
                if max(profile[st:en]) > 0.35:
                    continue
            keep.append((st, en))
        if not keep:  # fallback: everything except outer 2%
            keep = [(int(len(profile) * 0.02), int(len(profile) * 0.98))]
        return min(a for a, b in keep), max(b for a, b in keep)

    y0, y1 = bands(rowd, H, 0.02, 14)
    x0, x1 = bands(cold, W, 0.02, 14)
    return (int(x0), int(y0), int(x1), int(y1))


def parse_poly(p):
    nums = [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", p)]
    xs = nums[0::2]; ys = nums[1::2]
    return min(xs), min(ys), max(xs), max(ys)


def load_candidates(page_no):
    cands = {}
    # A: quran-ayah-coords
    d = json.load(open(WORK + "\\p%d.json" % page_no, encoding="utf-8"))
    items = [((b["surah_number"], b["ayah_number"]),
              (b["min_x"], b["min_y"], b["max_x"], b["max_y"])) for b in d]
    cands["A_quran-ayah-coords"] = items
    # B: old madani glyph db grouped per ayah-line
    con = sqlite3.connect(WORK + "\\ayahinfo_1260.db")
    cur = con.cursor()
    cur.execute(
        "SELECT line_number, sura_number, ayah_number, min_x, min_y, max_x, max_y "
        "FROM glyphs WHERE page_number=? ORDER BY line_number, position", (page_no,))
    groups = {}
    order = []
    for (ln, s, a, x0, y0, x1, y1) in cur.fetchall():
        k = (ln, s, a)
        if k not in groups:
            groups[k] = [x0, y0, x1, y1]
            order.append((k, (s, a)))
        else:
            g = groups[k]
            g[0] = min(g[0], x0); g[1] = min(g[1], y0)
            g[2] = max(g[2], x1); g[3] = max(g[3], y1)
    con.close()
    cands["B_old1405_glyphdb"] = [(ay, tuple(groups[k])) for k, ay in order]
    # C: quran-ws polygons
    d3 = json.load(open(WORK + "\\qw_p%03d.json" % page_no, encoding="utf-8"))
    cands["C_quranws_1441"] = [
        ((e["surahNumber"], e["ayahNumber"]), parse_poly(e["polygon"])) for e in d3]
    return cands


def coverage(gray, rects, thresh=205):
    ink = (gray < thresh)
    tot = 0
    hit = 0
    for r in rects:
        x0 = max(0, int(r[0])); y0 = max(0, int(r[1]))
        x1 = min(gray.shape[1], int(r[2])); y1 = min(gray.shape[0], int(r[3]))
        if x1 <= x0 or y1 <= y0:
            continue
        sub = ink[y0:y1, x0:x1]
        tot += sub.size
        hit += sub.sum()
    return hit / float(max(tot, 1))


def run(page_no):
    gray = np.array(Image.open(LOCAL + "\\page_%04d.webp" % page_no).convert("L"))
    tb = text_block(gray)
    ink = (gray < 205)
    tb_cov = ink[tb[1]:tb[3], tb[0]:tb[2]].mean()
    print("\n=== page %d ===  size=%s  text_block=%s  (band ink coverage %.3f)"
          % (page_no, gray.shape[::-1], tb, tb_cov))

    cands = load_candidates(page_no)
    for name, items in cands.items():
        boxes = [b for _, b in items]
        src = (min(b[0] for b in boxes), min(b[1] for b in boxes),
               max(b[2] for b in boxes), max(b[3] for b in boxes))
        sx = (tb[2] - tb[0]) / float(src[2] - src[0])
        sy = (tb[3] - tb[1]) / float(src[3] - src[1])
        tx = tb[0] - src[0] * sx
        ty = tb[1] - src[1] * sy
        rects = [(b[0] * sx + tx, b[1] * sy + ty, b[2] * sx + tx, b[3] * sy + ty)
                 for b in boxes]
        cov = coverage(gray, rects)
        print("  %-20s scale=(%.3f,%.3f)  box ink coverage=%.3f  vs band %.3f  ratio=%.2f"
              % (name, sx, sy, cov, tb_cov, cov / max(tb_cov, 1e-9)))

        im = Image.open(LOCAL + "\\page_%04d.webp" % page_no).convert("RGB")
        dr = ImageDraw.Draw(im, "RGBA")
        akeys = []
        for (ay, b) in items:
            if ay not in akeys:
                akeys.append(ay)
        for (ay, b) in items:
            col = PALETTE[akeys.index(ay) % len(PALETTE)]
            dr.rectangle((b[0] * sx + tx, b[1] * sy + ty,
                          b[2] * sx + tx, b[3] * sy + ty), outline=col, width=3)
        out = WORK + "\\FINAL_overlay_p%d_%s.png" % (page_no, name)
        im.save(out)
        print("     overlay ->", out)


if __name__ == "__main__":
    for p in (2, 300):
        run(p)
