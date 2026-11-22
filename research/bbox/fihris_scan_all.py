# -*- coding: utf-8 -*-
"""Scan ALL mwdoa pages: locate the marginal fihrist strip per page.

For each page:
  - frame borders via dense dark-ink column clusters (same method as the
    generator's uniform_bands_lh)
  - saturated-color column profile over the band rows
  - a fihrist strip = contiguous color-density run (>0.5) adjacent to the
    inner side of a frame border; record side + inner boundary + width
Summary at the end: side per page, boundary stats, any page without a strip.
"""
import json
import os
import numpy as np
from PIL import Image

PAGES_DIR = os.path.join("public", "assets", "mushuf_mwdoa_images")
OUT = os.path.join("temp", "bbox-research", "fihris_scan.json")


def _cluster_runs(flags, gap, min_len):
    out, in_run, gap_left = [], False, 0
    for i, v in enumerate(flags):
        if v:
            if not in_run:
                st, in_run = i, True
            gap_left = 0
        elif in_run:
            gap_left += 1
            if gap_left >= gap:
                if i - gap_left - st >= min_len:
                    out.append((st, i - gap_left))
                in_run = False
    if in_run and len(flags) - st >= min_len:
        out.append((st, len(flags)))
    return out


def analyze_page(page_no):
    im = Image.open(os.path.join(PAGES_DIR, "page_%04d.webp" % page_no)).convert("RGB")
    a = np.array(im)
    H, W = a.shape[:2]
    gray = np.array(im.convert("L"))
    ink = gray < 160
    r, g, b = a[:, :, 0].astype(int), a[:, :, 1].astype(int), a[:, :, 2].astype(int)
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    sat = (mx - mn) > 40

    r0, r1 = int(H * 0.08), int(H * 0.96)
    bandrows_ink = ink[r0:r1]
    bandrows_sat = sat[r0:r1]
    rh = float(r1 - r0)
    cold = bandrows_ink.sum(axis=0) / rh
    satd = bandrows_sat.sum(axis=0) / rh

    vclusters = _cluster_runs(cold > 0.35, gap=15, min_len=2)
    if len(vclusters) >= 2:
        fx0, fx1 = vclusters[0][1] + 10, vclusters[-1][0] - 10
    else:
        fx0, fx1 = 0, W

    def strip_on(side):
        """contiguous sat-run (>0.5) starting adjacent to the frame border."""
        if side == "L":
            lo, hi = fx0, min(W, fx0 + int(0.38 * W))
            prof = satd[lo:hi]
        else:
            lo, hi = max(0, fx1 - int(0.38 * W)), fx1
            prof = satd[lo:hi]
        if len(prof) == 0:
            return None
        on = prof > 0.5
        # run must START within 2% of W of the border
        start_ok = 0
        for i in range(min(len(on), int(0.02 * W))):
            if on[i]:
                start_ok = i
                break
        else:
            # allow a short pale gap after the border
            if not on.any():
                return None
            start_ok = int(np.argmax(on))
            if start_ok > int(0.04 * W):
                return None
        # extend the run (tolerate small gaps)
        run_end = start_ok
        gap = 0
        for i in range(start_ok, len(on)):
            if on[i]:
                run_end = i
                gap = 0
            else:
                gap += 1
                if gap > int(0.01 * W):
                    break
        width = run_end - start_ok + 1
        if width < int(0.02 * W):
            return None
        if side == "L":
            return {"x0": (lo + start_ok) / W, "x1": (lo + run_end + 1) / W,
                    "peak": float(prof[start_ok:run_end + 1].max())}
        return {"x0": (hi - run_end - 1) / W, "x1": (hi - start_ok) / W,
                "peak": float(prof[start_ok:run_end + 1].max())}

    left = strip_on("L")
    right = strip_on("R")
    return {"page": page_no, "W": W, "H": H, "fx0": fx0 / W, "fx1": fx1 / W,
            "left": left, "right": right}


def main():
    results = []
    for p in range(1, 605):
        path = os.path.join(PAGES_DIR, "page_%04d.webp" % p)
        if not os.path.exists(path):
            continue
        results.append(analyze_page(p))
        if p % 100 == 0:
            print("...%d" % p)
    json.dump(results, open(OUT, "w", encoding="utf-8"), indent=1)

    both = [r for r in results if r["left"] and r["right"]]
    only_l = [r for r in results if r["left"] and not r["right"]]
    only_r = [r for r in results if r["right"] and not r["left"]]
    none = [r for r in results if not r["left"] and not r["right"]]
    print("\ntotal %d   both=%d onlyL=%d onlyR=%d none=%d" %
          (len(results), len(both), len(only_l), len(only_r), len(none)))

    print("\n-- parity check (even=L, odd=R) --")
    bad = [r for r in results
           if (r["page"] % 2 == 0 and not r["left"]) or
              (r["page"] % 2 == 1 and not r["right"])]
    print("parity-violations:", [r["page"] for r in bad][:40])

    lb = [r["left"]["x1"] for r in only_l]
    rb = [r["right"]["x0"] for r in only_r]
    if lb:
        print("L strip inner boundary x1: min=%.3f p25=%.3f med=%.3f p75=%.3f max=%.3f" %
              (min(lb), float(np.percentile(lb, 25)), float(np.median(lb)),
               float(np.percentile(lb, 75)), max(lb)))
    if rb:
        print("R strip inner boundary x0: min=%.3f p25=%.3f med=%.3f p75=%.3f max=%.3f" %
              (min(rb), float(np.percentile(rb, 25)), float(np.median(rb)),
               float(np.percentile(rb, 75)), max(rb)))

    print("\n-- outliers (boundary far from median) --")
    if lb:
        med = float(np.median(lb))
        for r in only_l:
            if abs(r["left"]["x1"] - med) > 0.06:
                print("  L p%d x1=%.3f peak=%.2f" % (r["page"], r["left"]["x1"], r["left"]["peak"]))
    if rb:
        med = float(np.median(rb))
        for r in only_r:
            if abs(r["right"]["x0"] - med) > 0.06:
                print("  R p%d x0=%.3f peak=%.2f" % (r["page"], r["right"]["x0"], r["right"]["peak"]))
    print("\nnone pages:", [r["page"] for r in none][:40])
    print("both pages:", [r["page"] for r in both][:40])


main()
