# -*- coding: utf-8 -*-
"""Validate the regenerated mwdoa bboxes against the OLD ones.

Checks:
  1. Same set of pages (OK pages and flagged pages unchanged).
  2. Same ayah entries (s/a) per page, same segment count per ayah.
  3. y/h of every segment unchanged.
  4. x changes are one-sided per parity: even pages may only move x0 up
     (fihris on the left), odd pages may only move x1 down (fihris on the
     right); the other edge must be identical.
  5. Clip sanity: even clip_l in [0.10, 0.35], odd clip_r in [0.65, 0.90].
"""
import json
import sys

OLD = json.load(open("temp/bbox-research/mwdoa_app_OLD.json", encoding="utf-8"))
NEW = json.load(open("public/assets/ayah-bboxes/mwdoa.json", encoding="utf-8"))

old_p, new_p = OLD["pages"], NEW["pages"]
print("pages: old=%d new=%d" % (len(old_p), len(new_p)))
print("page-set equal:", set(old_p) == set(new_p))
gone = set(old_p) - set(new_p)
added = set(new_p) - set(old_p)
if gone:
    print("  pages GONE in new:", sorted(gone, key=int)[:30])
if added:
    print("  pages ADDED in new:", sorted(added, key=int)[:30])

bad = []
clip_l_vals, clip_r_vals = [], []
moved_l = moved_r = 0
for p, entries in new_p.items():
    old_entries = old_p.get(p)
    if old_entries is None:
        continue
    if len(old_entries) != len(entries):
        bad.append((p, "entry-count %d->%d" % (len(old_entries), len(entries))))
        continue
    even = int(p) % 2 == 0
    for oe, ne in zip(old_entries, entries):
        if (oe["s"], oe["a"]) != (ne["s"], ne["a"]):
            bad.append((p, "ayah order %s->%s" % ((oe["s"], oe["a"]),
                                                  (ne["s"], ne["a"]))))
            continue
        if len(oe["seg"]) != len(ne["seg"]):
            bad.append((p, "seg count s%d:a%d %d->%d" %
                        (ne["s"], ne["a"], len(oe["seg"]), len(ne["seg"]))))
            continue
        for i, (os_, ns_) in enumerate(zip(oe["seg"], ne["seg"])):
            ox, oy, ow, oh = os_
            nx, ny, nw, nh = ns_
            if (oy, oh) != (ny, nh):
                bad.append((p, "y/h changed s%d:a%d#%d" % (ne["s"], ne["a"], i)))
                continue
            if (ox, ow) == (nx, nw):
                continue
            ox1, nx1 = round(ox + ow, 4), round(nx + nw, 4)
            if even:
                # fihris left: x0 may increase, x1 identical
                if nx > ox + 1e-9 and abs(nx1 - ox1) < 0.0005 and nx1 - nx > 0.02:
                    moved_l += 1
                    continue
                bad.append((p, "even x-change s%d:a%d#%d %.3f..%.3f -> %.3f..%.3f"
                            % (ne["s"], ne["a"], i, ox, ox1, nx, nx1)))
            else:
                if nx1 < ox1 - 1e-9 and abs(nx - ox) < 0.0005 and nx1 - nx > 0.02:
                    moved_r += 1
                    continue
                bad.append((p, "odd x-change s%d:a%d#%d %.3f..%.3f -> %.3f..%.3f"
                            % (ne["s"], ne["a"], i, ox, ox1, nx, nx1)))

print("segments narrowed on even pages (left clip): %d" % moved_l)
print("segments narrowed on odd pages (right clip): %d" % moved_r)
print("PROBLEMS: %d" % len(bad))
for b in bad[:40]:
    print("   ", b)

# clip positions from the research JSON info block
res = json.load(open("temp/bbox-research/mwdoa_ayah_bboxes.json", encoding="utf-8"))
info_l, info_r, none_pages = [], [], []
for pg in res["pages"]:
    inf = pg.get("info", {})
    even = pg["page"] % 2 == 0
    if even:
        v = inf.get("fihris_l")
        if v is None:
            none_pages.append(pg["page"])
        else:
            info_l.append((pg["page"], v))
    else:
        v = inf.get("fihris_r")
        if v is None:
            none_pages.append(pg["page"])
        else:
            info_r.append((pg["page"], v))

if info_l:
    vals = sorted(v for _, v in info_l)
    print("\nclip_l: n=%d min=%.3f med=%.3f max=%.3f" %
          (len(vals), vals[0], vals[len(vals) // 2], vals[-1]))
    outl = [(p, v) for p, v in info_l if not (0.10 <= v <= 0.35)]
    print("  outside [0.10,0.35]:", outl[:20])
if info_r:
    vals = sorted(v for _, v in info_r)
    print("clip_r: n=%d min=%.3f med=%.3f max=%.3f" %
          (len(vals), vals[0], vals[len(vals) // 2], vals[-1]))
    outr = [(p, v) for p, v in info_r if not (0.65 <= v <= 0.90)]
    print("  outside [0.65,0.90]:", outr[:20])
print("pages with NO clip:", none_pages[:30])

n_ayahs = sum(len(v) for v in new_p.values())
n_segs = sum(len(e["seg"]) for v in new_p.values() for e in v)
print("\nnew app json: pages=%d ayahs=%d segs=%d" % (len(new_p), n_ayahs, n_segs))
if bad:
    sys.exit(1)
print("\nVALIDATION OK")
