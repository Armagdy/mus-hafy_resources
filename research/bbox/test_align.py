# -*- coding: utf-8 -*-
"""
Alignment test: do the quran-ayah-coords boxes (old Madani scan) match
the local mushaf_madinah_images pages?

Method:
  1. Load local page image, compute ink bbox (non-white pixels), with several
     inset levels (to see whether an ornamental border frame is present).
  2. Load dataset boxes for the page, compute their union bbox.
  3. Fit an axis-aligned affine (sx, sy, tx, ty) mapping dataset space -> image
     space so that the dataset union bbox maps onto the image ink bbox.
  4. Score: mean darkness inside transformed boxes vs page mean darkness.
     A good alignment should make box interiors much darker than average.
  5. Draw colored overlays (one color per ayah) for visual inspection.
"""
import json
import sys
from PIL import Image, ImageDraw, ImageStat

PAGE_DIR = r"D:\apps\quran\mushafy\public\assets\mushaf_madinah_images"
OUT_DIR = r"D:\apps\quran\mushafy\temp\bbox-research"

PALETTE = [
    (230, 25, 75), (60, 180, 75), (0, 130, 200), (245, 130, 48),
    (145, 30, 180), (70, 240, 240), (240, 50, 230), (210, 245, 60),
    (250, 190, 190), (0, 128, 128), (220, 190, 255), (170, 110, 40),
    (255, 250, 200), (128, 0, 0), (170, 255, 195), (128, 128, 0),
    (255, 215, 180), (0, 0, 128), (128, 128, 128), (255, 255, 255),
]


def ink_bbox(im, inset_frac=0.0, thresh=245):
    """Bounding box of dark pixels, optionally ignoring a margin inset."""
    g = im.convert("L")
    w, h = g.size
    if inset_frac > 0:
        x0 = int(w * inset_frac)
        y0 = int(h * inset_frac)
        g = g.crop((x0, y0, w - x0, h - y0))
    bw = g.point(lambda p: 255 if p < thresh else 0)
    bb = bw.getbbox()
    if bb is None:
        return None
    if inset_frac > 0:
        x0 = int(w * inset_frac)
        y0 = int(h * inset_frac)
        bb = (bb[0] + x0, bb[1] + y0, bb[2] + x0, bb[3] + y0)
    return bb


def load_boxes(path):
    d = json.load(open(path, encoding="utf-8"))
    return d


def union(boxes):
    x0 = min(b["min_x"] for b in boxes)
    y0 = min(b["min_y"] for b in boxes)
    x1 = max(b["max_x"] for b in boxes)
    y1 = max(b["max_y"] for b in boxes)
    return (x0, y0, x1, y1)


def fit(src_bb, dst_bb):
    sx = (dst_bb[2] - dst_bb[0]) / (src_bb[2] - src_bb[0])
    sy = (dst_bb[3] - dst_bb[1]) / (src_bb[3] - src_bb[1])
    tx = dst_bb[0] - src_bb[0] * sx
    ty = dst_bb[1] - src_bb[1] * sy
    return sx, sy, tx, ty


def transform(box, s):
    sx, sy, tx, ty = s
    return (
        box[0] * sx + tx,
        box[1] * sy + ty,
        box[2] * sx + tx,
        box[3] * sy + ty,
    )


def darkness(im, rects):
    """Mean luminance inside rects (lower = more ink)."""
    vals = []
    for r in rects:
        r = (max(0, int(r[0])), max(0, int(r[1])),
             min(im.width, int(r[2])), min(im.height, int(r[3])))
        if r[2] <= r[0] or r[3] <= r[1]:
            continue
        st = ImageStat.Stat(im.crop(r))
        vals.append(st.mean[0])
    return sum(vals) / max(1, len(vals))


def run(page_no, json_path):
    img_path = PAGE_DIR + "\\page_%04d.webp" % page_no
    im = Image.open(img_path).convert("RGB")
    gray = im.convert("L")
    print("\n=== page %d ===" % page_no)
    print("image size:", im.size)
    page_mean = ImageStat.Stat(gray).mean[0]
    print("page mean luminance: %.1f" % page_mean)

    for inset in (0.0, 0.02, 0.04, 0.06):
        bb = ink_bbox(gray, inset)
        print("  ink bbox (inset %.0f%%): %s  w=%d h=%d" %
              (inset * 100, bb, bb[2] - bb[0], bb[3] - bb[1]))

    boxes = load_boxes(json_path)
    src = union(boxes)
    print("dataset entries: %d, dataset union: %s (w=%d h=%d)" %
          (len(boxes), src, src[2] - src[0], src[3] - src[1]))

    results = []
    for inset in (0.0, 0.02, 0.04, 0.06):
        dst = ink_bbox(gray, inset)
        s = fit(src, dst)
        rects = [transform((b["min_x"], b["min_y"], b["max_x"], b["max_y"]), s)
                 for b in boxes]
        d = darkness(gray, rects)
        results.append((inset, d, s, dst))
        print("  fit inset %.0f%% -> darkness in boxes: %.1f (page %.1f, gain %.2fx)"
              % (inset * 100, d, page_mean, page_mean / max(d, 1e-6)))

    # best = lowest darkness (most ink inside boxes)
    best_inset, best_d, best_s, best_dst = min(results, key=lambda r: r[1])
    print("  BEST inset: %.0f%% (darkness %.1f)" % (best_inset * 100, best_d))

    # overlay for visual check: draw each dataset box, colored per ayah
    s = best_s
    draw_im = im.copy()
    dr = ImageDraw.Draw(draw_im, "RGBA")
    ayahs = []
    for b in boxes:
        key = (b["surah_number"], b["ayah_number"])
        if key not in ayahs:
            ayahs.append(key)
    for b in boxes:
        key = (b["surah_number"], b["ayah_number"])
        col = PALETTE[ayahs.index(key) % len(PALETTE)]
        r = transform((b["min_x"], b["min_y"], b["max_x"], b["max_y"]), s)
        dr.rectangle(r, outline=col, width=3)
    out = OUT_DIR + "\\overlay_p%d_quran-ayah-coords.png" % page_no
    draw_im.save(out)
    print("  saved:", out)
    return best_d, page_mean


if __name__ == "__main__":
    for page_no, j in [(2, "p2.json"), (300, "p300.json")]:
        run(page_no, j)
    print("\nInterpretation: gain >> 1 (e.g. box darkness < 120 vs page ~200+) means")
    print("the boxes land on text -> the dataset matches this edition/print.")
