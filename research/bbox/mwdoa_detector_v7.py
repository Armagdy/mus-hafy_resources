# -*- coding: utf-8 -*-
"""
mwdoa detector v7 — built on the now-visible marker structure:
  a large GOLDEN DIAMOND medallion (~0.5-1.0 x line height, 50-66 px) with a
  DARK rosette pattern inside. Faded gold included (sat > 38).

Checks:
  1. Around the first confirmed position (G2 x=147 y=824) there should be a
     full-size medallion (G2 was a fragment).
  2. Per-page counts vs expected ayah ends.
"""
import importlib.util
import os
import sqlite3

import numpy as np
from PIL import Image
import cv2

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
spec = importlib.util.spec_from_file_location(
    "gen", os.path.join(ROOT, "scripts", "generate_ayah_bboxes.py"))
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)

PAGES_DIR = os.path.join(ROOT, "public", "assets", "mushuf_mwdoa_images")


def masks(a):
    r = a[:, :, 0].astype(np.int32)
    g = a[:, :, 1].astype(np.int32)
    b = a[:, :, 2].astype(np.int32)
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    sat = mx - mn
    hue = np.where(mx == r, ((g - b) / np.maximum(mx - mn, 1) * 60 + 360) % 360,
                   np.where(mx == g, 60 * (2 + (b - r) / np.maximum(mx - mn, 1)),
                            60 * (4 + (r - g) / np.maximum(mx - mn, 1))))
    gold = ((hue >= 22) & (hue < 52) & (sat > 38) & (mx < 248)).astype(np.uint8)
    dark = (mx < 150).astype(np.uint8)
    return gold, dark


def uniform_bands_lh(gray, th=160):
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
        return [], 0
    hs = [b[1] - b[0] for b in raw]
    med = float(np.median(hs))
    raw = [b for b in raw if (b[1] - b[0]) >= 0.45 * med]
    lh = float(np.median([b[1] - b[0] for b in raw]))
    bands = [(int(round((y0 + y1) / 2 - lh / 2)), int(round((y0 + y1) / 2 + lh / 2)))
             for (y0, y1) in raw]
    return bands, lh


def detect(a, bands, lh, dark_ratio_min=0.06, dark_th=150):
    """Golden medallions: large gold components containing dark rosette pixels."""
    gold, dark = masks(a)
    H, W = gold.shape
    n, labels, stats, cents = cv2.connectedComponentsWithStats(gold, 8)
    out = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if w < 0.35 * lh or w > 1.35 * lh:
            continue
        if h < 0.40 * lh or h > 1.35 * lh:
            continue
        ar = h / float(w)
        if ar < 0.55 or ar > 2.2:
            continue
        fill = area / float(w * h)
        if fill < 0.10 or fill > 0.60:
            continue
        cy = y + h / 2.0
        if not any(bb[0] - 10 <= cy <= bb[1] + 10 for bb in bands):
            continue
        # dark pixels INSIDE the component's bbox
        m = labels == i
        inside_dark = float((dark[y:y + h, x:x + w] & m[y:y + h, x:x + w]).sum())
        box_area = float(w * h)
        if inside_dark / box_area < dark_ratio_min:
            continue
        out.append({
            "x": int(x), "y": int(y), "w": int(w), "h": int(h),
            "fill": round(fill, 2),
            "dark_in": round(inside_dark / box_area, 3),
        })
    return out


def expected_counts(con):
    cur = con.cursor()
    page_keys = {}
    for pg in range(1, 605):
        cur.execute("SELECT DISTINCT sura_number, ayah_number FROM glyphs WHERE page_number=?", (pg,))
        page_keys[pg] = set(cur.fetchall())
    ends = {}
    for pg in range(1, 604):
        ends[pg] = len(page_keys[pg] - page_keys[pg + 1])
    ends[604] = len(page_keys[604])
    return ends


def main():
    # check around the first confirmed marker (G2 x=147 y=824)
    im = Image.open(os.path.join(PAGES_DIR, "page_0300.webp")).convert("RGB")
    a = np.array(im)
    gray = np.array(im.convert("L"))
    bands, lh = uniform_bands_lh(gray)
    marks = detect(a, bands, lh)
    print("p300 detected medallions:", len(marks))
    for m in marks:
        tag = ""
        if abs(m["x"] - 147) < 40 and abs(m["y"] - 824) < 50:
            tag = "  <== near first confirmed (G2)"
        if abs(m["x"] - 239) < 20 and abs(m["y"] - 972) < 20:
            tag = "  <== second confirmed (row11 col8)"
        print("   x=%4d y=%4d %2dx%2d fill=%.2f dark_in=%.3f%s"
              % (m["x"], m["y"], m["w"], m["h"], m["fill"], m["dark_in"], tag))

    # count validation across a sample
    con = sqlite3.connect(gen.ensure_db())
    ends = expected_counts(con)
    sample = list(range(3, 605, 9))
    exact = 0
    deltas = []
    for pg in sample:
        im = Image.open(os.path.join(PAGES_DIR, "page_%04d.webp" % pg)).convert("RGB")
        a = np.array(im)
        gray = np.array(im.convert("L"))
        bands, lh = uniform_bands_lh(gray)
        marks = detect(a, bands, lh)
        e = ends.get(pg, 0)
        deltas.append(len(marks) - e)
        if len(marks) == e:
            exact += 1
    import collections
    dist = collections.Counter(deltas)
    print("\nsampled %d pages: exact %d (%.0f%%)" % (len(sample), exact, 100 * exact / len(sample)))
    print("delta distribution:", dict(sorted(dist.items())))


main()
