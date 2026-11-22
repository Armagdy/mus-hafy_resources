# -*- coding: utf-8 -*-
"""
Convert a research output (temp/bbox-research/<mushaf>_ayah_bboxes.json)
into the compact app asset (public/assets/ayah-bboxes/<mushaf>.json).

Compact schema:
{
  "schema": 1,
  "mushaf": "madinah",
  "pages": {
    "3": [ { "s": 18, "a": 54, "seg": [[x, y, w, h], ...] }, ... ],
    ...
  }
}

Pages whose fit was not trustworthy (fit == 'bbox'/'default' — flagged pages)
are EXCLUDED so the app gracefully falls back to its "selection not
available" behavior there.

Usage:
  python scripts/emit_app_bboxes.py                 # madinah (1421-based)
  python scripts/emit_app_bboxes.py --mushaf tashel
  python scripts/emit_app_bboxes.py --mushaf madinah \
      --src temp/bbox-research/madinah_ayah_bboxes.json
"""
import argparse
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(ROOT, "temp", "bbox-research")
OUT_DIR = os.path.join(ROOT, "public", "assets", "ayah-bboxes")

# madinah's canonical source is the 1421H-based generator (the print is
# a 1421-family typesetting); the classic-based file stays available via
# --src for comparison.
DEFAULT_SRC = {
    "madinah": "madinah_ayah_bboxes_1421.json",
    "tashel": "tashel_ayah_bboxes.json",
    "mwdoa": "mwdoa_ayah_bboxes.json",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mushaf", type=str, default="madinah")
    ap.add_argument("--src", type=str, default=None,
                    help="override the source research JSON file name")
    args = ap.parse_args()
    mushaf = args.mushaf

    SRC = os.path.join(CACHE_DIR,
                       args.src or DEFAULT_SRC.get(mushaf,
                                                   "%s_ayah_bboxes.json"
                                                   % mushaf))
    OUT = os.path.join(OUT_DIR, "%s.json" % mushaf)

    src = json.load(open(SRC, encoding="utf-8"))
    pages_out = {}
    skipped = []
    for p in src["pages"]:
        info = p.get("info", {})
        fit = info.get("fit")
        if fit in ("bbox", "default") or info.get("error"):
            skipped.append(p["page"])
            continue
        entries = []
        for ay in p["ayahs"]:
            segs = []
            for (x, y, w, h) in ay["segments"]:
                segs.append([round(x, 4), round(y, 4), round(w, 4), round(h, 4)])
            entries.append({"s": ay["surah"], "a": ay["ayah"], "seg": segs})
        pages_out[str(p["page"])] = entries

    out = {"schema": 1, "mushaf": mushaf, "pages": pages_out}
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    n_ayahs = sum(len(v) for v in pages_out.values())
    n_segs = sum(len(e["seg"]) for v in pages_out.values() for e in v)
    print("wrote %s" % OUT)
    print("  pages: %d (skipped/flagged: %s)" % (len(pages_out), skipped))
    print("  ayah entries: %d, segments: %d, size: %.1f KB"
          % (n_ayahs, n_segs, os.path.getsize(OUT) / 1024))


if __name__ == "__main__":
    main()
