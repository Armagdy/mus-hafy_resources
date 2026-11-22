# -*- coding: utf-8 -*-
"""ASCII-dump the ink around predicted ayah-end positions so we can see
what the madinah end-of-ayah marker looks like pixel-wise."""
import json
import os
import sqlite3
import sys

import numpy as np
from PIL import Image

ROOT = r"D:\apps\quran\mushafy"
PAGES_DIR = os.path.join(ROOT, "public", "assets", "mushaf_madinah_images")
con = sqlite3.connect(os.path.join(ROOT, "temp", "bbox-research",
                                   "ayahinfo_classic_1260.db"))

res = json.load(open(os.path.join(ROOT, "temp", "bbox-research",
                                  "madinah_ayah_bboxes.json"), encoding="utf-8"))
by_page = {p["page"]: p for p in res["pages"]}


def dump(pg, ln, x_center, half=45, cell=3):
    p = by_page[pg]
    tr = p["transform"]
    sx, tx = tr["sx"], tr["tx"]
    gray = np.array(Image.open(os.path.join(
        PAGES_DIR, "page_%04d.webp" % pg)).convert("L"))
    H, W = gray.shape
    ink = gray < 205
    # band rows for this line: use the emitted y for a segment on that line
    x0 = int(max(0, x_center - half))
    x1 = int(min(W - 1, x_center + half))
    # find the band rows: reuse page_geometry
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    from generate_ayah_bboxes import page_geometry
    (c0, c1), bands, _, _ = page_geometry(gray, 205)
    a, b = bands[ln - 1]
    a = max(0, a - 8)
    b = min(H, b + 8)
    print("p%d line %d rows %d..%d, x %d..%d" % (pg, ln, a, b, x0, x1))
    hdr = "     " + "".join(str((x0 + i * cell) // 10 % 10)
                            for i in range(0, (x1 - x0) // cell + 1))
    print(hdr)
    for yy in range(a, b, 2):
        row = ""
        for xx in range(x0, x1, cell):
            blk = ink[yy:yy + 2, xx:xx + cell]
            frac = blk.mean()
            row += " " if frac < 0.15 else ("." if frac < 0.4 else
                                           ("+" if frac < 0.7 else "#"))
        print("%4d %s" % (yy, row))


# p564 line 2: end of 67:27 (continuation segment ends mid-line, db x~752)
cur = con.cursor()
cur.execute("""SELECT MIN(min_x) FROM glyphs WHERE page_number=564
               AND line_number=2 AND sura_number=67 AND ayah_number=27""", )
x_end = cur.fetchone()[0]
tr = by_page[564]["transform"]
sx, tx = tr["sx"], tr["tx"]
wx = x_end * sx + tx
print("predicted end of 67:27 on line 2: db_x=%s -> img x=%.0f" % (x_end, wx))
dump(564, 2, wx)
con.close()
