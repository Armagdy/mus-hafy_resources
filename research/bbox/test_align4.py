# -*- coding: utf-8 -*-
"""
1-D profile matching per axis.

Their page's row/col ink profiles are the geometric fingerprint of the print
(15 text lines, margin edges). Each candidate dataset implies an expected
profile (from its boxes). We find (scale, shift) per axis that maximizes
normalized correlation, bounded to sane ranges, and report how sharp the
peak is. A true edition match gives a sharp peak at a sane scale; a mismatch
gives a flat, noisy correlation.
"""
import json
import sqlite3
import numpy as np
from PIL import Image, ImageDraw
import cv2

PAGE_DIR = r"D:\apps\quran\mushafy\public\assets\mushaf_madinah_images"
WORK = r"D:\apps\quran\mushafy\temp\bbox-research"


def load_gray(page_no):
    return np.array(Image.open(PAGE_DIR + "\\page_%04d.webp" % page_no).convert("L"))


def smooth(v, k=9):
    return cv2.GaussianBlur(v.astype(np.float32), (k, 1), 0).flatten() if v.ndim == 1 else v


def norm01(v):
    v = v.astype(np.float32)
    rng = v.max() - v.min()
    return (v - v.min()) / (rng if rng > 1e-9 else 1.0)


def best_corr(target, pattern):
    """Slide `pattern` (shorter or equal) over `target`; return best NCC and shift."""
    t = target.astype(np.float32)
    p = pattern.astype(np.float32)
    n = len(p)
    if n > len(t):
        return -1, 0
    best = (-2, 0)
    tm = t.mean()
    ps = p.std()
    if ps < 1e-6:
        return -1, 0
    for s in range(0, len(t) - n + 1, 1):
        w = t[s:s + n]
        denom = (w.std() * ps * n)
        if denom < 1e-6:
            continue
        c = float(((w - w.mean()) * (p - p.mean())).sum() / denom)
        if c > best[0]:
            best = (c, s)
    return best


def match_axis(img_profile, boxes_profile_fn, lo=0.85, hi=1.15, steps=31):
    """Search scale s.t. rescaled dataset profile matches image profile."""
    best = (-2, None)  # (corr, scale, shift)
    L = len(img_profile)
    for sc in np.linspace(lo, hi, steps):
        # dataset profile rendered at this scale, to length L*sc-ish:
        base = boxes_profile_fn  # callable returning (profile, src_len)
        prof, src_len = base()
        target_len = max(20, int(round(src_len * sc)))
        if target_len > L:
            continue
        prof_s = cv2.resize(prof.reshape(-1, 1).astype(np.float32),
                           (1, target_len), interpolation=cv2.INTER_AREA).flatten()
        c, shift = best_corr(img_profile, prof_s)
        if c > best[0]:
            best = (c, sc, shift, target_len)
    return best


def boxes_from_qac(path):
    d = json.load(open(path, encoding="utf-8"))
    return [(b["min_x"], b["min_y"], b["max_x"], b["max_y"]) for b in d]


def boxes_from_db(db_path, page_no):
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute(
        "SELECT line_number, sura_number, ayah_number, min_x, min_y, max_x, max_y "
        "FROM glyphs WHERE page_number=? ORDER BY line_number, position", (page_no,))
    rows = cur.fetchall()
    con.close()
    out = []
    cur_group = None
    for (line, sura, ayah, x0, y0, x1, y1) in rows:
        key = (line, sura, ayah)
        if key != cur_group:
            cur_group = key
            out.append([x0, y0, x1, y1])
        else:
            b = out[-1]
            b[0] = min(b[0], x0); b[1] = min(b[1], y0)
            b[2] = max(b[2], x1); b[3] = max(b[3], y1)
    return [tuple(b) for b in out]


def run(page_no, name, boxes, gray):
    H, W = gray.shape
    ink = (gray < 205).astype(np.float32)
    col_prof = norm01(smooth(ink.sum(axis=0)))
    row_prof = norm01(smooth(ink.sum(axis=1)))

    def x_profile():
        L = int(max(b[2] for b in boxes)) + 20
        p = np.zeros(L, np.float32)
        for (x0, y0, x1, y1) in boxes:
            p[int(x0):int(x1) + 1] += 1
        return norm01(smooth(p)), L

    def y_profile():
        L = int(max(b[3] for b in boxes)) + 20
        p = np.zeros(L, np.float32)
        for (x0, y0, x1, y1) in boxes:
            p[int(y0):int(y1) + 1] += 1
        return norm01(smooth(p)), L

    cx = match_axis(col_prof, x_profile)
    cy = match_axis(row_prof, y_profile)
    print("  %-20s X: corr=%.3f scale=%.3f shift=%d | Y: corr=%.3f scale=%.3f shift=%d"
          % (name, cx[0], cx[1], cx[2], cy[0], cy[1], cy[2]))

    # build the implied transform: dataset coord -> image coord
    if cx[0] > 0 and cy[0] > 0:
        # target_len = src_len*scale, mapped onto image axis starting at `shift`
        def mk(src_len, sc, shift):
            def f(v):
                return v * sc + shift
            return f
        fx = mk(0, cx[1], cx[2])
        fy = mk(0, cy[1], cy[2])
        im = Image.open(PAGE_DIR + "\\page_%04d.webp" % page_no).convert("RGB")
        dr = ImageDraw.Draw(im, "RGBA")
        for (x0, y0, x1, y1) in boxes:
            dr.rectangle((fx(x0), fy(y0), fx(x1), fy(y1)),
                         outline=(230, 25, 75, 255), width=3)
        out = WORK + "\\overlay_p%d_%s_1d.png" % (page_no, name)
        im.save(out)
        print("     overlay:", out)
    return cx, cy


def main():
    db_path = WORK + "\\ayahinfo_1260.db"
    for page_no, jpath in [(2, "p2.json"), (300, "p300.json")]:
        gray = load_gray(page_no)
        print("\n=== page %d ===" % page_no)
        run(page_no, "quran-ayah-coords", boxes_from_qac(jpath), gray)
        run(page_no, "madani_1421_ayahinfo", boxes_from_db(db_path, page_no), gray)


if __name__ == "__main__":
    main()
