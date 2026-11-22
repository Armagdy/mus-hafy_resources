# -*- coding: utf-8 -*-
"""
mwdoa marker detector v3: TEMPLATE MATCHING using the user-confirmed marker
(G2 on page 300, bbox x=147 y=824 w=18 h=26).

Method:
  1. Convert pages to a "gold intensity" map: hue in [25,50] -> saturation,
     everything else -> 0. Golden ornaments survive; black text and paper
     vanish.
  2. Template = the G2 marker's gold map (padded slightly).
  3. matchTemplate (TM_CCOEFF_NORMED) over the page; peaks above a threshold
     with non-max suppression = markers.
  4. Validate per-page counts against the expected ayah-end counts.
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
# confirmed marker on page 300
G2 = dict(page=300, x=147, y=824, w=18, h=26)


def gold_map(a):
    """hue 25-50 -> saturation value; else 0. uint8 image."""
    r = a[:, :, 0].astype(np.int32)
    g = a[:, :, 1].astype(np.int32)
    b = a[:, :, 2].astype(np.int32)
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    sat = (mx - mn).astype(np.int32)
    hue = np.where(mx == r, ((g - b) / np.maximum(mx - mn, 1) * 60 + 360) % 360,
                   np.where(mx == g, 60 * (2 + (b - r) / np.maximum(mx - mn, 1)),
                            60 * (4 + (r - g) / np.maximum(mx - mn, 1))))
    gold = ((hue >= 25) & (hue < 50) & (sat > 45) & (mx < 245))
    out = np.where(gold, np.clip(sat, 0, 255), 0).astype(np.uint8)
    return out


def load_template():
    im = Image.open(os.path.join(
        PAGES_DIR, "page_%04d.webp" % G2["page"])).convert("RGB")
    a = np.array(im)
    gm = gold_map(a)
    x, y, w, h = G2["x"], G2["y"], G2["w"], G2["h"]
    pad = 6
    x0 = max(0, x - pad)
    y0 = max(0, y - pad)
    x1 = min(gm.shape[1], x + w + pad)
    y1 = min(gm.shape[0], y + h + pad)
    tmpl = gm[y0:y1, x0:x1]
    return tmpl, (x0, y0, x1, y1)


def detect(gm, tmpl, threshold=0.55, nms=20):
    res = cv2.matchTemplate(gm, tmpl, cv2.TM_CCOEFF_NORMED)
    loc = np.where(res >= threshold)
    pts = sorted(zip(loc[1], loc[0], res[loc[0], loc[1]]),
                 key=lambda p: -p[2])
    kept = []
    for (y, x, s) in pts:
        if all(abs(y - ky) > nms or abs(x - kx) > nms for (ky, kx, _) in kept):
            kept.append((y, x, float(s)))
        if len(kept) > 80:
            break
    return kept, res


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
    tmpl, tbox = load_template()
    print("template box on p300:", tbox, "size:", tmpl.shape)
    con = sqlite3.connect(gen.ensure_db())
    ends = expected_counts(con)

    # sanity: on page 300 itself, do the peaks look like the 8 markers?
    for pg in (300, 3, 50, 120, 400):
        im = Image.open(os.path.join(
            PAGES_DIR, "page_%04d.webp" % pg)).convert("RGB")
        gm = gold_map(np.array(im))
        kept, res = detect(gm, tmpl)
        exp = ends.get(pg, 0)
        scores = [round(k[2], 2) for k in kept[:20]]
        print("\npage %3d: detected=%2d expected=%2d  top scores=%s"
              % (pg, len(kept), exp, scores))
        if pg == 300:
            for (y, x, s) in kept[:12]:
                print("   marker at x=%d y=%d score=%.2f" % (x, y, s))
    # threshold sweep on the sample
    print("\nthreshold sweep (count pages where detected==expected):")
    sample = list(range(3, 605, 25))
    for th in (0.5, 0.55, 0.6, 0.65, 0.7):
        m = 0
        det = []
        for pg in sample:
            im = Image.open(os.path.join(
                PAGES_DIR, "page_%04d.webp" % pg)).convert("RGB")
            gm = gold_map(np.array(im))
            kept, _ = detect(gm, tmpl, threshold=th)
            e = ends.get(pg, 0)
            det.append(len(kept) - e)
            if len(kept) == e:
                m += 1
        import collections
        dist = collections.Counter(det)
        print("  th=%.2f: exact %d/%d  delta-dist %s"
              % (th, m, len(sample), dict(sorted(dist.items()))))


main()
