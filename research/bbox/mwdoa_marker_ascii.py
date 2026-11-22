# -*- coding: utf-8 -*-
"""
Print the user-confirmed mwdoa marker (G2 on page 300) as 1:1 pixel ASCII:
'+' = golden hue (22-52, sat>40), '#' = dark ink, '.' = paper.
Print the core 18x26 plus margins, and a few zoomed-out rows of context.
"""
import numpy as np
from PIL import Image

DIR = r"D:\apps\quran\mushafy\public\assets\mushuf_mwdoa_images"

im = Image.open(DIR + "\\page_0300.webp").convert("RGB")
a = np.array(im).astype(np.int32)
gray = np.array(im.convert("L")).astype(np.int32)
H, W = gray.shape

r, g, b = a[:, :, 0], a[:, :, 1], a[:, :, 2]
mx = np.maximum(np.maximum(r, g), b)
mn = np.minimum(np.minimum(r, g), b)
sat = mx - mn
hue = np.where(mx == r, ((g - b) / np.maximum(mx - mn, 1) * 60 + 360) % 360,
               np.where(mx == g, 60 * (2 + (b - r) / np.maximum(mx - mn, 1)),
                        60 * (4 + (r - g) / np.maximum(mx - mn, 1))))


def show(x0, y0, x1, y1, step=1):
    print("region x %d..%d  y %d..%d (1 char = %d px)" % (x0, x1, y0, y1, step))
    for yy in range(y0, y1, step):
        row = ""
        for xx in range(x0, x1, step):
            goldp = (22 <= hue[yy, xx] < 52) and sat[yy, xx] > 40
            dark = gray[yy, xx] < 150
            mid = gray[yy, xx] < 215 and not goldp
            row += "#" if dark else ("+" if goldp else ("~" if mid else "."))
        print("  " + row)


print("=== THE CONFIRMED MARKER (G2 core, x=147..165, y=824..850) ===")
show(139, 816, 173, 856)
print()
print("=== wider context (same marker, 2x downsample) ===")
show(110, 800, 210, 880, step=2)
