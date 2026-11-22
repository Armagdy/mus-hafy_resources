# -*- coding: utf-8 -*-
"""
Decisive alignment test between a coordinate dataset and the local madinah images.

Approach: treat the dataset's boxes as a binary mask, binarize the local page,
then search the axis-aligned affine (sx, sy, tx, ty) that maximizes the
fraction of dataset-mask area landing on ink. Compare candidates:
  A) quran-ayah-coords (old Madani scan, ayah-level boxes)
  B) quran.com madani_1421 ayahinfo_1260.db (glyph boxes, digital 1421 print)

If a candidate aligns, the best score should clearly beat the "shifted control"
(the same mask nudged off by half a line height) and the other candidate.
"""
import json
import sqlite3
import zipfile
import urllib.request
import numpy as np
from PIL import Image
import cv2

PAGE_DIR = r"D:\apps\quran\mushafy\public\assets\mushaf_madinah_images"
WORK = r"D:\apps\quran\mushafy\temp\bbox-research"


def load_image(page_no):
    p = PAGE_DIR + "\\page_%04d.webp" % page_no
    g = np.array(Image.open(p).convert("L"))
    return g


def ink_mask(gray, thresh=205):
    return (gray < thresh).astype(np.uint8)


def dataset_mask_from_boxes(boxes):
    """boxes: list of (x0,y0,x1,y1). Returns mask + its canvas size."""
    W = int(max(b[2] for b in boxes)) + 40
    H = int(max(b[3] for b in boxes)) + 40
    m = np.zeros((H, W), np.uint8)
    for (x0, y0, x1, y1) in boxes:
        cv2.rectangle(m, (int(x0), int(y0)), (int(x1), int(y1)), 1, -1)
    return m


def transform_mask(mask, sx, sy, tx, ty, out_w, out_h):
    M = np.float32([[sx, 0, tx], [0, sy, ty]])
    return cv2.warpAffine(mask, M, (out_w, out_h), flags=cv2.INTER_NEAREST)


def score(ink, mask, sx, sy, tx, ty):
    H, W = ink.shape
    t = transform_mask(mask, sx, sy, tx, ty, W, H)
    area = t.sum()
    if area == 0:
        return 0.0
    return float((t & ink).sum()) / float(area)


def fit_bbox(src_bb, dst_bb):
    sx = (dst_bb[2] - dst_bb[0]) / float(src_bb[2] - src_bb[0])
    sy = (dst_bb[3] - dst_bb[1]) / float(src_bb[3] - src_bb[1])
    tx = dst_bb[0] - src_bb[0] * sx
    ty = dst_bb[1] - src_bb[1] * sy
    return sx, sy, tx, ty


def text_block_bbox(ink, min_density_frac=0.02):
    """Bbox of the text block, ignoring thin frame lines.
    Frame lines = rows/cols with very high ink run-length; remove them via
    morphology with long kernels, then take the remaining ink bbox."""
    H, W = ink.shape
    # remove long horizontal lines
    hk = cv2.morphologyology = None
    opened_h = cv2.morphologyEx(ink, cv2.MORPH_OPEN,
                                cv2.getStructuringElement(cv2.MORPH_RECT, (W // 8, 1)))
    opened_v = cv2.morphologyEx(ink, cv2.MORPH_OPEN,
                                cv2.getStructuringElement(cv2.MORPH_RECT, (1, H // 12)))
    cleaned = ink & ~opened_h & ~opened_v
    ys, xs = np.where(cleaned > 0)
    if len(xs) == 0:
        return (0, 0, W, H)
    return (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))


def optimize(ink, mask, init, iters=3):
    """Coarse-to-fine local search around the bbox-fit transform."""
    sx, sy, tx, ty = init
    H, W = ink.shape
    # scale steps relative
    best = score(ink, mask, sx, sy, tx, ty)
    for it in range(iters):
        ranges = [
            (0.9, 1.11, 11),   # sx, sy multipliers
        ]
        found = False
        for fs in [0.06, 0.03, 0.012, 0.005]:
            for msx in np.linspace(1 - fs, 1 + fs, 7):
                for msy in np.linspace(1 - fs, 1 + fs, 7):
                    for dtx in np.linspace(-fs * W, fs * W, 5):
                        for dty in np.linspace(-fs * H, fs * H, 5):
                            s = score(ink, mask, sx * msx, sy * msy, tx + dtx, ty + dty)
                            if s > best + 1e-6:
                                best = s
                                sx, sy, tx, ty = sx * msx, sy * msy, tx + dtx, ty + dty
                                found = True
        if not found:
            break
    return best, (sx, sy, tx, ty)


def boxes_from_qac_json(path):
    d = json.load(open(path, encoding="utf-8"))
    return [(b["min_x"], b["min_y"], b["max_x"], b["max_y"]) for b in d]


def boxes_from_db(db_path, page_no, group_line=True):
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute(
        "SELECT line_number, sura_number, ayah_number, position, "
        "min_x, min_y, max_x, max_y FROM glyphs WHERE page_number=? "
        "ORDER BY line_number, position", (page_no,))
    rows = cur.fetchall()
    con.close()
    if group_line:
        # group glyphs by (line, sura, ayah) -> one box per ayah-line segment
        out = []
        cur_group = None
        for (line, sura, ayah, pos, x0, y0, x1, y1) in rows:
            key = (line, sura, ayah)
            if key != cur_group:
                cur_group = key
                out.append([x0, y0, x1, y1])
            else:
                b = out[-1]
                b[0] = min(b[0], x0); b[1] = min(b[1], y0)
                b[2] = max(b[2], x1); b[3] = max(b[3], y1)
        return [tuple(b) for b in out]
    return [(r[4], r[5], r[6], r[7]) for r in rows]


def main():
    pages = [(2, "p2.json"), (300, "p300.json")]

    # download + extract ayahinfo_1260
    import os
    zip_path = WORK + "\\ayahinfo_1260.zip"
    db_path = WORK + "\\ayahinfo_1260.db"
    if not os.path.exists(db_path):
        urllib.request.urlretrieve(
            "https://files.quran.app/hafs/madani_1421/databases/ayahinfo/ayahinfo_1260.zip",
            zip_path)
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(WORK)
        print("extracted:", z.namelist())

    for page_no, jpath in pages:
        gray = load_image(page_no)
        ink = ink_mask(gray)
        tb = text_block_bbox(ink)
        print("\n=== page %d === image %s text-block(est) %s" %
              (page_no, gray.shape[::-1], tb))

        candidates = {
            "quran-ayah-coords(old scan)": boxes_from_qac_json(jpath),
            "madani_1421 ayahinfo(glyphs)": boxes_from_db(db_path, page_no),
        }
        for name, boxes in candidates.items():
            mask = dataset_mask_from_boxes(boxes)
            src_bb = (min(b[0] for b in boxes), min(b[1] for b in boxes),
                      max(b[2] for b in boxes), max(b[3] for b in boxes))
            init = fit_bbox(src_bb, tb)
            s0 = score(ink, mask, *init)
            s_best, tf = optimize(ink, mask, init)
            # shifted control: nudge by ~half line height vertically
            line_h = (tb[3] - tb[1]) / 15.0
            sx, sy, tx, ty = tf
            s_shift = max(score(ink, mask, sx, sy, tx, ty + line_h * 0.5),
                          score(ink, mask, sx, sy, tx, ty - line_h * 0.5),
                          score(ink, mask, sx, sy, tx + (tb[2]-tb[0]) * 0.06, ty),
                          score(ink, mask, sx, sy, tx - (tb[2]-tb[0]) * 0.06, ty))
            print("  %-32s bboxfit=%.3f  best=%.3f  shifted-control=%.3f  margin=%.2fx"
                  % (name, s0, s_best, s_shift, s_best / max(s_shift, 1e-9)))
            print("     transform: sx=%.4f sy=%.4f tx=%.1f ty=%.1f" % tf)


if __name__ == "__main__":
    main()
