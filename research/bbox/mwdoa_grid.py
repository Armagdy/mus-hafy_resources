# -*- coding: utf-8 -*-
"""
Grid diagnostic for mwdoa page 300: uniform line bands (confirmed correct)
+ 10 vertical columns. Rows numbered 1..17 at the right margin, columns
numbered 1..10 from RIGHT (RTL reading order). The user reports cells like
"9-3" that contain the end-of-ayah marker.
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFont

DIR = r"D:\apps\quran\mushafy\public\assets\mushuf_mwdoa_images"
OUT = r"D:\apps\quran\mushafy\temp\bbox-research\mwdoa_grid_p300.png"
PAGE = 300

im = Image.open(DIR + "\\page_%04d.webp" % PAGE).convert("RGB")
W, H = im.size
gray = np.array(im.convert("L"))

# uniform bands (same as validated pipeline)
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
print("bands:", len(bands))

canvas = im.copy()
dr = ImageDraw.Draw(canvas)

try:
    font = ImageFont.truetype("arial.ttf", 30)
    small = ImageFont.truetype("arial.ttf", 24)
except Exception:
    font = ImageFont.load_default()
    small = font

# vertical columns over the text width: 10 columns between x=20 and W-20
x_left, x_right = 20, W - 20
ncol = 10
colw = (x_right - x_left) / ncol
# band y-extent for the grid
y_top = bands[0][0] - 20
y_bot = bands[-1][1] + 20

# draw column separators (light) and column numbers at top (from RIGHT)
for c in range(ncol + 1):
    xx = int(x_left + c * colw)
    dr.line([(xx, y_top), (xx, y_bot)], fill=(120, 120, 120), width=1)
# column labels: col 1 at the RIGHT
for c in range(1, ncol + 1):
    # column c spans which x?
    x0 = int(x_right - c * colw)
    x1 = int(x_right - (c - 1) * colw)
    dr.text(((x0 + x1) // 2 - 10, y_top - 44), str(c), fill=(200, 0, 200), font=font)

# row labels at the right margin + band boundary lines
for k, (y0, y1) in enumerate(bands):
    dr.line([(x_left, y0), (x_right, y0)], fill=(0, 190, 190), width=1)
    dr.line([(x_left, y1), (x_right, y1)], fill=(0, 190, 190), width=1)
    dr.text((x_right + 6, (y0 + y1) // 2 - 14), str(k + 1), fill=(200, 0, 200), font=small)

canvas.save(OUT)
print("saved:", OUT, canvas.size)
