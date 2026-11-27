# -*- coding: utf-8 -*-
"""Validate the multi-scale regeneration of the mwdoa boxes.

Checks, against the previous run (mwdoa_ayah_bboxes_prev_multiscale.json):
  1. no regression: every previously-emitted page must still be emitted;
  2. identity: per-page ayah key list must be unchanged (DB-derived);
  3. geometry: which pages' segments moved, and by how much — expected on
     gap-filled / recovered / pruned pages, a red flag on plain pages;
  4. the recovered pages (previously flagged) listed for the review gallery.

Run after scripts/generate_ayah_bboxes_mwdoa.py --all."""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CACHE = os.path.join(ROOT, "research", "bbox")

OLD = json.load(open(os.path.join(CACHE, "mwdoa_ayah_bboxes_prev_multiscale.json"),
                     encoding="utf-8"))
NEW = json.load(open(os.path.join(CACHE, "mwdoa_ayah_bboxes.json"), encoding="utf-8"))

old_pages = {p["page"]: p for p in OLD["pages"]}
new_pages = {p["page"]: p for p in NEW["pages"]}

regress = sorted(set(old_pages) - set(new_pages))
recovered = sorted(set(new_pages) - set(old_pages))
print("old pages: %d   new pages: %d" % (len(old_pages), len(new_pages)))
print("recovered (previously flagged): %s" % recovered)
print("REGRESSIONS (previously OK, now missing): %s  %s"
      % (regress, "<-- MUST BE EMPTY" if regress else "(none)"))

EPS = 0.002          # ~2-3 px on a 1110px-wide page
moved_pages = []
key_mismatch = []
for pg in sorted(set(old_pages) & set(new_pages)):
    o, n = old_pages[pg], new_pages[pg]
    okeys = [(a["surah"], a["ayah"]) for a in o["ayahs"]]
    nkeys = [(a["surah"], a["ayah"]) for a in n["ayahs"]]
    if okeys != nkeys:
        key_mismatch.append(pg)
        continue
    worst = 0.0
    for oa, na in zip(o["ayahs"], n["ayahs"]):
        if len(oa["segments"]) != len(na["segments"]):
            worst = 1.0
            break
        for (ox, oy, ow, oh), (nx, ny, nw, nh) in zip(oa["segments"], na["segments"]):
            worst = max(worst, abs(ox - nx), abs(oy - ny), abs(ow - nw), abs(oh - nh))
    if worst > EPS:
        moved_pages.append((pg, round(worst, 4)))

gapfilled = [p["page"] for p in NEW["pages"] if p.get("info", {}).get("gap_filled")]
pruned = [p["page"] for p in NEW["pages"] if p.get("info", {}).get("markers_pruned")]
print("gap-filled pages: %s" % sorted(gapfilled))
print("score-pruned pages: %d pages" % len(pruned))
print("identity mismatches: %s  %s" % (key_mismatch, "<-- MUST BE EMPTY" if key_mismatch else "(none)"))
print("geometry moved > %.3f: %s" % (EPS, moved_pages))

# the review gallery should cover: recovered + gap-filled + moved pages
gallery = sorted(set(recovered) | set(gapfilled) |
                set(p for p, w in moved_pages))
print()
print("pages to eyeball in the review gallery: %s" % gallery)
print("plain pages whose geometry moved (should only overlap the lists above):")
plain_moved = [p for p, w in moved_pages
               if p not in gapfilled and p not in pruned and p not in recovered]
print("   %s" % plain_moved)
