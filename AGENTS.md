# Operator instructions: Facebook Dating vetting & swiping

You operate an existing, working pipeline. **Do not write new code. Do not edit files.**
Run the commands below, read the output, and follow the tables.

Working directory: `/home/angel/pi/dater`. Every command must start with `nix-shell --run`.

## Hard rules
1. Never tap the phone yourself (`adb shell input ...`). Only `workflow_script.sh` taps.
2. Never edit `config.toml`, `*.py`, `*.sh` or anything in `templates/` or `models/`.
3. Never delete anything in `screenshots/runs/` or `execution_log.md`.
4. Never change anything on the host outside this directory.
5. If something is not covered below: **stop and report**. Do not improvise.

## Step 1 – Health check (always run first)
```
nix-shell --run "python3 tests/run_tests.py"
```
- Last line `ALL PASSED` → go to Step 2.
- Anything else → **stop**. Report the `[FAIL]` lines.

## Step 2 – Check the phone and the LLM
```
adb devices
curl -s -m 10 http://192.168.1.110:9931/v1/models | grep -o '"id":"gemma-4-26B-A4B-it"'
```
- `adb devices` must list `192.168.240.112:5555  device`. If not, run
  `adb connect 192.168.240.112:5555` once and check again. Still missing → **stop**.
- The curl must print `"id":"gemma-4-26B-A4B-it"`. If empty → **stop** (LLM server down).

## Step 3 – Dry run (vets 1 profile, no tap)
```
nix-shell --run "KEEP_DISPLAY=1 ./workflow_script.sh"
```
Must contain `[profile 1] decision: LIKE` or `decision: DISLIKE` and end with a
`## Run summary` table. Otherwise use the table in Step 5.

## Step 4 – Swipe run
```
nix-shell --run "KEEP_DISPLAY=1 ./workflow_script.sh --swipe -n 10"
```
- Use `-n 10` unless the user asked for a different number. Maximum `-n 25` per run.
- Takes about 20–30 seconds per profile. Use a timeout of at least `30 × n + 60` seconds.
- Between runs wait at least 60 seconds.

## Step 5 – Read the result
Find the last log line starting with `[profile N]` before `=== workflow end ===`.

| Output contains | Meaning | What you do |
|---|---|---|
| `## Run summary` with all rows LIKE/DISLIKE and `-n` rows | Success | Report the summary table to the user |
| `LLM unavailable/failed - not tapping` | LLM server problem | Redo Step 2. Do not rerun until the curl works |
| `no profile card visible` | Out of profiles, or a pop-up is covering the screen | **Stop.** Report it. Do not retry |
| `ERROR: could not reach the Dating swipe screen` | Navigation failed | Rerun Step 3 once. Fails again → **stop** |
| `analysis error` | Unexpected | **Stop.** Report the line |
| `error: no devices` / `device offline` | ADB lost | Redo Step 2 |

## Step 6 – Report to the user
Always include:
1. The `## Run summary` table, copied exactly (it is also saved as `summary.md` in the run folder).
2. The run folder path (`screenshots/runs/run_...`).
3. Anything unusual: a profile shown as `?, ?` (age not read), any `SKIP`, or a profile that also appeared in an earlier run.

## Reference (read only if needed)
- Decision order: buttons found → name/age/bio read → `[rules]` in `config.toml` → LLM → tap.
- Profiles that fail a rule are disliked **without** asking the LLM. That is expected.
- `KEEP_DISPLAY=1` keeps the phone at 1080x1920. To restore the normal screen afterwards:
  `adb shell wm size reset && adb shell wm density reset`
- Full details: `README.md`.
