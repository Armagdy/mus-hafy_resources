# -*- coding: utf-8 -*-
"""
Image-to-image registration: local mushaf_madinah pages vs the quran.com
classic 1405H Madani reference scans (1260x2038).

ORB features + RANSAC affine. If the local set is (a processed version of)
the same print, every page should register with lots of inliers and a
consistent scale/translation.
"""
import numpy as np
from PIL import Image
import cv2

LOCAL = r"D:\apps\quran\mushafy\public\assets\mushaf_madinah_images"
REF = r"D:\apps\quran\mushafy\temp\bbox-research"


def register(page_tag):
    local = np.array(Image.open(LOCAL + "\\page_%s.webp" % page_tag).convert("L"))
    ref = np.array(Image.open(REF + "\\ref_madani_%03d.png" % int(page_tag)).convert("L"))

    # downscale both to height ~800 for speed
    def fit(img):
        h, w = img.shape
        s = 800.0 / h
        return cv2.resize(img, (int(w * s), int(h * s))), s
    A, sa = fit(local)
    B, sb = fit(ref)

    orb = cv2.ORB_create(nfeatures=3000, scaleFactor=1.2, nlevels=10)
    kA, dA = orb.detectAndCompute(A, None)
    kB, dB = orb.detectAndCompute(B, None)
    if dA is None or dB is None:
        print("  no features"); return None
    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    matches = bf.match(dA, dB)
    matches = sorted(matches, key=lambda m: m.distance)[:800]
    if len(matches) < 10:
        print("  too few matches (%d)" % len(matches)); return None
    ptsA = np.float32([kA[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
    ptsB = np.float32([kB[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)
    M, mask = cv2.estimateAffine2D(ptsA, ptsB, method=cv2.RANSAC,
                                   ransacReprojThreshold=4.0, maxIters=5000)
    inliers = int(mask.sum()) if mask is not None else 0
    ratio = inliers / float(len(matches))
    print("  local %s vs ref: matches=%d inliers=%d (%.1f%%)" %
          (page_tag, len(matches), inliers, 100 * ratio))
    if M is not None:
        # M maps local(downscaled) -> ref(downscaled); express in original px:
        S = np.diag([sb / sa, sb / sa, 1.0])
        M3 = np.vstack([M, [0.0, 0.0, 1.0]])
        M2 = S @ M3 @ np.linalg.inv(S)
        print("     affine(local px -> ref px): sx=%.4f sy=%.4f tx=%.1f ty=%.1f  det=%.4f"
              % (M2[0, 0], M2[1, 1], M2[0, 2], M2[1, 2], np.linalg.det(M2[:2, :2])))
        return M2, inliers, ratio
    return None


for tag in ("0002", "0300", "0604"):
    register(tag)
