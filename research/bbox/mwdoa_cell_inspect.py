# -*- coding: utf-8 -*-
"""
Examine the newly confirmed mwdoa marker cell: row 11 (7th from bottom),
column 8 (3rd from left), page 300. Print its pixels as ASCII and find the
golden/compact candidates inside, then compare with G2.
"""
import numpy as np
from PIL import Image
import cv2

DIR = r"D:\apps\quran\mushafy\public\assets\mushuf_mwdoa_images"

im = Image.open(DIR + "\\page_0300.webp").convert("RGB")
a = np.array(im).astype(np.int32)
gray = np.array(im.convert("L"))
H, W = gray.shape

# bands (same pipeline)
ink = gray < 160
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
hs = [b[1] - b[0] for b in raw]
med = float(np.median(hs))
raw = [b for b in raw if (b[1] - b[0]) >= 0.45 * med]
lh = float(np.median([b[1] - b[0] for b in raw]))
bands = [(int(round((y0 + y1) / 2 - lh / 2)), int(round((y0 + y1) / 2 + lh / 2)))
         for (y0, y1) in raw]
print("bands: %d, lh=%.0f" % (len(bands), lh))
print("band 11 (7th from bottom):", bands[10])

# grid geometry (same as the diagnostic image)
x_left, x_right = 20, W - 20
ncol = 10
colw = (x_right - x_left) / ncol
# column 8 (3rd from left) spans:
cx0 = int(x_right - 8 * colw)
cx1 = int(x_right - 7 * colw)
by0, by1 = bands[10]
print("cell row11 col8: x %d..%d, y %d..%d" % (cx0, cx1, by0, by1))

r, g, b = a[:, :, 0], a[:, :, 1], a[:, :, 2]
mx = np.maximum(np.maximum(r, g), b)
mn = np.minimum(np.minimum(r, g), b)
sat = mx - mn
hue = np.where(mx == r, ((g - b) / np.maximum(mx - mn, 1) * 60 + 360) % 360,
               np.where(mx == g, 60 * (2 + (b - r) / np.maximum(mx - mn, 1)),
                        60 * (4 + (r - g) / np.maximum(mx - mn, 1))))
gold = ((hue >= 22) & (hue < 52) & (sat > 40) & (mx < 245)).astype(np.uint8)

print("\nASCII of the cell (1 char = 1 px): #=dark <150, +=gold, ~=mid, .=paper")
yy0 = max(0, by0 - 10)
yy1 = min(H, by1 + 10)
for yy in range(yy0, yy1):
    row = ""
    for xx in range(cx0, cx1):
        goldp = gold[yy, xx] > 0
        dark = gray[yy, xx] < 150
        mid = gray[yy, xx] < 215
        row += "#" if dark else ("+" if goldp else ("~" if mid else "."))
    print("  " + row)

# candidates inside the cell: golden components
n, labels, stats, cents = cv2.connectedComponentsWithStats(gold, 8)
print("\ngolden components overlapping this cell:")
for i in range(1, n):
    x, y, w, h, area = stats[i]
    if x + w < cx0 or x > cx1 or y + h < by0 - 6 or y > by1 + 6:
        continue
    print("  x=%4d y=%4d w=%3d h=%3d area=%4d fill=%.2f"
          % (x, y, w, h, area, area / float(w * h)))
