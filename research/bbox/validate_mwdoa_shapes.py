# -*- coding: utf-8 -*-
"""Deep-check the 317 flagged segment changes.

For each: confirm the change is one of the two BENIGN shapes:
  A) normal clip: new [cx0, x1] subset of old [tx0, x1] (even) / mirror
     (odd) — narrowing only.
  B) marker-at-column-edge sliver: the previous marker sits at/near the
     clip edge, so the span becomes a tiny slice touching the marker —
     new ~= [old.x1, clip] (even) / [clip, old.x0] (odd).
Anything else = real problem.
"""
import json

OLD = json.load(open("temp/bbox-research/mwdoa_app_OLD.json", encoding="utf-8"))
NEW = json.load(open("public/assets/ayah-bboxes/mwdoa.json", encoding="utf-8"))

EPS = 0.002
normal = sliver = other = 0
others = []
for p, entries in NEW["pages"].items():
    old_entries = OLD["pages"].get(p)
    if not old_entries:
        continue
    even = int(p) % 2 == 0
    for oe, ne in zip(old_entries, entries):
        for i, (os_, ns_) in enumerate(zip(oe["seg"], ne["seg"])):
            ox, oy, ow, oh = os_
            nx, ny, nw, nh = ns_
            ox1, nx1 = ox + ow, nx + nw
            if (ox, oy, ow, oh) == (nx, ny, nw, nh):
                continue
            if even:
                # A: left edge moves right, right edge same, narrower
                if nx >= ox - EPS and abs(nx1 - ox1) <= EPS and nw <= ow + EPS:
                    normal += 1
                    continue
                # B: sliver at the marker: new starts at old's right edge
                if abs(nx - ox1) <= EPS and nx1 - ox1 <= 0.01 and nx1 <= 0.35:
                    sliver += 1
                    continue
            else:
                if nx1 <= ox1 + EPS and abs(nx - ox) <= EPS and nw <= ow + EPS:
                    normal += 1
                    continue
                if abs(nx1 - ox) <= EPS and ox - nx <= 0.01 and nx >= 0.65:
                    sliver += 1
                    continue
            other += 1
            others.append((p, ne["s"], ne["a"], i,
                           "%.3f..%.3f -> %.3f..%.3f" % (ox, ox1, nx, nx1)))

print("changed segments: normal-clip=%d marker-sliver=%d OTHER=%d"
      % (normal, sliver, other))
for o in others[:30]:
    print("   ", o)
