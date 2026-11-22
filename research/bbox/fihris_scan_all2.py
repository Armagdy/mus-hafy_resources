# -*- coding: utf-8 -*-
"""Scan ALL mwdoa pages: locate the marginal fihrist strip per page (v2).

Two independent signals, cross-checked:
  1. COLOR strip: contiguous saturated-color column run (density > 0.55)
     adjacent to the INNER side of a frame border, covering >= 80% of the
     band rows vertically.
  2. DIVIDER line: a dense dark-ink vertical column cluster between the
     frame border and 30% inward (the text-area boundary line).
A page's clip edge = the divider x (validated by the color strip when
present). Reports side per page + boundary stats + disagreements.
"""
import json
import os
import numpy as np
from PIL import Image

PAGES_DIR = os.path.join("public", "assets", "mushuf_mwdoa_images")
OUT = os.path.join("temp", "bbox-research", "fihris_scan2.json")


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
    rh = float(r1 - r0)
    bink = ink[r0:r1]
    bsat = sat[r0:r1]
    cold = bink.sum(axis=0) / rh
    satd = bsat.sum(axis=0) / rh

    vclusters = _cluster_runs(cold > 0.35, gap=15, min_len=2)
    if len(vclusters) >= 2:
        fx0, fx1 = vclusters[0][1] + 10, vclusters[-1][0] - 10
        inner = vclusters[1:-1]
    else:
        fx0, fx1 = 0, W
        inner = []

    # --- divider candidates: inner clusters within 30% of a border ---
    div_l = [c for c in inner if c[0] < fx0 + 0.30 * W]
    div_r = [c for c in inner if c[1] > fx1 - 0.30 * W]
    div_l_x = div_l[-1][0] if div_l else None      # rightmost line = boundary
    div_r_x = div_r[0][1] if div_r else None

    # --- color strip adjacent to each border ---
    def color_strip(side):
        if side == "L":
            lo, hi = fx0, min(W, int(fx0 + 0.32 * W))
        else:
            lo, hi = max(0, int(fx1 - 0.32 * W)), fx1
        if hi - lo < 10:
            return None
        prof = satd[lo:hi]
        on = prof > 0.55
        if side == "R":
            on = on[::-1]
        idx = np.argmax(on) if on.any() else None
        if idx is None or idx > int(0.02 * W):
            return None
        run_end, gap = idx, 0
        for i in range(idx, len(on)):
            if on[i]:
                run_end, gap = i, 0
            else:
                gap += 1
                if gap > int(0.01 * W):
                    break
        width = run_end - idx + 1
        if width < int(0.04 * W):
            return None
        # vertical coverage of the strip band
        if side == "L":
            cols = bsat[:, lo + idx: lo + run_end + 1]
            inner_x = lo + run_end + 1
        else:
            cols = bsat[:, hi - run_end - 1: hi - idx]
            inner_x = hi - run_end - 1
        vcover = (cols.sum(axis=1) > (cols.shape[1] * 0.4)).mean()
        if vcover < 0.75:
            return None
        return {"inner_x": inner_x, "width": width,
                "peak": float(prof[idx:run_end + 1].max()), "vcover": float(vcover)}

    res = {"page": page_no, "fx0": fx0, "fx1": fx1, "W": W, "H": H,
           "div_l": div_l_x, "div_r": div_r_x,
           "cL": color_strip("L"), "cR": color_strip("R")}
    # combine: clip edge per side (color strip wins, divider as fallback)
    def edge(c, d):
        c_ok = c is not None
        d_ok = d is not None and (fx0 if d else fx1) is not None
        if c_ok:
            return c["inner_x"]
        if d_ok:
            return d
        return None
    res["clip_l"] = edge(res["cL"], res["div_l"])
    res["clip_r"] = edge(res["cR"], res["div_r"])
    return res


def main():
    results = []
    for p in range(1, 605):
        path = os.path.join(PAGES_DIR, "page_%04d.webp" % p)
        if not os.path.exists(path):
            continue
        results.append(analyze_page(p))
        if p % 100 == 0:
            print("...%d" % p)
    def plain(o):
        if isinstance(o, dict):
            return {k: plain(v) for k, v in o.items()}
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.floating,)):
            return float(o)
        return o
    json.dump([plain(r) for r in results], open(OUT, "w", encoding="utf-8"), indent=1)

    both = [r for r in results if r["clip_l"] is not None and r["clip_r"] is not None]
    only_l = [r for r in results if r["clip_l"] is not None and r["clip_r"] is None]
    only_r = [r for r in results if r["clip_l"] is None and r["clip_r"] is not None]
    none = [r for r in results if r["clip_l"] is None and r["clip_r"] is None]
    print("\ntotal %d  both=%d onlyL=%d onlyR=%d none=%d" %
          (len(results), len(both), len(only_l), len(only_r), len(none)))

    even_l = [r for r in only_l if r["page"] % 2 == 0]
    odd_l = [r for r in only_l if r["page"] % 2 == 1]
    even_r = [r for r in only_r if r["page"] % 2 == 0]
    odd_r = [r for r in only_r if r["page"] % 2 == 1]
    print("onlyL: even=%d odd=%d   onlyR: even=%d odd=%d" %
          (len(even_l), len(odd_l), len(even_r), len(odd_r)))
    if odd_l:
        print("  odd pages with L strip:", [r["page"] for r in odd_l][:30])
    if even_r:
        print("  even pages with R strip:", [r["page"] for r in even_r][:30])

    lb = [r["clip_l"] / r["W"] for r in only_l if r["clip_l"] is not None]
    rb = [r["clip_r"] / r["W"] for r in only_r if r["clip_r"] is not None]
    if lb:
        print("L clip edge: min=%.3f med=%.3f max=%.3f" % (min(lb), float(np.median(lb)), max(lb)))
    if rb:
        print("R clip edge: min=%.3f med=%.3f max=%.3f" % (min(rb), float(np.median(rb)), max(rb)))

    # divider vs color-strip agreement
    agree_l = disagree_l = agree_r = disagree_r = 0
    for r in results:
        if r["cL"] and r["div_l"] is not None:
            if abs(r["cL"]["inner_x"] - r["div_l"]) < 0.02 * r["W"]:
                agree_l += 1
            else:
                disagree_l += 1
        if r["cR"] and r["div_r"] is not None:
            if abs(r["cR"]["inner_x"] - r["div_r"]) < 0.02 * r["W"]:
                agree_r += 1
            else:
                disagree_r += 1
    print("divider/color agreement: L %d/%d  R %d/%d" %
          (agree_l, agree_l + disagree_l, agree_r, agree_r + disagree_r))

    print("\nnone pages:", [r["page"] for r in none][:60])
    print("both pages:", [r["page"] for r in both][:60])


main()
