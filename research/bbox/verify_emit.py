# -*- coding: utf-8 -*-
"""Post-regeneration verification of the emitted app assets."""
import json
import numpy as np

for name, old_path in (("madinah", "public/assets/ayah-bboxes/madinah.json"),):
    new = json.load(open(old_path, encoding="utf-8"))
    res = json.load(open("temp/bbox-research/%s_ayah_bboxes.json" % name,
                         encoding="utf-8"))
    res_by_page = {p["page"]: p for p in res["pages"]}

    n_pages = len(new["pages"])
    n_ayahs = sum(len(v) for v in new["pages"].values())
    n_segs = sum(len(e["seg"]) for v in new["pages"].values() for e in v)

    # sanity: segments within [0,1]
    bad = []
    for pg_s, entries in new["pages"].items():
        for e in entries:
            for s in e["seg"]:
                if s[0] < -0.02 or s[1] < -0.02 or s[2] <= 0 or s[3] <= 0 \
                        or s[0] + s[2] > 1.02 or s[1] + s[3] > 1.02:
                    bad.append((pg_s, e["s"], e["a"]))
    print("%s: pages=%d ayahs=%d segs=%d  out-of-range=%d"
          % (name, n_pages, n_ayahs, n_segs, len(bad)))
    if bad[:5]:
        print("   e.g.", bad[:5])

    # global_prior pages
    gp = [p["page"] for p in res["pages"]
          if p["info"].get("x_fit") == "global_prior"]
    print("   global_prior pages:", gp)

    # p564 spot check
    p564 = new["pages"]["564"]
    e = p564[0]
    print("   p564 first ayah %d:%d seg0=%s (expect x~0.126..0.880)"
          % (e["s"], e["a"], e["seg"][0]))

    # excluded (flagged) pages in research but present in asset?
    skipped = [p["page"] for p in res["pages"]
               if str(p["page"]) not in new["pages"]]
    print("   pages excluded from asset:", skipped)
