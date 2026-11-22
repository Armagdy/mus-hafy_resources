# -*- coding: utf-8 -*-
"""
Bounded alignment test (frame-aware).

1. Detect the ornamental border frame bands on the local page image.
2. Text block = area inside the frame.
3. bbox-fit each candidate dataset's union -> text block, then refine with a
   *bounded* template-matching search (scale +-7%, translation +-6% of page)
   maximizing normalized cross-correlation between the dataset mask and ink.
4. Report NCC at optimum vs NCC when shifted by half a line height (control).
"""
import json
import sqlite3
import numpy as np
from PIL import Image
import cv2

PAGE_DIR = r"D:\apps\quran\mushafy\public\assets\mushaf_madinah_images"
WORK = r"D:\apps\quran\mushafy\temp\bbox-research"


def load_gray(page_no):
    return np.array(Image.open(PAGE_DIR + "\\page_%04d.webp" % page_no).convert("L"))


def detect_frame(ink, frac=0.30):
    """Return (top, bottom, left, right) band widths of the border frame."""
    H, W = ink.shape
    rows = ink.sum(axis=1) / W
    cols = ink.sum(axis=0) / H

    def band(profile, from_start, lim, thresh):
        n = 0
        idx = range(0, lim) if from_start else range(len(profile) - 1, len(profile) - lim - 1, -1)
        gap = 0
        for i in idx:
            if profile[i] > thresh:
                n = (i + 1) if from_start else (len(profile) - i)
                gap = 0
            else:
                gap += 1
                if gap > 25:   # allow small ornament gaps
                    break
        return n

    top = band(rows, True, int(H * 0.08), frac)
    bottom = band(rows, False, int(H * 0.08), frac)
    left = band(cols, True, int(W * 0.08), frac)
    right = band(cols, False, int(W * 0.08), frac)
    return top, bottom, left, right


def text_block(gray, thresh=205):
    ink = (gray < thresh).astype(np.uint8)
    H, W = ink.shape
    t, b, l, r = detect_frame(ink)
    pad = 6
    x0 = l + pad if l else 0
    y0 = t + pad if t else 0
    x1 = W - r - pad if r else W
    y1 = H - b - pad if b else H
    return (x0, y0, x1, y1), (t, b, l, r)


def dataset_mask_from_boxes(boxes):
    W = int(max(b[2] for b in boxes)) + 40
    H = int(max(b[3] for b in boxes)) + 40
    m = np.zeros((H, W), np.uint8)
    for (x0, y0, x1, y1) in boxes:
        cv2.rectangle(m, (int(x0), int(y0)), (int(x1), int(y1)), 1, -1)
    return m


def bbox_of(boxes):
    return (min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes))


def fit_bbox(src_bb, dst_bb):
    sx = (dst_bb[2] - dst_bb[0]) / float(src_bb[2] - src_bb[0])
    sy = (dst_bb[3] - dst_bb[1]) / float(src_bb[3] - src_bb[1])
    tx = dst_bb[0] - src_bb[0] * sx
    ty = dst_bb[1] - src_bb[1] * sy
    return sx, sy, tx, ty


def warp(mask, sx, sy, tx, ty, w, h):
    M = np.float32([[sx, 0, tx], [0, sy, ty]])
    return cv2.warpAffine(mask, M, (w, h), flags=cv2.INTER_NEAREST)


def ncc(a, b):
    a = a.astype(np.float32)
    b = b.astype(np.float32)
    if a.std() < 1e-6 or b.std() < 1e-6:
        return -1
    return float((a * b).mean() / (a.std() * b.std()))


def bounded_search(ink_img, mask, init, tb):
    """Scale candidates around bbox-fit; translation via matchTemplate window."""
    H, W = ink_img.shape
    sx0, sy0, tx0, ty0 = init
    best = (-2, None)
    win_x = int(W * 0.06)
    win_y = int(H * 0.06)
    for msx in (0.94, 0.97, 1.0, 1.03, 1.06):
        for msy in (0.94, 0.97, 1.0, 1.03, 1.06):
            sx, sy = sx0 * msx, sy0 * msy
            # template: the whole page-sized warp, cropped to content bbox
            full = warp(mask, sx, sy, tx0, ty0, W, H)
            ys, xs = np.where(full > 0)
            if len(xs) == 0:
                continue
            bx0, by0, bx1, by1 = xs.min(), ys.min(), xs.max(), ys.max()
            tmpl = full[by0:by1 + 1, bx0:bx1 + 1]
            if tmpl.shape[0] > H or tmpl.shape[1] > W:
                continue
            # search region: image padded conceptually; use matchTemplate on ink
            res = cv2.matchTemplate(ink_img, tmpl, cv2.TM_CCOEFF_NORMED)
            _, mx, _, loc = cv2.minMaxLoc(res)
            cand_tx = loc[0] - bx0
            cand_ty = loc[1] - by0
            # constrain near init translation
            if abs(cand_tx - tx0) > win_x or abs(cand_ty - ty0) > win_y:
                # fall back to init translation for this scale
                cand_tx, cand_ty = tx0, ty0
                placed = warp(mask, sx, sy, tx0, ty0, W, H)
                c = ncc(ink_img, placed)
            else:
                placed = warp(mask, sx, sy, cand_tx, cand_ty, W, H)
                c = ncc(ink_img, placed)
            if c > best[0]:
                best = (c, (sx, sy, cand_tx, cand_ty))
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


def main():
    pages = [(2, "p2.json"), (300, "p300.json")]
    db_path = WORK + "\\ayahinfo_1260.db"
    for page_no, jpath in pages:
        gray = load_gray(page_no)
        ink = (gray < 205).astype(np.uint8) * 255
        tb, frame = text_block(gray)
        print("\n=== page %d === size=%s frame(t,b,l,r)=%s text_block=%s" %
              (page_no, gray.shape[::-1], frame, tb))
        line_h = (tb[3] - tb[1]) / 15.0

        candidates = {
            "quran-ayah-coords": boxes_from_qac(jpath),
            "madani_1421_ayahinfo": boxes_from_db(db_path, page_no),
        }
        for name, boxes in candidates.items():
            src_bb = bbox_of(boxes)
            init = fit_bbox(src_bb, tb)
            mask = dataset_mask_from_boxes(boxes)
            c0 = ncc(ink, warp(mask, *init, gray.shape[1], gray.shape[0]))
            c, tf = bounded_search(ink, mask, init, tb)
            sx, sy, tx, ty = tf
            # half-line shift controls
            shifted = []
            for dty in (line_h * 0.5, -line_h * 0.5):
                shifted.append(ncc(ink, warp(mask, sx, sy, tx, ty + dty,
                                             gray.shape[1], gray.shape[0])))
            for dtx in (line_h * 0.5, -line_h * 0.5):
                shifted.append(ncc(ink, warp(mask, sx, sy, tx + dtx, ty,
                                             gray.shape[1], gray.shape[0])))
            print("  %-20s init NCC=%.3f best NCC=%.3f  shifted NCCs=%s" %
                  (name, c0, c, ["%.3f" % s for s in shifted]))
            print("     sx=%.4f sy=%.4f tx=%.1f ty=%.1f  (dataset page est. %dx%d)"
                  % (sx, sy, tx, ty, int(src_bb[2] * sx), int(src_bb[3] * sy)))

            # save overlay for the best transform
            from PIL import ImageDraw
            im = Image.open(PAGE_DIR + "\\page_%04d.webp" % page_no).convert("RGB")
            dr = ImageDraw.Draw(im, "RGBA")
            H, W = gray.shape
            for (x0, y0, x1, y1) in boxes:
                r = (x0 * sx + tx, y0 * sy + ty, x1 * sx + tx, y1 * sy + ty)
                dr.rectangle(r, outline=(230, 25, 75, 255), width=3)
            out = WORK + "\\overlay_p%d_%s.png" % (page_no, name)
            im.save(out)
            print("     overlay:", out)


if __name__ == "__main__":
    main()
