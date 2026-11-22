# -*- coding: utf-8 -*-
"""
Compact diagnostic for mwdoa page 300:
  Panel 1/2: page top/bottom halves with line bands (cyan), strict black
             candidates (red circles, numbered), golden candidates (blue).
  Panel 3: 4x crops of the golden candidates.
User identifies which circles are the real ayah-end markers.
"""
import numpy as np
from PIL import Image, ImageDraw
import cv2

DIR = r"D:\apps\quran\mushafy\public\assets\mushuf_mwdoa_images"
OUT = r"D:\apps\quran\mushafy\temp\bbox-research\mwdoa_diag_p300_compact.png"
PAGE = 300

im = Image.open(DIR + "\\page_%04d.webp" % PAGE).convert("RGB")
a = np.array(im).astype(np.int32)
gray = np.array(im.convert("L"))
H, W = gray.shape

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


def blobs_in_bands(mask, min_fill, lo, hi, aspect):
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


black = blobs_in_bands(ink, 0.35, 0.30, 1.05, 1.5)

r, g, b = a[:, :, 0], a[:, :, 1], a[:, :, 2]
mx = np.maximum(np.maximum(r, g), b)
mn = np.minimum(np.minimum(r, g), b)
sat = mx - mn
hue = np.where(mx == r, ((g - b) / np.maximum(mx - mn, 1) * 60 + 360) % 360,
               np.where(mx == g, 60 * (2 + (b - r) / np.maximum(mx - mn, 1)),
                        60 * (4 + (r - g) / np.maximum(mx - mn, 1))))
gold = ((hue >= 25) & (hue < 50) & (sat > 60) & (mx < 240))
golden = blobs_in_bands(gold, 0.20, 0.22, 1.15, 1.7)
print("strict black candidates:", len(black))
print("golden candidates:", len(golden))
print("(expected ayah-end markers on this page if standard pagination: 8)")

canvas = im.copy()
dr = ImageDraw.Draw(canvas)
for (y0, y1) in bands:
    dr.line([(0, y0), (W, y0)], fill=(0, 200, 200), width=2)
    dr.line([(0, y1), (W, y1)], fill=(0, 200, 200), width=2)


def circle(dr, x, y, w, h, color, label):
    pad = 10
    dr.ellipse((x - pad, y - pad, x + w + pad, y + h + pad), outline=color, width=4)
    dr.text((x + w + pad + 2, y - 26), label, fill=color)


for i, (x, y, w, h) in enumerate(black):
    circle(dr, x, y, w, h, (255, 0, 0), "B%d" % (i + 1))
for i, (x, y, w, h) in enumerate(golden):
    circle(dr, x, y, w, h, (0, 80, 255), "G%d" % (i + 1))

# panels: top half, bottom half (native res), then golden crops strip
half = H // 2
p1 = canvas.crop((0, 0, W, half))
p2 = canvas.crop((0, half, W, H))

Z = 4
crop_w = int(lh * 1.7 * Z)
crop_h = crop_w
if golden:
    strip = Image.new("RGB", (crop_w * len(golden) + 10 * (len(golden) + 1),
                              crop_h + 40), (24, 26, 30))
    sd = ImageDraw.Draw(strip)
    xoff = 10
    for i, (x, y, w, h) in enumerate(golden):
        cx = max(0, x + w // 2 - crop_w // (2 * Z))
        cy = max(0, y + h // 2 - crop_h // (2 * Z))
        crop = im.crop((cx, cy, min(W, cx + crop_w // Z), min(H, cy + crop_h // Z)))
        crop = crop.resize((crop_w, crop_h), Image.LANCZOS)
        strip.paste(crop, (xoff, 34))
        sd.rectangle((xoff, 34, xoff + crop_w, 34 + crop_h),
                     outline=(0, 80, 255), width=3)
        sd.text((xoff + 6, 8), "G%d (x%d)" % (i + 1, Z), fill=(255, 255, 255))
        xoff += crop_w + 10
else:
    strip = Image.new("RGB", (W, 60), (24, 26, 30))

combo = Image.new("RGB", (W, p1.height + p2.height + strip.height + 24),
                  (255, 255, 255))
combo.paste(p1, (0, 0))
combo.paste(p2, (0, p1.height + 8))
combo.paste(strip, ((W - strip.width) // 2, p1.height + p2.height + 16))
combo.save(OUT)
print("saved:", OUT, combo.size)
