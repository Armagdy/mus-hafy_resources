# Ayah Bounding Boxes for the Image Mushafs — Research & Working Pipeline

> Goal: give `mwdoa` (الموضوعي), `tashel` (الحفظ الميسر) and `madinah` (مصحف المدينة)
> the same ayah-selection / follow-along highlighting that the text mushafs
> (`tarteel`, `tajweed`) already have — without running a generic OCR model.

Status date: 2026-11-22. **All three image mushafs are solved** — madinah
and tashel via the classic-DB line-fit pipeline, mwdoa via marker detection.
Ayah selection is implemented in the app for all of them.

**2026-11-22 (evening): the madinah print identified — 1421H family. The
box source switched.** The user's report kept pointing at wrong-word
highlighting even after the x-fit fix, and asked whether the print's
writing matches the online DB at all (source of the images:
<https://archive.org/details/quran-mushaf-almadinah-hafs>, a 300-ppi
scan, white margins cropped per page). Measured, apples-to-apples on 56
plain pages (both DBs structurally identical, same band pairing):

| DB | ayah boundaries on the print's real gaps |
|---|---|
| classic 1405H word boxes | 13.2% (≈ chance: 8.2%) |
| **madani 1421H ayah-line boxes** | **63.1%** |

Per-band checks confirm it is not a convention artifact: madinah p564
band 8 really holds THREE ayah segments {68:1cont, 68:2, 68:3} and band 15
contains 68:16's start (classic says two and none). The print shares the
classic's line/pagination GRID (separate compact ~220px centered basmalah
lines — fingerprint-verified, corr 0.93 across surah starts) but its
within-line typesetting is the 1421's. (tashel is the opposite: classic
matches at 56% vs 15% — its pipeline stays as is.)

New generator: **`scripts/generate_ayah_bboxes_madinah_1421.py`**

- 1421 DB conventions measured: same line grid as the classic (header
  slots = line-number gaps); basmalah slots carry a row MISLABELED as the
  following ayah with the basmalah's centered extent → skipped via
  "classic has no glyphs on that line" + narrow (~220px) band block;
  compact surah-start lines (e.g. p604-style basmalah+first-ayah merged,
  wide block) keep the row.
- per-line affine: 1421 line extent → band text block; y from the band.
- validation is PHYSICAL (segments inside their band's block) — the
  reading-order first-ayah check against `quran-meta-data.json` is
  informational only, because the 1421H pagination cuts ~50 page
  boundaries one ayah differently than the classic/meta (e.g. 68:16
  starts on p564's last line, physically verified). Known limitation:
  for those boundary ayahs the app turns the page by the meta, so the
  head words lose their highlight — ~0.8% of ayahs, noted here for a
  future per-mushaf page mapping.
- juz-30 short-surah pages: the 1421 re-typesets them freely, leaving
  13 pages with a band uncovered → emitted as partial (still useful).

Full run: **602/602 pages emitted, 0 excluded, 13 partial.** Final
asset verification (`temp/bbox-research/score_final_asset.py`):
**64.5%** of all internal ayah boundaries land on real white gaps
(classic-based asset: 13.2%), 0 orphan segments.
`emit_app_bboxes.py` now reads `madinah_ayah_bboxes_1421.json` for
madinah (`--src` overrides).

---

---

## 0a. The p564 investigation (2026-11-22)

### Symptom
Follow-along / selection highlight rects on the madinah pages were stretched
horizontally: segment edges spilled up to ~±120 px (≈11% of the page width)
past the real text into the ornamental frame and the neighboring ayahs,
looking like the boxes "need a shift to the right" (worst at line starts,
opposite at line ends — an extent-fit signature).

### Is the local print even the classic 1405H? (user question)
Examined before touching the fit, comparing the local images against BOTH
online databases (`temp/bbox-research/`):

- The two DBs differ in per-page LINE structure on 97 pages (the 1421
  squeezes surah starts into fewer lines), and their page boundaries cut
  ~50 pages one ayah apart (the initial "0 page-start differences" check
  was buggy — it sorted rows by `position`, which is cumulative within
  an ayah; reading order on a line is rightmost-first).
- Basmalah fingerprint test (`temp/bbox-research/basmalah_test2.py`): on
  the 30 surah-start pages whose first band is the tall header, the band
  right after the header is pixel-identical across pages (pairwise
  column-profile correlation median 0.955) and matches p564 band 7
  (0.94–0.98). That band is the basmalah — the local print keeps separate
  compact basmalah lines. This proved the LINE grid, and at first looked
  like "classic 1405H layout, the DB choice was right" — but the
  within-line tests below (§0-evening) showed the grid is shared while
  the word layout is the 1421's, so the DB choice was only half right.
- Y-structure agrees with the classic grid (index fits, residuals
  ≤ 11 px on 557 pages) — that pairing is content-blind and remains true.

### Root cause (x axis only)
`page_geometry` measured the page's text x-extent with a 1%-of-band-rows
cutoff. The ornamental frame's faint outer border lines (x ≈ 0–12 and
1082–1089 on a 1090 px page; they sit under the 40%-density frame mask) pass
that cutoff inside the text bands, so the measured "text" extent was the full
page width (1..1088) instead of the true block (≈130..962). The extent fit
then stretched `sx` (0.95 vs true 0.73) and pulled `tx` left — every box was
scaled past the text block, ~±80–120 px off at the edges, near-zero error at
mid-page (where the two fits cross).

The same measurement also fragmented on pages justified by letter spacing
(p3, p604): non-connecting Arabic letters leave 10–19 px gaps inside words,
larger than the 15 px run-split used when measuring band text blocks.

### Fix (in `scripts/generate_ayah_bboxes.py`)
1. `band_text_block()`: a line's text block = the **largest connected ink
   run** in the band, splitting columns on gaps ≥ 30 px (intra-text gaps stay
   < 20 px; the frame is ≥ 30 px away on every measured page). Frame side
   blocks, hizb rosettes and border remnants are separate runs and never win.
2. `page_x_extent()`: median of per-band text-block edges (was a min/max over
   a 1%-cutoff scan) — used as the page-level fallback only.
3. `fit_page()` x-axis: **paired-line fit** — map the DB's full-width lines
   (db line extent ≥ 85% of the db page extent) onto their bands' text blocks
   and take the median edges; `info.x_fit = "paired(n)"`. Falls back to the
   page extent (`x_page_extent_fallback` flag), then to the old default.
4. Verified per-line on p3/50/106/300/564/604: block-width ratios are now
   uniform (0.69–0.76) and the transforms are page-consistent
   (sx ≈ 0.72–0.76, text block ≈ x 130..962 on a 1090 px page).
5. Global-consensus pass (in `main()`): the print's text block is fixed
   across pages, so after all pages are fitted, the median paired block
   (over clean pages) becomes a prior. The handful of pages whose own
   paired block is displaced > 45 px — their line-fill genuinely differs
   from the classic print (measured: p191, p339; scattered-but-centered
   pages like p110/p602-604 keep their own fit, the median is robust
   there) — are re-fitted with the consensus block (`x_fit=global_prior`):
   boxes then cover the true text as a superset with correct edges
   instead of being compressed toward the right.
6. Margin-rule mask (`strip_columns_mask`): tashel pages carry **dotted
   vertical rules on both margins** (x≈2–25 and x≈964–987 on 990 px pages)
   only 9–27 px from the text — closer than any gap-split threshold, and
   dotted, so density masks miss them. They are caught by a different
   invariant: rules are inked **between text lines**, real text never is
   (columns with > 8% ink in the inter-band gap rows, within the bands'
   vertical span, are dropped from `band_text_block`). This exposed
   tashel's true text block (≈58..947; the previous fits had the rules
   merged in: ≈3..986, ~5% too wide) and also kills madinah's faint outer
   border line as a bonus.

Net effect on the emitted rects: mid-line split points move ~0–2 px; segment
edges move up to ~120 px inward to the true text block; page 564 line 1 now
spans x 0.126..0.880 (was 0.010..0.995).

---

## 0. TL;DR — which pipeline per mushaf

| Mushaf | Method | Quality |
|---|---|---|
| `madinah` | Classic 1405H word-box DB warped onto pages (line-center fit) | 602/604 pages, median line residual 5.8 px; pages 1-2 are ornamental front-matter (excluded) |
| `tashel` | Same pipeline (verified it matches the classic layout line-for-line) | 604/604 pages, median residual 6.2 px, zero pagination mismatches |
| `mwdoa` | Marker detection: golden end-of-ayah medallions found by template matching; ayah identity from known standard pagination; count-validated per page | 584/604 pages validated (502 exact + 42 recovered via low-threshold retry + 40 score-pruned over-detections); 20 pages excluded: 160, 233, 242, 253, 279, 292, 319, 339, 345, 368, 375, 384, 415, 426, 450, 466, 473, 496, 542, 601 |

The three generated app assets live in `public/assets/ayah-bboxes/`
(`madinah.json`, `tashel.json`, `mwdoa.json`, ~550 KB each, normalized 0..1
segments). Regenerate with `scripts/generate_ayah_bboxes.py` (+ the mwdoa
variant) and `scripts/emit_app_bboxes.py`.

---

## 1. Why tarteel / tajweed don't need this

`tarteel`/`tajweed` render pages as **text** (`quran_pages_lines.json` + per-page
QPC fonts in `TartelPage.tsx`). Ayah highlight rects are computed at runtime from
the DOM (`getBoundingClientRect` on `[data-ayah]` word spans). Boxes are implicit
in the layout, so no coordinate file exists or is needed.

The three image mushafs are opaque `page_XXXX.webp` files that were produced by a
custom pipeline (`pdf_to_jpg.py` → crop → deskew → WebP). Any external coordinate
set must therefore be **registered onto our processed images**, or generated on
them directly.

---

## 2. Options considered (all verified)

| Option | What it is | Verdict for us |
|---|---|---|
| **Quran Android "ayahinfo" DBs** (`files.quran.app/hafs/...`) | Word/glyph boxes for the classic **1405H Madani** print (88,246 rows, SQLite `glyphs` table), plus per-riwayah DBs for `madani_1421`, `shemerly`, `qaloon`, `warsh`, `naskh` | ✅ **Winner for `madinah`** — our pages match the classic layout line-for-line (see §3) |
| [quran-ws/quran-svg](https://github.com/quran-ws/quran-svg) | Ayah **polygons** for 5 KFQC riwayat (hafs, warsh, qaloon, douri, shubah), CC BY 4.0 (attribution waived in products), per-page JSON + CDN `cdn.quran.ws` | ✅ Best ready-made data for KFQC-print mushafs; coordinate space = SVG page units (viewBox 345×550) |
| QUL "Mushaf layouts" ([qul.tarteel.ai](https://qul.tarteel.ai/resources/mushaf-layout)) | Line/word layout data (page → lines → word ids) for KFGQPC V1/V2/V4, IndoPak 13/15/16, Nastaleeq, Qatar, etc. — **logical layout, no pixels** | Useful to re-render pages as text (like tarteel), **not** for overlaying existing images |
| [GitCreativeCode/quran-ayah-coords](https://github.com/GitCreativeCode/quran-ayah-coords) | Ayah-level boxes for the old Madani scan, 604 JSONs, CC BY-SA 4.0 | Same print family as the ayahinfo DB but coarser (ayah-level); superseded by the DB |
| [quran/ayah-detection](https://github.com/quran/ayah-detection) | CV scripts (template/contour matching) to detect ayah-end markers; tested on shamerly/qaloon/warsh | ✅ The reference design for **tashel/mwdoa** (§5) |
| [bllfoad/ayahai](https://github.com/bllfoad/ayahai) | YOLOv5-based ayah detection + bounding boxes (Mushafalummah) | Alternative for marker detection; needs Python + model |
| HuggingFace `devgongaji/quran-bounding-labels` | Pascal VOC boxes (ayah lines + markers) for 4 Indonesian editions | ⚠️ No license declared, images not included — training data only |
| Kaggle `anasfahmy/Quran_Dataset` | Hafs page images + ayah/word JSON + marker overlays | Useful as CV training/validation data |

Notes on licenses: quran-ws metadata is CC BY 4.0 with attribution waived inside
products; KFGQPC artwork allows free digital use (no commercial *printing*).
Quran Android's databases have been used by dozens of apps for a decade.

---

## 3. `madinah` — verified solution (ready to ship after visual review)

### What we verified

Our `mushaf_madinah_images` are a **framed Egyptian-style reprint of the standard
Madani 15-line layout** (not the quran.com scans themselves — our pages have an
ornamental border, theirs don't; and our images were cropped/deskewed per page).
Key checks performed (see `temp/bbox-research/` for scripts + evidence):

- Standard 604-page pagination matches our app metadata exactly
  (`quran-meta-data.json` `pages[]` == classic DB reading order == QPC layout —
  0 mismatches across all 604 pages).
- 15-line structure matches the classic print line-for-line: fitting the DB's
  line centers onto our detected line bands gives **median residual 5.8 px
  (p90 = 8.1 px, max = 11.3 px)** on a ~94 px line pitch — sub-line accuracy.
- Surah-header pages align via the DB's own line-number gaps (headers/basmalahs
  occupy the missing line numbers). E.g. page 106: our header bands sit exactly
  at lines 6–7, after 4:176's five lines, matching the layout in
  `quran_pages_lines.json`.
- The `madani_1421` DB (newer print) does **not** match our images (its
  line geometry differs) — use the classic DB, not the 1421 one.

### The pipeline (`scripts/generate_ayah_bboxes.py`)

For each page:

1. Mask out the ornamental frame columns (density > 40% of page height — some
   pages have several stacked frame layers).
2. Detect our text-line bands from the row profile; drop thin divider bands
   (hizb ornaments) by median-height filter.
3. Query the classic ayahinfo DB (`glyphs` table, word boxes).
4. Fit an axis-aligned affine (sx, sy, tx, ty):
   - **index pairing** when our band count == the DB's max line number
     (band *i* ↔ DB line *i*; DB line-number gaps = header/basmalah lines);
   - **hypothesis repair** when off by one (split a tall merged band / drop a
     divider band, keep the best residual);
   - tail-aligned / bbox fallbacks otherwise, always flagged.
5. Group DB words by (line, surah, ayah) → one box per ayah line segment →
   warp → **normalize to 0..1 of the image** → emit JSON.
6. Validation per page: reading-order first ayah vs `quran-meta-data.json`,
   line-fit residuals, band counts. Every page carries its flags.

### Results (all 604 pages)

- 557 pages: clean index fit; 45 pages: repaired fit (all ≤ 11.3 px residual).
- 2 pages: **flagged** — pages 1 and 2 are near-identical dense ornamental pages
  (52% identical pixels, no text-line structure at any threshold). The DB
  expects Fatihah (7 lines) + Baqarah 1:1–1:5 there. **Needs a human decision**
  (see §7).
- 0 pagination mismatches.

Output schema (`temp/bbox-research/madinah_ayah_bboxes.json`):

```json
{
  "pages": [
    {
      "page": 300, "width": 1090, "height": 1600,
      "transform": { "sx": 0.94764, "sy": 0.7026, "tx": -57.7, "ty": 88.2 },
      "ayahs": [
        { "surah": 18, "ayah": 54,
          "segments": [[x, y, w, h], [x, y, w, h]] }   // one per printed line, 0..1
      ],
      "info": { "fit": "index", "max_line_residual_px": 5.2, "flags": [] }
    }
  ]
}
```

`segments` mirrors exactly what `TartelPage.tsx` computes at runtime for the
text mushafs (per-line rects per ayah), so the overlay/highlight UI can be
reused: draw each segment scaled to the rendered image size; hit-test long-press
against the segments; during playback, highlight the current ayah's segments
(and auto-turn pages using the existing `getAyahPage()` logic).

### Review before shipping (10 minutes)

Open `temp/bbox-research/overlays/madinah_pXXXX.png` — colored boxes drawn over
the real pages:

- `madinah_p0003.png`, `madinah_p0106.png` (surah header page), `madinah_p0300.png`,
  `madinah_p0187.png` / `madinah_p0585.png` (previously tricky, now fitted),
  `madinah_p0604.png` (three surahs), `madinah_p0001/0002.png` (the anomaly).

If the boxes sit on the ayahs (they should, given ≤11 px line residuals), copy
`madinah_ayah_bboxes.json` to `public/assets/ayah-bboxes/madinah.json` and wire
it into `SwiperPageDisplay.tsx`.

---

## 4. App integration — IMPLEMENTED (2026-11-22)

Ayah selection + follow-along highlighting is now wired into the app for the
`madinah` image mushaf, mirroring TartelPage's interaction model:

| File | Role |
|---|---|
| `public/assets/ayah-bboxes/madinah.json` | Compact app data — 602 pages, per-ayah per-line segments, normalized 0..1 (546 KB; pages 1-2 excluded) |
| `src/lib/ayah-bboxes.ts` | Loader (fetch + module-level cache, graceful null on failure) + `findAyahAtPoint` hit-test + `findNearestAyahAtPoint` (nearest-ayah snap for holds in empty space, aspect-corrected distance + `AYAH_SNAP_MAX_DISTANCE` threshold) |
| `src/components/quran/SwiperPageDisplay.tsx` | New `ImagePageView` (memoized, per-page instance): desktop **hover → highlight**, press-and-hold **(400ms, pointer events, mouse or touch) → select** (nearest-ayah snap for gap presses), **playing-ayah highlight** during follow-along. Percentage-positioned overlay divs (`ayah-highlight-overlay`, same colors as TartelPage), so no runtime measuring at any size |
| `src/test/ayah-bboxes.test.ts` | 21 unit tests (hit-test, tolerance, nearest-snap distances, caching, fallbacks) |
| `scripts/emit_app_bboxes.py` | Converts the research JSON → the compact app asset (skips flagged pages) |

Behavior:

- **Selection** works exactly like the text mushafs: long-press an ayah →
  haptics → the existing ayah menu/flow (`onAyahSelect` → parent sets
  `currentPlayingAyah` → highlight persists; playback seeks if playing; the
  mp3quran-without-timings guard keeps working).
- **Follow-along**: during playback the current ayah's segments are highlighted
  on the madinah pages (page auto-navigation was already there).
- **Graceful degradation**: tashel/mwdoa (no data yet), madinah pages 1-2
  (ornamental), and any fetch failure → the reader behaves exactly as before
  (guidance toast). Web-prod fetches the JSON from the jsDelivr CDN, so it
  needs a push to GitHub master to go live; dev + native (bundled) work
  immediately.

Regenerate after re-running the pipeline:

```
python scripts/generate_ayah_bboxes.py --all
python scripts/emit_app_bboxes.py
```

---

## 5. `tashel` and `mwdoa` — SOLVED (2026-11-22)

**tashel** follows the standard Madani layout line-for-line (probe residuals
5.0-8.0 px on all sampled pages), so the classic-DB pipeline covers it:
`python scripts/generate_ayah_bboxes.py --mushaf tashel --all` (binarization
threshold 140 — its pages are slightly tinted). 604/604 pages fit (median
residual 6.2 px), zero pagination mismatches, and unlike madinah its pages
1-2 are real content pages (no front-matter issue).

**mwdoa** has its own line layout, so it needed marker detection — cracked
with two user-confirmed labels:

1. The end-of-ayah sign is an ornate **golden diamond medallion (~53×64 px)
   with a dark rosette inside** (hue 22-52, sat > 38 — often faded). A full
   clean medallion cut from page 300 (user-confirmed) is the template.
2. `cv2.matchTemplate` on a gold-hue map (TM_CCOEFF_NORMED >= 0.55, 30 px NMS)
   finds exactly the expected marker count per page — validated on pages
   2/3/50/106/300/400/604 (5, 11, 9, 3, 8, 8, 15). This also proves mwdoa
   follows the standard 604-page Madani pagination.
3. Reading order (top band first, right-to-left within a band) assigns the
   k-th marker to the k-th ayah END on the page (ayah list + page boundaries
   from the classic DB). Segments come from the marker chain: spans between
   consecutive markers on a band + full intermediate bands + the tail of the
   ayah continuing onto the next page.
4. Pages where detected count != expected (after the low-threshold retry) are
   flagged and EXCLUDED from the app asset (graceful fallback there); the
   flagged list shows exactly which pages need a human look. Final full run:
   **584/604 pages validated** (5,988 ayah entries, 14,223 segments) — the 20
   excluded pages keep the classic "selection not available" behavior.

Pipeline: `scripts/generate_ayah_bboxes_mwdoa.py` (over-detection pruned by
score — real markers score 0.8+ vs ~0.55-0.7 for incidental ornament matches).
Post user review (2026-11-22): marker boxes are offset +8px (the template's
padding), segment x-ranges are bounded by the page's ornamental frame
(dense-column clusters per page — including page 2's wide side panels), and
the boundary ayahs' line spans come from the DB's on-page WORD counts
(~9 words/line) so nothing spills into the border or the footer text.

**Fihris clip (2026-11-22, second user review).** Every mwdoa content page
prints a marginal FIHRIS (index) column on its OUTER edge — left on even
(left-hand) pages, right on odd (right-hand) ones; layout outside-in: page
frame → index entries (small colored chips + dark text, pale cream
background) → ornamental rule band (gold/dark, ~2.5-3%W wide, with a pale
gap after it) → text column. The frame-bounded tx extent still included
it, so every full-width highlight segment covered the fihris (user-reported
"the selection includes the fihris"). `fihrist_clip_x()` now detects the
strip per page — rule = the innermost dense ink column cluster (primary,
geometrically exact), the entries' saturated-chip run adjacent to the frame
(fallback for pale strips), refined by a walk toward the text that skips
the ornament band and pale margins and stops at the first text-like ink
column. The INNER side is never clipped: the thematic print puts pale
topic-colored TEXT blocks there (e.g. pages 38/41/178/201...), whose rows
align with the text bands. Full re-run: same 584/604 pages validated, same
20 flagged; 8,286 segments changed, all one-sided narrowing (8,233 clips +
53 marker-edge slivers), clip edges land at 0.198-0.251 (even) / 0.759-0.800
(odd); pages 1-2 keep no clip (ornamental). The regenerated asset is synced
to `public/assets/ayah-bboxes/mwdoa.json` AND the Android bundle copy
(`android/app/src/main/assets/public/...`).

**Multi-scale + gap-fill recovery (2026-11-27, user-reported page 242).** The
20 pages excluded since the first run — **160, 233, 242, 253, 279, 292, 319,
339, 345, 368, 375, 384, 415, 426, 450, 466, 473, 496, 542, 601** — had no
ayah selection/highlighting in the app. Root cause: the golden medallion's
PRINTED SIZE varies across the volume (53x64 px on the template's page 300,
up to ~66x78 elsewhere, occasionally mixed sizes within one page, e.g.
601). Against the fixed template those markers score ~0.53 — just under the
0.55 gate — and the page failed the count validation. A saturation-gate
probe (sat 38→20) ruled out ink fading as the cause for most of them; the
remaining ones ARE faded (score 0.35-0.55).

`scripts/generate_ayah_bboxes_mwdoa.py` now runs a two-pass detector:

- **Pass 1** — the classic single-scale match, unchanged. Every page it
  count-validates is emitted BIT-IDENTICAL to the reviewed asset (an
  all-multiscale run was tried first and rejected: cross-scale NCC winners
  shift marker edges ~3 px on hundreds of already-good pages — see
  `mwdoa_ayah_bboxes_run1_allmultiscale.json` + `mwdoa_multiscale_log.txt`).
- **Pass 2** — only pages pass 1 cannot validate: a multi-scale template
  sweep (TEMPLATE_SCALES 0.8-1.3, cross-scale NMS) recovers the different
  marker sizes (e.g. 242 scores 0.93 at k=1.2); still-short pages get a GAP
  FILL — the missing faded markers (0.35-0.55) are accepted only inside the
  reading-order gaps between the trusted anchors and within the text
  column, so marginal ornaments (surah headers, fihris chips, frame) can
  never win a slot. This replaces the old blind 0.45 retry, which could
  seat an ornament in the chain.

Full re-run: **604/604 pages validated, 0 flagged** — the emitted asset adds
the 20 pages and changes only the 42 pages that previously depended on the
blind retry (now rebuilt through pass 2); the other 542 pages are
byte-identical to the previous asset (`validate_mwdoa_multiscale.py`).
Overlays for all 62 pass-2 pages + controls:
`research/bbox/render_mwdoa_overlays.py` → `review_mwdoa_multiscale.html`
(each colored rect should end exactly at its red medallion).

**First-ayah head coverage (2026-11-27, user-reported pages 160/253).** The
regenerated asset's first ayah was clipped on **77 pages** — all fresh
mid-surah page starts: the first ayah's start band was estimated from its
on-page word count (`WPL = 9` words per band), but the mwdoa print runs
~6-9 words per band, so the estimate undercounted the line span and the
highlight missed the top line(s) — three lines on page 205. A
continuation/fresh check against the DB (the page's first ayah appearing
on the previous page, or opening a surah) now decides directly: a
continuation flows from the top band; a fresh mid-surah ayah's first line
IS the top band (ink-density-guarded, so the ornamental Fatiha page stays
on the estimate); only surah openings keep the word estimate — their
ornamental header + basmalah sit above the first ayah's text. No ayah ever
spans a page boundary in the classic DB (checked: 0 pages), so the
page-bottom continuation branch never runs and the tail needed no change —
the dense bottom "bands" on every page are the frame's decorative rule,
not text.

The `temp/bbox-research/mwdoa_*.py` probes document the dead ends (gray and
color thresholds, isolation tests, self-similarity mining, fragment template
matching — all failed because the marker is a large faded-gold diamond, not
a compact black blob).

Historical plan (kept for reference): both are Egyptian 604-page editions
with standard pagination; no coordinate dataset exists for either print, so
boxes must be generated **on our images**:

1. **Line geometry**: same band detection as §3 (works as-is on these sets —
   verified on sample pages).
2. **Ayah boundaries**: detect the ayah-end markers (۝ medallions). Because the
   page → ayah list is known from `quran-meta-data.json`, the *k*-th marker on a
   page (in reading order, RTL) is the end of the *k*-th ayah — no OCR needed,
   only marker detection + validation against the expected ayah count per page.
   - Template matching (`quran/ayah-detection` approach): cut one marker from a
     page, match across pages; the mwdoa/tashel markers are geometrically
     consistent.
   - Or contour detection (`find_ayat_v2.py` approach): markers are compact,
     roughly square blobs with high fill ratio at line ends — filter by size,
     fill, and distance from the nearest line's baseline.
   - Or YOLO (AyahAI) if the classical approaches need too much tuning.
3. **Assignment**: within each line band, the text between marker *k−1* and
   marker *k* belongs to ayah *k* (RTL order; first/last lines join the
   previous/next page's ayah via the known mapping). Emits the same
   `segments` JSON as madinah.
4. **Validation UI**: overlay + flag pages where marker count ≠ expected ayah
   count; eyeball flagged pages. The known page content makes review fast.

Rough effort: ~a day of CV tuning + a review pass over ~600 pages (spot-check
the flagged ones only). All building blocks (band detection, overlay rendering,
flags) already exist in `scripts/generate_ayah_bboxes.py`.

---

## 6. Artifacts produced by this research (in `temp/bbox-research/`)

- `madinah_ayah_bboxes.json` — full 604-page output (normalized segments).
- `overlays/madinah_pXXXX.png` — review overlays.
- `ayahinfo_classic_1260.db` — cached classic 1405H word-box DB (from
  `https://files.quran.app/hafs/madani/databases/ayahinfo/ayahinfo_1260.zip`).
- `test_align*.py`, `register_images.py`, `final_overlays.py` — the forensic
  experiments backing §3.

## 7. Open questions / next steps

1. **What are madinah pages 1–2?** They are near-identical ornamental pages with
   no text-line structure — not the Fatihah / Baqarah-start pages the app
   mapping expects. Check `page_0001.webp` / `page_0002.webp` in the app: if
   they're front-matter ornaments, the mushaf is missing its first two content
   pages (or the mapping is off by two for this set) — either way those two
   pages need manual boxes or a source-PDF fix.
2. Eyeball the overlays (§3 review list) → confirm → copy JSON into
   `public/assets/ayah-bboxes/` and integrate (§4).
3. Decide whether to build the marker-detection pipeline for `tashel`/`mwdoa`
   now (§5) — I can prototype it on a handful of pages next.
