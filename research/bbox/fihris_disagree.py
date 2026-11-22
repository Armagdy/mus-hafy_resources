# -*- coding: utf-8 -*-
"""List pages where the color-strip inner edge and the divider line disagree
by >2% of width (outer/parity side only), to decide the clip value."""
import json

SCAN = json.load(open("temp/bbox-research/fihris_scan2.json", encoding="utf-8"))

for r in SCAN:
    even = r["page"] % 2 == 0
    c, d = (r["cL"], r["div_l"]) if even else (r["cR"], r["div_r"])
    if c is None and d is None:
        print("p%-4d NO SIGNAL (color=%s divider=%s)" % (r["page"], r["cL"], r["div_r"]))
        continue
    if c is not None and d is not None:
        if abs(c["inner_x"] - d) > 0.02 * r["W"]:
            print("p%-4d DISAGREE color=%.3f div=%.3f (d=%.3fW) peak=%.2f vcover=%.2f" %
                  (r["page"], c["inner_x"] / r["W"], d / r["W"],
                   abs(c["inner_x"] - d) / r["W"], c["peak"], c["vcover"]))
    elif c is None:
        print("p%-4d DIVIDER-ONLY div=%.3f" % (r["page"], d / r["W"]))
    else:
        print("p%-4d COLOR-ONLY  color=%.3f peak=%.2f vcover=%.2f" %
              (r["page"], c["inner_x"] / r["W"], c["peak"], c["vcover"]))
