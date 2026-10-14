#!/usr/bin/env python3
"""Build a Markdown summary table for one workflow run.

Usage: python3 summarize_run.py <run_dir>
       python3 summarize_run.py --mark <report.json> <action>   (record the tap actually made)

Reads every *.report.json in <run_dir> (written by vet_profile.py), prints the
table and writes it to <run_dir>/summary.md.
"""
import glob
import json
import os
import sys


def cell(s, width=None):
    s = "" if s is None else str(s)
    s = s.replace("|", "/").replace("\n", " ").strip()
    if width and len(s) > width:
        s = s[: width - 1] + "…"
    return s


def mark(path, action):
    r = json.load(open(path))
    r["action"] = action
    with open(path, "w") as f:
        json.dump(r, f, indent=2)


def main():
    if sys.argv[1] == "--mark":
        mark(sys.argv[2], sys.argv[3])
        return
    run_dir = sys.argv[1]
    reports = sorted(glob.glob(os.path.join(run_dir, "profile_*.report.json")))
    rows, counts, llm_times, reanalysed = [], {}, [], False
    for i, path in enumerate(reports, 1):
        r = json.load(open(path))
        llm = r.get("llm") or {}
        decision = r.get("decision", "?")
        counts[decision] = counts.get(decision, 0) + 1
        if "seconds" in llm:
            llm_times.append(llm["seconds"])
            tries = f", {llm['attempts']} tries" if llm.get("attempts", 1) > 1 else ""
            by = f"LLM ({llm['seconds']:.1f}s{tries})"
        elif "error" in llm:
            by = "LLM error"
        else:
            by = "rules"
        if r.get("note"):
            by += " *"
            reanalysed = True
        if r.get("reasons"):
            reason = "; ".join(x.removeprefix("LLM: ") for x in r["reasons"])
        else:
            reason = llm.get("reason") or "all rule checks passed"
        name_age = f"{cell(r.get('name')) or '?'}, {r.get('age') or '?'}"
        faces = r.get("photo", {}).get("usable_faces", "?")
        action = r.get("action", "not tapped")
        rows.append(f"| {i} | {name_age} | {r.get('layout', '?')} | {faces} | "
                    f"{by} | **{decision}** | {action} | {cell(reason, 90)} |")

    out = [f"## Run summary: {os.path.basename(os.path.normpath(run_dir))}", ""]
    if rows:
        out += ["| # | Profile | Layout | Faces | Decided by | Decision | Action | Reason |",
                "|---|---|---|---|---|---|---|---|", *rows, ""]
        totals = ", ".join(f"{k}: {v}" for k, v in sorted(counts.items()))
        out.append(f"**Profiles:** {len(rows)}  |  **{totals}**")
        if llm_times:
            out.append(f"**LLM time:** avg {sum(llm_times) / len(llm_times):.1f}s, "
                       f"max {max(llm_times):.1f}s over {len(llm_times)} call(s)")
        if reanalysed:
            out.append("\\* re-analysed after the run; see the report's \"note\".")
    else:
        out.append("_No profiles were vetted in this run._")
    text = "\n".join(out) + "\n"
    with open(os.path.join(run_dir, "summary.md"), "w") as f:
        f.write(text)
    print(text)


if __name__ == "__main__":
    main()
