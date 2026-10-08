#!/usr/bin/env python3
"""Re-capture the LIKE/DISLIKE button templates from a screenshot.

Only needed if the locked screen size/density or Facebook's button design changes.

Usage: python3 tools/make_templates.py <screenshot.png> <layout> <x_cx> <x_cy> <heart_cx> <heart_cy>
  layout: card    -> writes templates/x_mark.png,   templates/heart.png   (crop 100px)
          profile -> writes templates/x_mark_2.png, templates/heart_2.png (crop 108px)
Button centres can be read from an existing report.json ("buttons") or measured by eye.
Afterwards update LAYOUTS spacing in vet_profile.py if the gap between buttons changed.
"""
import os
import sys

import cv2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    if len(sys.argv) != 7:
        print(__doc__)
        sys.exit(1)
    img = cv2.imread(sys.argv[1])
    layout = sys.argv[2]
    xc, xy, hc, hy = map(int, sys.argv[3:])
    size, suffix = {"card": (100, ""), "profile": (108, "_2")}[layout]
    r = size // 2
    for name, (cx, cy) in (("x_mark", (xc, xy)), ("heart", (hc, hy))):
        out = os.path.join(ROOT, "templates", f"{name}{suffix}.png")
        cv2.imwrite(out, img[cy - r:cy + r, cx - r:cx + r])
        print("wrote", out)


if __name__ == "__main__":
    main()
