# -*- coding: utf-8 -*-
"""
Extract the signature of the confirmed mwdoa ayah marker (the 2nd blue
circle from the top of the p300 diagnostic = G2), and compare with the other
golden candidates to see what distinguishes the real marker.

Also saves high-zoom crops of all golden candidates for reference.
"""
import numpy as np
from PIL import Image, ImageDraw
import cv2

DIR = r"D:\apps\quran\mushafy\public\assets\mushuf_mwdoa_images"
OUT = r"D:\apps\quran\mushafy\temp\bbox-research\mwdoa_golden_crops_p300.png"
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

r, g, b = a[:, :, 0], a[:, :, 1], a[:, :, 2]
mx = np.maximum(np.maximum(r, g), b)
mn = np.minimum(np.minimum(r, g), b)
sat = mx - mn
hue = np.where(mx == r, ((g - b) / np.maximum(mx - mn, 1) * 60 + 360) % 360,
               np.where(mx == g, 60 * (2 + (b - r) / np.maximum(mx - mn, 1)),
                        60 * (4 + (r - g) / np.maximum(mx - mn, 1))))
gold = ((hue >= 25) & (hue < 50) & (sat > 60) & (mx < 240)).astype(np.uint8)

n, labels, stats, cents = cv2.connectedComponentsWithStats(gold, 8)
cands = []
for i in range(1, n):
    x, y, w, h, area = stats[i]
    if h < 0.22 * lh or h > 1.15 * lh:
        continue
    if w < 0.22 * lh or w > 1.15 * lh:
        continue
    if w > h * 1.7 or h > w * 1.7:
        continue
    if area / float(w * h) < 0.20:
        continue
    cy = y + h / 2.0
    if not any(bb[0] - 8 <= cy <= bb[1] + 8 for bb in bands):
        continue
    # stats inside the component
    m = labels == i
    cmask = gold * m
    px = a[m & (gold > 0)]
    mean_col = px.mean(axis=0).astype(int)
    hmean = float(hue[m & (gold > 0)].mean())
    smean = float(sat[m & (gold > 0)].mean())
    cands.append({
        "x": int(x), "y": int(y), "w": int(w), "h": int(h),
        "area": int(area), "fill": round(area / float(w * h), 2),
        "col": tuple(int(c) for c in mean_col),
        "hue": round(hmean, 1), "sat": round(smean, 1),
    })

cands.sort(key=lambda c: (c["y"], c["x"]))
print("golden candidates on mwdoa p300 (sorted by y):")
for i, c in enumerate(cands):
    tag = "  <== G%d (user: 2nd from top = THE marker)" % (i + 1) if i == 1 else ""
    print("G%d: x=%4d y=%4d w=%3d h=%3d fill=%.2f hue=%.0f sat=%.0f col=%s%s"
          % (i + 1, c["x"], c["y"], c["w"], c["h"], c["fill"], c["hue"],
             c["sat"], c["col"], tag))

# distance from nearest band center, and band index
print("\nbands:", len(bands))
for i, c in enumerate(cands):
    cy = c["y"] + c["h"] / 2.0
    best = min(range(len(bands)), key=lambda k: abs((bands[k][0] + bands[k][1]) / 2 - cy))
    print("G%d -> band %d (center dist %.0f)" % (i + 1, best + 1,
          abs((bands[best][0] + bands[best][1]) / 2 - cy)))

# zoom crops of all candidates, G2 first and largest
Z = 6
crop_w = 160
strip = Image.new("RGB", (crop_w * len(cands) + 8 * (len(cands) + 1), 200),
                  (24, 26, 30))
sd = ImageDraw.Draw(strip)
xoff = 8
for i, c in enumerate(cands):
    cx = c["x"] + c["w"] // 2
    cy = c["y"] + c["h"] // 2
    box = (max(0, cx - crop_w // (2 * Z)), max(0, cy - 200 // (2 * Z)),
           min(W, cx + crop_w // (2 * Z)), min(H, cy + 200 // (2 * Z)))
    crop = im.crop(box).resize((crop_w, 200), Image.LANCZOS)
    strip.paste(crop, (xoff, 4))
    sd.rectangle((xoff, 4, xoff + crop_w, 204),
                 outline=(0, 255, 0) if i == 1 else (0, 80, 255), width=3)
    sd.text((xoff + 4, 0), "G%d" % (i + 1), fill=(255, 255, 255))
    xoff += crop_w + 8
strip.save(OUT)
print("saved:", OUT)
