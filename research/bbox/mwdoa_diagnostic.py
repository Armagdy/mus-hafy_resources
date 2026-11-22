# -*- coding: utf-8 -*-
"""
Diagnostic image for mwdoa page 300:
  - full page with detected line bands (cyan),
  - BLACK compact-blob candidates circled RED + numbered,
  - GOLDEN (hue 25-50) compact-blob candidates circled BLUE + numbered,
  - a 4x zoom strip of every candidate at the bottom.
The user points at which circles are the real ayah-end markers.
"""
import numpy as np
from PIL import Image, ImageDraw
import cv2

DIR = r"D:\apps\quran\mushafy\public\assets\mushuf_mwdoa_images"
OUT = r"D:\apps\quran\mushafy\temp\bbox-research\mwdoa_diag_p300.png"
PAGE = 300

im = Image.open(DIR + "\\page_%04d.webp" % PAGE).convert("RGB")
a = np.array(im).astype(np.int32)
gray = np.array(im.convert("L"))
H, W = gray.shape

# --- line bands (gray<160) ---
ink = gray < 160
cold = ink.sum(axis=0) / H
keep = np.where(cold <= 0.4)[0]
inner = ink[:, keep]
rowd = inner.sum(axis=1) / inner.shape[1]
bands, in_b = [], False
for i, v in enumerate(rowd):
    if v > 0.03 and not in_b:
        st, in_b = i, True
    elif v <= 0.03 and in_b:
        if i - st > 25:
            bands.append((st, i))
        in_b = False
if in_b and H - st > 25:
    bands.append((st, H))
bands = [b for b in bands if b[0] > 5 and b[1] < H - 5]
if bands:
    hs = [b[1] - b[0] for b in bands]
    med = float(np.median(hs))
    bands = [b for b in bands if (b[1] - b[0]) >= 0.45 * med]
lh = float(np.median([b[1] - b[0] for b in bands])) if bands else 60
print("bands:", len(bands), "lh:", lh)

def blobs_in_bands(mask, min_fill=0.30, lo=0.22, hi=1.15, aspect=1.7):
    n, labels, stats, cents = cv2.connectedComponentsWithStats(mask.astype(np.uint8), 8)
    out = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if h < lo * lh or h > hi * lh:
            continue
        if w < lo * lh or w > hi * lh:
            continue
        if w > h * aspect or h > w * aspect:
            continue
        fill = area / float(w * h)
        if fill < min_fill:
            continue
        cy = y + h / 2.0
        if not any(b[0] - 8 <= cy <= b[1] + 8 for b in bands):
            continue
        out.append((int(x), int(y), int(w), int(h)))
    return out

# --- black candidates ---
black = blobs_in_bands(ink)

# --- golden candidates (hue 25-50, saturated) ---
r, g, b = a[:, :, 0], a[:, :, 1], a[:, :, 2]
mx = np.maximum(np.maximum(r, g), b)
mn = np.minimum(np.minimum(r, g), b)
sat = mx - mn
hue = np.zeros((H, W), np.float32)
hue = np.where(mx == r, ((g - b) / np.maximum(mx - mn, 1) * 60 + 360) % 360,
               np.where(mx == g, 60 * (2 + (b - r) / np.maximum(mx - mn, 1)),
                        60 * (4 + (r - g) / np.maximum(mx - mn, 1))))
gold = ((hue >= 25) & (hue < 50) & (sat > 60) & (mx < 240))
golden = blobs_in_bands(gold, min_fill=0.20)

print("black candidates:", len(black))
print("golden candidates:", len(golden))

canvas = im.copy()
dr = ImageDraw.Draw(canvas)

for (y0, y1) in bands:
    dr.line([(0, y0), (W, y0)], fill=(0, 200, 200), width=2)
    dr.line([(0, y1), (W, y1)], fill=(0, 200, 200), width=2)

def circle(dr, x, y, w, h, color, num):
    pad = 10
    dr.ellipse((x - pad, y - pad, x + w + pad, y + h + pad), outline=color, width=4)
    dr.text((x + w + pad + 2, y - 26), str(num), fill=color)

for i, (x, y, w, h) in enumerate(black):
    circle(dr, x, y, w, h, (255, 0, 0), i + 1)
for i, (x, y, w, h) in enumerate(golden):
    circle(dr, x, y, w, h, (0, 80, 255), i + 1)

# --- zoom strip ---
cands = ([("B%d" % (i + 1), (x, y, w, h), (255, 0, 0)) for i, (x, y, w, h) in enumerate(black)] +
         [("G%d" % (i + 1), (x, y, w, h), (0, 80, 255)) for i, (x, y, w, h) in enumerate(golden)])
Z = 4
pad = 24
crop_h = int(lh * 1.6) * Z
crop_w = crop_h
n = len(cands)
if n:
    strip = Image.new("RGB", (crop_w * n + 10 * (n + 1), crop_h + 40), (24, 26, 30))
    sd = ImageDraw.Draw(strip)
    xoff = 10
    for label, (x, y, w, h), col in cands:
        cx = max(0, x + w // 2 - crop_w // (2 * Z))
        cy = max(0, y + h // 2 - crop_h // (2 * Z))
        crop = im.crop((cx, cy, min(W, cx + crop_w // Z), min(H, cy + crop_h // Z)))
        crop = crop.resize((crop_w, crop_h), Image.LANCZOS)
        strip.paste(crop, (xoff, 34))
        sd.rectangle((xoff, 34, xoff + crop_w, 34 + crop_h), outline=col, width=3)
        sd.text((xoff + 6, 8), label, fill=(255, 255, 255))
        xoff += crop_w + 10
    total_w = max(canvas.width, strip.width)
    combo = Image.new("RGB", (total_w, canvas.height + strip.height + 10), (255, 255, 255))
    combo.paste(canvas, (0, 0))
    combo.paste(strip, ((total_w - strip.width) // 2, canvas.height + 10))
    combo.save(OUT)
    print("saved:", OUT, combo.size)
