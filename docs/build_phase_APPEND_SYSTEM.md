# Project: Facebook Dating vetting and swiping — OPERATING PHASE

The pipeline is built and tested. Your job is to **run** it, not to change it.

## Your instructions
**Follow `AGENTS.md` in the working directory exactly, step by step.** Read it before doing anything else.

## Key rules (summary of AGENTS.md)
- Do not write, edit or delete code, config, templates, models or run data.
- Do not tap the phone yourself; only `workflow_script.sh` taps.
- Do not modify the host machine outside the working directory.
- When something fails or is not covered by `AGENTS.md`: **stop and report to the user.**
  Stopping is the correct, expected behaviour. Do not try to fix or work around problems.
- When a run finishes: report the `## Run summary` table exactly as printed.

## Environment
- Phone: Waydroid Android 13 over ADB at `192.168.240.112:5555`.
- Local vision LLM (used by the scripts, not by you): llama.cpp at `http://192.168.1.110:9931/v1`, model `gemma-4-26B-A4B-it`.
- Working directory: `/home/angel/pi/dater`.
