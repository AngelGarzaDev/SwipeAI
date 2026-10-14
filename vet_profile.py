#!/usr/bin/env python3
"""Vet a Facebook Dating profile screenshot.

Usage: python3 vet_profile.py <screenshot.png> [config.toml]

The last line of stdout is machine readable:
    LIKE <x> <y>       profile passed the guidelines; tap the heart at x,y
    DISLIKE <x> <y>    profile failed; tap the X at x,y
    NONE               no Dating card / buttons visible
A JSON report is also written next to the screenshot (<name>.report.json).
"""
import json
import os
import re
import subprocess
import sys

import cv2
import numpy as np

import config
import llm_judge

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATES = {"LIKE": ["templates/heart.png", "templates/heart_2.png"],
             "DISLIKE": ["templates/x_mark.png", "templates/x_mark_2.png"]}
MATCH_THRESHOLD = 0.8

# Screen layouts on the locked 1080x1920 @320dpi display. Identified by the
# horizontal distance between the X and heart button centres.
#   card:    first Dating page - profile card, buttons on photo's bottom-right.
#   profile: after the first swipe - full-screen profile, buttons bottom-centre
#            floating over the bio.
LAYOUTS = {
    "card": {"spacing": 162,
             # regions as functions of (hx, hy, xx) -> (y0, y1, x0, x1)
             "photo": lambda hx, hy, xx: (hy - 1003, hy, hx - 903, hx + 97),
             "text": lambda hx, hy, xx: (hy + 25, hy + 190, hx - 903, xx - 70)},
    "profile": {"spacing": 304,
                "photo": lambda hx, hy, xx: (65, 1361, 0, 1080),
                "text": lambda hx, hy, xx: (1375, 1820, 0, 1080)},
}
SPACING_TOLERANCE = 25
BUTTON_Y_TOLERANCE = 10
# Heart button fill is purple: OpenCV hue ~129, high saturation.
HEART_HUE = (115, 145)
CASCADE = os.path.join(HERE, "models", "haarcascade_frontalface_alt2.xml")


def log(msg):
    print(f"DEBUG: {msg}")


def find_buttons(img):
    """Locate the like/dislike buttons with multi-scale template matching."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    found = {}
    for label, rels in TEMPLATES.items():
        best = (0.0, None, None)
        for rel in rels:
            tpl = cv2.imread(os.path.join(HERE, rel), cv2.IMREAD_GRAYSCALE)
            if tpl is None:
                continue
            for scale in (0.9, 1.0, 1.1):
                t = cv2.resize(tpl, None, fx=scale, fy=scale)
                res = cv2.matchTemplate(gray, t, cv2.TM_CCOEFF_NORMED)
                _, mv, _, ml = cv2.minMaxLoc(res)
                if mv > best[0]:
                    best = (mv, (ml[0] + t.shape[1] // 2, ml[1] + t.shape[0] // 2), rel)
        log(f"{label} template score {best[0]:.3f} at {best[1]} ({best[2]})")
        if best[0] >= MATCH_THRESHOLD:
            found[label] = best[1]
    if len(found) < 2:
        return found, None

    (hx, hy), (xx, xy) = found["LIKE"], found["DISLIKE"]
    # Geometry check: same row, X left of heart, known spacing.
    if abs(hy - xy) > BUTTON_Y_TOLERANCE or hx <= xx:
        log(f"rejected: buttons not side by side (heart {hx},{hy} x {xx},{xy})")
        return {}, None
    layout = None
    for name, L in LAYOUTS.items():
        if abs((hx - xx) - L["spacing"]) <= SPACING_TOLERANCE:
            layout = name
    if layout is None:
        log(f"rejected: unknown button spacing {hx - xx}")
        return {}, None
    # Colour check: heart button body must be purple.
    hsv = cv2.cvtColor(img[hy - 40:hy + 40, hx - 40:hx + 40], cv2.COLOR_BGR2HSV)
    purple = cv2.inRange(hsv, (HEART_HUE[0], 80, 80), (HEART_HUE[1], 255, 255))
    frac = cv2.countNonZero(purple) / purple.size
    if frac < 0.3:
        log(f"rejected: heart region only {frac:.0%} purple")
        return {}, None
    log(f"layout={layout} spacing={hx - xx} heart_purple={frac:.0%}")
    return found, layout


def ocr(img):
    try:
        out = subprocess.run(["tesseract", "stdin", "stdout", "--psm", "6"],
                             input=cv2.imencode(".png", img)[1].tobytes(),
                             capture_output=True, timeout=30)
        return out.stdout.decode("utf-8", "ignore").strip()
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        log(f"OCR unavailable: {e}")
        return ""


YUNET = os.path.join(HERE, "models", "face_detection_yunet_2023mar.onnx")


def detect_faces_yunet(photo, min_score):
    """YuNet CNN face detector (CPU, ~230KB model). Returns [(x,y,w,h,score)]."""
    s = 640.0 / max(photo.shape[:2])
    small = cv2.resize(photo, None, fx=s, fy=s)
    h, w = small.shape[:2]
    det = cv2.FaceDetectorYN.create(YUNET, "", (w, h), score_threshold=min_score,
                                    nms_threshold=0.3, top_k=50)
    _, out = det.detect(small)
    faces = []
    if out is not None:
        for row in out:
            x, y, fw, fh = row[:4] / s
            faces.append((int(x), int(y), int(fw), int(fh), round(float(row[14]), 3)))
    return faces


def detect_faces_haar(photo):
    """Fallback: Haar cascade with small rotations."""
    gray = cv2.cvtColor(photo, cv2.COLOR_BGR2GRAY)
    det = cv2.CascadeClassifier(CASCADE)
    s = 600.0 / max(gray.shape)
    small = cv2.equalizeHist(cv2.resize(gray, None, fx=s, fy=s))
    h, w = small.shape
    faces = []
    for angle in (0, -20, 20):
        M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
        rot = cv2.warpAffine(small, M, (w, h), borderMode=cv2.BORDER_REPLICATE)
        found = det.detectMultiScale(rot, scaleFactor=1.05, minNeighbors=4, minSize=(24, 24))
        if len(found):
            Minv = cv2.invertAffineTransform(M)
            for (x, y, fw, fh) in found:
                cx, cy = Minv @ np.array([x + fw / 2, y + fh / 2, 1.0])
                faces.append((int((cx - fw / 2) / s), int((cy - fh / 2) / s),
                              int(fw / s), int(fh / s), None))
            break
    return faces


def analyze_photo(photo, g):
    gray = cv2.cvtColor(photo, cv2.COLOR_BGR2GRAY)
    sharp = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    bright = float(gray.mean())
    if os.path.exists(YUNET) and hasattr(cv2, "FaceDetectorYN"):
        detector = "yunet"
        faces = detect_faces_yunet(photo, g.get("min_face_score", 0.6))
    else:
        detector = "haar"
        faces = detect_faces_haar(photo)
    area = photo.shape[0] * photo.shape[1]
    big = [f for f in faces if (f[2] * f[3]) / area >= g["min_face_area_ratio"]]
    return {"detector": detector, "sharpness": round(sharp, 1), "brightness": round(bright, 1),
            "faces": len(faces), "usable_faces": len(big),
            "face_boxes": [list(f[:4]) for f in faces],
            "face_scores": [f[4] for f in faces]}


def parse_text(text):
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    name, age = None, None
    for i, l in enumerate(lines):
        m = re.match(r"^([A-Za-z][^\d,]{0,39}?)\s*[,.\u2018\u2019'`;:]?\s+(\d{2})\b", l)
        if m:
            name, age = m.group(1).strip(), int(m.group(2))
            bio = " ".join(lines[i + 1:])
            return name, age, bio
    return name, age, " ".join(lines)


def vet(report, g):
    reasons = []
    age = report["age"]
    if age is None:
        if g["require_age_detected"]:
            reasons.append("age not detected")
    elif not (g["age_min"] <= age <= g["age_max"]):
        reasons.append(f"age {age} outside {g['age_min']}-{g['age_max']}")
    p = report["photo"]
    if g["require_face_in_photo"] and p["usable_faces"] == 0:
        reasons.append("no clear face in main photo")
    if p["sharpness"] < g["min_photo_sharpness"]:
        reasons.append(f"photo blurry ({p['sharpness']})")
    if not (g["min_photo_brightness"] <= p["brightness"] <= g["max_photo_brightness"]):
        reasons.append(f"photo exposure off ({p['brightness']})")
    bio = (report["bio"] or "").lower()
    for w in g["bio_blocklist"]:
        if w.lower() in bio:
            reasons.append(f"bio contains blocked term '{w}'")
    if g["bio_required_any"] and not any(w.lower() in bio for w in g["bio_required_any"]):
        reasons.append("bio lacks any required term")
    name = (report["name"] or "").lower()
    for w in g["name_blocklist"]:
        if w.lower() in name:
            reasons.append(f"name contains blocked term '{w}'")
    return reasons


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    shot = sys.argv[1]
    cfg = config.load(sys.argv[2] if len(sys.argv) > 2 else None)
    g, llm_cfg = cfg["rules"], cfg["llm"]
    img = cv2.imread(shot)
    if img is None:
        print("ERROR")
        sys.exit(2)

    btn, layout = find_buttons(img)
    if layout is None:
        log("Dating buttons not found (not on Dating swipe screen?)")
        print("NONE")
        return

    hx, hy = btn["LIKE"]
    xx, xy = btn["DISLIKE"]
    H, W = img.shape[:2]

    def region(key):
        y0, y1, x0, x1 = LAYOUTS[layout][key](hx, hy, xx)
        return max(0, y0), min(H, y1), max(0, x0), min(W, x1)

    y0, y1, x0, x1 = region("photo")
    photo = img[y0:y1, x0:x1]
    y0, y1, x0, x1 = region("text")
    text_src = img.copy()
    # Blank out the floating buttons so they don't garble OCR.
    for bx, by in ((hx, hy), (xx, xy)):
        cv2.circle(text_src, (bx, by), 80, (255, 255, 255), -1)
    text_img = text_src[y0:y1, x0:x1]

    raw = ocr(text_img)
    name, age, bio = parse_text(raw)
    report = {"screenshot": shot, "name": name, "age": age, "bio": bio, "ocr_raw": raw,
              "layout": layout, "photo": analyze_photo(photo, g), "buttons": {k: list(v) for k, v in btn.items()}}
    # Stage 1: cheap deterministic rules (age, YuNet face, photo quality, words).
    reasons = vet(report, g)
    report["decision"] = "DISLIKE" if reasons else "LIKE"
    report["reasons"] = reasons
    report["decided_by"] = "rules"

    # Stage 2: local vision LLM judgement, only for profiles that passed the rules.
    if not reasons and llm_judge.enabled(llm_cfg):
        try:
            j = llm_judge.judge(photo, report, llm_cfg)
            report["llm"] = j
            report["decision"] = j["decision"]
            report["decided_by"] = "llm"
            if j["decision"] == "DISLIKE":
                reasons = report["reasons"] = [f"LLM: {j['reason']}"]
            log(f"LLM ({j['model']}, {j['seconds']}s): {j['decision']} - {j['reason']}")
        except Exception as e:  # noqa: BLE001 - any LLM failure must not tap blindly
            report["llm"] = {"error": str(e)}
            on_err = llm_cfg.get("on_error", "skip")
            log(f"LLM error ({e}); on_error={on_err}")
            if on_err == "skip":
                report["decision"] = "SKIP"
                report["decided_by"] = "llm_error"

    base = os.path.splitext(shot)[0]
    # Never overwrite the record of a profile that was already acted on.
    if os.path.exists(base + ".report.json") and "action" in json.load(open(base + ".report.json")):
        base += ".reanalysis"
    with open(base + ".report.json", "w") as f:
        json.dump(report, f, indent=2)
    dbg = photo.copy()
    for (x, y, w, h) in report["photo"]["face_boxes"]:
        cv2.rectangle(dbg, (x, y), (x + w, y + h), (0, 255, 0), 3)
    cv2.imwrite(base + ".faces.png", dbg)

    log(f"name={name!r} age={age} bio={bio!r}")
    log(f"photo={ {k: v for k, v in report['photo'].items() if k != 'face_boxes'} }")
    log(f"decision={report['decision']} reasons={reasons or ['all checks passed']}")
    if report["decision"] == "SKIP":
        print("SKIP")
        return
    x, y = btn[report["decision"]]
    print(f"{report['decision']} {x} {y}")


if __name__ == "__main__":
    main()
