#!/usr/bin/env python3
"""Offline regression tests (no phone, no LLM needed).

Run from the project root:  nix-shell --run "python3 tests/run_tests.py"
"""
import contextlib
import io
import os
import subprocess
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
import cv2  # noqa: E402

import config  # noqa: E402
import vet_profile as vp  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures")
failures = 0


def check(name, cond, detail=""):
    global failures
    print(f"  [{'PASS' if cond else 'FAIL'}] {name} {detail}")
    failures += 0 if cond else 1


def quiet(fn, *a):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a)


print("Button detection / layout")
btn, layout = quiet(vp.find_buttons, cv2.imread(f"{FIX}/card_layout.png"))
check("card layout", layout == "card" and btn.get("LIKE") == (943, 1291), f"{layout} {btn}")
btn, layout = quiet(vp.find_buttons, cv2.imread(f"{FIX}/profile_layout.png"))
check("profile layout", layout == "profile" and btn.get("DISLIKE") == (387, 1704), f"{layout} {btn}")
btn, layout = quiet(vp.find_buttons, cv2.imread(f"{FIX}/home_screen.png"))
check("home screen -> no buttons", layout is None, f"{layout} {btn}")

print("Name/age parsing")
for text, exp in [("Hannah, 25\nbio", ("Hannah", 25)), ("Katy\u2018 45 Second Look", ("Katy", 45)),
                  ("Mary Ann, 29", ("Mary Ann", 29)), ("Just joined\nAlice, 31", ("Alice", 31))]:
    got = vp.parse_text(text)[:2]
    check(repr(text), got == exp, f"-> {got}")

print("Face detection (YuNet)")
g = config.load()["rules"]
for fx, region in (("card_layout", (288, 1291, 40, 1040)), ("profile_layout", (65, 1361, 0, 1080))):
    y0, y1, x0, x1 = region
    p = vp.analyze_photo(cv2.imread(f"{FIX}/{fx}.png")[y0:y1, x0:x1], g)
    check(f"{fx}: exactly one face", p["usable_faces"] == 1, f"{p['detector']} {p['face_scores']}")

print("End-to-end with mock LLM")
mock = subprocess.Popen([sys.executable, "tests/mock_llm.py"], stdout=subprocess.DEVNULL)
time.sleep(1.5)
env = dict(os.environ, LLM_ENABLED="1", LLM_URL="http://127.0.0.1:18080/v1")
out = subprocess.run([sys.executable, "vet_profile.py", f"{FIX}/profile_layout.png"],
                     capture_output=True, text=True, env=env).stdout.strip().splitlines()[-1]
check("mock LLM DISLIKE is honoured", out == "DISLIKE 387 1704", out)
mock.terminate()
mock.wait()
out = subprocess.run([sys.executable, "vet_profile.py", f"{FIX}/profile_layout.png"],
                     capture_output=True, text=True, env=env).stdout.strip().splitlines()[-1]
check("LLM down -> SKIP (no tap)", out == "SKIP", out)

for f in os.listdir(FIX):  # tidy report artefacts
    if f.endswith((".report.json", ".faces.png")):
        os.remove(os.path.join(FIX, f))

print(f"\n{'ALL PASSED' if not failures else f'{failures} FAILURE(S)'}")
sys.exit(1 if failures else 0)
