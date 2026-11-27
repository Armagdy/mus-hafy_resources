# -*- coding: utf-8 -*-
"""
Confirm the mwdoa page-373 ayah-box geometry by rendering exactly what the
app draws on top of the page image.

Replicates the app's highlight pipeline (src/lib/ayah-outline.ts +
SwiperPageDisplay.tsx, mwdoa style):
  - outlinePad { top: 0.002, bottom: 0.002 } (no x pad, no flushFlowEdges)
  - bridges between consecutive line strips that share an x-overlap
    (gap <= 0.08 of the page)
  - ONE unified outline per horizontally-connected run (union perimeter),
    stroked 2px green like the app

Usage:
  python confirm_p373_render.py <app_mwdoa.json> <out_dir> <label>
e.g.
  python confirm_p373_render.py ../mus-hafy_pwa/public/assets/ayah-bboxes/mwdoa.json \
         research/bbox/confirm_p373 BEFORE
"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont
import cv2

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
PAGE = 373

app_json = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(ROOT), "mus-hafy_pwa", "public", "assets",
    "ayah-bboxes", "mwdoa.json")
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
    ROOT, "research", "bbox", "confirm_p373")
LABEL = (sys.argv[3] if len(sys.argv) > 3 else "").strip("_ ") or ""
os.makedirs(OUT, exist_ok=True)
pfx = ("p373_%s_" % LABEL) if LABEL else "p373_"

im_path = os.path.join(ROOT, "assets", "mushuf_mwdoa_images",
                      "page_%04d.webp" % PAGE)
im = Image.open(im_path).convert("RGB")
W, H = im.size
data = json.load(open(app_json, encoding="utf-8"))
entries = data["pages"][str(PAGE)]

# ---- app constants (mwdoa) ----
PAD_TOP, PAD_BOT = 0.002, 0.002
BRIDGE_MAX_GAP = 0.08
STROKE = 2
GREEN = (21, 128, 61)


def font(sz):
    for p in ("C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/arial.ttf"):
        try:
            return ImageFont.truetype(p, sz)
        except Exception:
            pass
    try:
        return ImageFont.load_default(size=sz)
    except Exception:
        return ImageFont.load_default()


def app_rects(segs):
    rects = []
    for (x, y, w, h) in segs:
        x1, y1 = x * W, (y - PAD_TOP) * H
        x2, y2 = (x + w) * W, (y + h + PAD_BOT) * H
        if x2 <= x1 or y2 <= y1:
            continue
        rects.append((x1, y1, x2, y2))
    return rects


def app_bridges(rects):
    if len(rects) < 2:
        return []
    s = sorted(rects, key=lambda r: (r[1], r[0]))
    out = []
    for i in range(1, len(s)):
        p, q = s[i - 1], s[i]
        if q[1] < p[3]:
            continue
        if q[1] - p[3] > BRIDGE_MAX_GAP * H:
            continue
        lo, hi = max(p[0], q[0]), min(p[2], q[2])
        if hi - lo <= 1e-9 or q[1] - p[3] <= 0:
            continue
        out.append((lo, p[3], hi, q[1]))
    return out


def app_outline_contours(segs):
    rects = app_rects(segs)
    if not rects:
        return []
    mask = np.zeros((H, W), np.uint8)
    for (x1, y1, x2, y2) in rects + app_bridges(rects):
        cv2.rectangle(mask, (int(round(x1)), int(round(y1))),
                      (max(int(round(x2)) - 1, int(round(x1))),
                       int(round(y2)) - 1), 255, -1)
    conts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return [cv2.boxPoints(cv2.minAreaRect(c)) for c in conts]


def draw_outline(arr, segs, color=GREEN, width=STROKE):
    for box in app_outline_contours(segs):
        bx0, by0 = box.min(axis=0)
        bx1, by1 = box.max(axis=0)
        if bx1 - bx0 < 1.5:      # hairline loop: the app's stroke makes it a bar
            cv2.rectangle(arr, (int(bx0), int(by0)), (int(bx0) + 1, int(by1)),
                          color, width)
            continue
        pts = np.array([(round(x), round(y)) for (x, y) in box], np.int32)
        cv2.polylines(arr, [pts], True, color, width)


# ---------- 1) raw segments overview ----------
PAL = [(230, 25, 75), (60, 180, 75), (0, 130, 200), (245, 130, 48),
       (145, 30, 180), (70, 240, 240), (240, 50, 230), (210, 245, 60)]
c1 = im.copy()
d1 = ImageDraw.Draw(c1)
f_small = font(22)
for i, e in enumerate(entries):
    col = PAL[i % len(PAL)]
    for (x, y, w, h) in e["seg"]:
        d1.rectangle((x * W, y * H, (x + w) * W, (y + h) * H),
                     outline=col, width=3)
    x, y, w, h = e["seg"][0]
    d1.text((x * W + 6, (y + h) * H + 4), "%d:%d" % (e["s"], e["a"]),
            fill=col, font=f_small)
c1.save(os.path.join(OUT, pfx + "01_segments_raw.png"))
print("wrote %s01_segments_raw.png (%d ayahs)" % (pfx, len(entries)))

# ---------- 2) app-rendered outlines ----------
# the two regions that were corrupted (merged line pairs) + a normal ayah
SHOW = [(26, 137), (26, 138), (26, 139), (26, 140),
        (26, 153), (26, 154),
        (26, 145)]
c2arr = np.array(im)
for (s, a) in SHOW:
    e = next((t for t in entries if t["s"] == s and t["a"] == a), None)
    if not e:
        continue
    draw_outline(c2arr, e["seg"])
    loops = app_outline_contours(e["seg"])
    gray = np.array(im.convert("L"))
    print("ayah %d:%d -> %d outline loop(s):" % (s, a, len(loops)))
    for box in sorted(loops, key=lambda b: b[0][0]):
        bx0, by0 = box.min(axis=0)
        bx1, by1 = box.max(axis=0)
        reg = gray[int(by0):int(by1) + 1, int(bx0):int(bx1) + 1]
        ink = float((reg < 160).mean()) if reg.size else 0.0
        print("   x %7.1f..%7.1f  y %7.1f..%7.1f  (%4.0f x %.0f px)  ink=%.3f%s"
              % (bx0, bx1, by0, by1, bx1 - bx0, by1 - by0, ink,
                 "   <-- EMPTY ARTIFACT" if ink < 0.02 else ""))
c2 = Image.fromarray(c2arr)
d2 = ImageDraw.Draw(c2)
f_big = font(30)
for (s, a) in SHOW:
    e = next((t for t in entries if t["s"] == s and t["a"] == a), None)
    if not e:
        continue
    seg = max(e["seg"], key=lambda t: t[0] + t[2])
    d2.rectangle((seg[0] * W + 8, seg[1] * H - 44,
                  seg[0] * W + 160, seg[1] * H - 8), fill=(180, 0, 0))
    d2.text((seg[0] * W + 14, seg[1] * H - 42), "%d:%d" % (s, a),
            fill=(255, 255, 255), font=f_big)
c2.save(os.path.join(OUT, pfx + "02_app_outlines.png"))
print("wrote %s02_app_outlines.png (ayahs %s)" % (pfx, SHOW))

# ---------- 3) zoomed crops ----------
crops = []
f_z = font(26)


def crop(x0, x1, y0, y1, title, scale=3):
    x0, x1 = max(0, int(x0)), min(W, int(x1))
    y0, y1 = max(0, int(y0)), min(H, int(y1))
    c = c2.crop((x0, y0, x1, y1))
    c = c.resize(((x1 - x0) * scale, (y1 - y0) * scale), Image.LANCZOS)
    cd = ImageDraw.Draw(c)
    cd.text((18, 12), title, fill=(180, 0, 0), font=f_z)
    crops.append(c)


# the page top: lines 1-2 (the "first 4 ayahs" region)
crop(0, W, 30, 230, "page top: lines 1-2  (ayahs 26:137-140, 3x zoom)")
# the three former sliver spots (26:144 / 26:147 / 26:149 left-margin bars)
for (s, a) in [(26, 144), (26, 147), (26, 149)]:
    e = next((t for t in entries if t["s"] == s and t["a"] == a), None)
    if not e:
        continue
    seg = min(e["seg"], key=lambda t: t[1])   # top-most segment anchors the LINE
    by = (seg[1] + seg[3] / 2) * H
    crop(-0.02 * W, 0.26 * W, by - 0.075 * H, by + 0.075 * H,
         "ayah %d:%d  (3x zoom, left page margin)" % (s, a))
# the second corrupted region: lines 10-11 (ayahs 26:152-155)
crop(0, W, 830, 1030, "lines 10-11  (ayahs 26:152-155, 3x zoom)")

gap = 14
wsum = max(c.width for c in crops)
hsum = sum(c.height for c in crops) + gap * (len(crops) - 1)
stack = Image.new("RGB", (wsum, hsum), (255, 255, 255))
oy = 0
for c in crops:
    stack.paste(c, (0, oy))
    oy += c.height + gap
stack.save(os.path.join(OUT, pfx + "03_zoom_crops.png"))
print("wrote %s03_zoom_crops.png (%d stacked crops)" % (pfx, len(crops)))
