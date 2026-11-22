# mus-hafy_resources

Resources + generator pipeline for the Mushafy Quran app ([mus-hafy_pwa](https://github.com/Armagdy/mus-hafy_pwa)).
The app fetches these assets at runtime from **Cloudflare Pages**
(`https://mus-hafy-resources.pages.dev/...`), so the app keeps working even if the
source repo is closed. A jsDelivr mirror of this repo serves as an automatic
fallback in the app when the primary CDN fails.

## Layout

| Path | Contents |
|---|---|
| `assets/` | The full asset tree. **Source of truth for everything the app loads.** Mushaf page images (madinah / tashel / mwdoa), per-page QPC font sets, static fonts, ayah bounding-box JSONs, meta data JSONs, reciters, snippets. |
| `scripts/` | Generators & batch tools: bbox generation/detection (`generate_ayah_bboxes*.py`, `emit_app_bboxes.py`), image processing (`deskew`, `crop`, `optimize-images.js`, `imagemagick_trim.ps1`), PDF extraction (`pdf_to_jpg.py`, `split_pdf.py`, `poppler/`), audio (`generate_everyayah_audio.py`, `update_audio_metadata.py`). |
| `poppler/` | Poppler 24.08.0 binaries — used by the PDF scripts. |
| `research/bbox/` | Ayah bounding-box research: detector iterations (`mwdoa_detector_v*.py`), overlay galleries, reference DBs (`ayahinfo_*.db`), review pages, validation scripts, findings. See `research/AYAH_BOUNDING_BOXES_RESEARCH.md`. |

## How the app consumes this repo

- **Primary CDN (production web + on-demand native downloads):**
  `https://mus-hafy-resources.pages.dev` — Cloudflare Pages, free, unlimited bandwidth.
- **Fallback CDN:** `https://cdn.jsdelivr.net/gh/Armagdy/mus-hafy_resources@main/assets` —
  jsDelivr mirrors this repo, but note jsDelivr refuses repos over 50 MB
  ("Package size exceeded the configured limit of 50 MB" → sporadic 403s on
  individual files), so it is only a safety net, never the primary.
- **Bundled subset:** the app repo (`mus-hafy_pwa`) keeps a small copy of the
  bundled assets under its own `public/assets/` because native APK builds and the
  service worker need them offline:
  `quran-meta-data.json`, `ayah-meta-data.json`, `reciters.json`,
  `quran_pages_lines.json`, `ayah-bboxes/*.json`, `mushaf_snippets/`, `ayah.svg`
  and the small static fonts (`quran-hafs`, `quran-icon`, `surah-header`,
  `surah-name-v4`).
  When any of those change here, copy the updated file into the app repo too.
- **Never bundled (too large, CDN-only):** `mushaf_madinah_images/`,
  `mushuf_mwdoa_images/`, `mushaf_tashel_pages/`, `fonts/qpc_v2_font/`,
  `fonts/qpc_v4_font/` — they live **only** in this repo and on the CDN.

## Deploying asset updates to Cloudflare Pages

Whenever files under `assets/` change, re-publish the CDN (needs a Cloudflare API
token with **Pages Write** permission and your account ID):

```bash
cd mus-hafy_resources
CLOUDFLARE_API_TOKEN=<token> CLOUDFLARE_ACCOUNT_ID=79a1024a2267422d9b99ef8209112d5b \
  npx wrangler pages deploy assets --project-name=mus-hafy-resources --branch=main --commit-dirty=true
```

Then commit + push this repo so the jsDelivr fallback mirror stays in sync.

## Regenerating ayah bounding boxes

The scripts mostly use paths relative to the **app repo** working tree
(e.g. `public/assets/ayah-bboxes/...`), so run them from inside a `mus-hafy_pwa`
checkout (or adjust the paths at the top of each script):

1. Research/iteration happens in `research/bbox/` (detectors, overlays, review pages).
2. `scripts/generate_ayah_bboxes*.py` produce per-mushaf box data.
3. `scripts/emit_app_bboxes.py` writes the compact app asset to `public/assets/ayah-bboxes/<mushaf>.json`.
4. Copy the emitted JSON here into `assets/ayah-bboxes/` and into the app repo's
   `public/assets/ayah-bboxes/`.

## Notes

- `assets/quran_pages_lines.json` (~22 MB) exceeds jsDelivr's per-file limit —
  the app always fetches it from its own origin (it is bundled), never the CDN.
- Fonts provenance & licenses: see `assets/resources.txt`.
- The image-processing scripts expect Python 3 with Pillow/OpenCV and, for the
  PowerShell ones, ImageMagick; the PDF ones use the bundled `poppler/`.
