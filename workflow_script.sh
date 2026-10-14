#!/usr/bin/env bash
# Facebook Dating vetting/swiping prototype (Waydroid + ADB).
#
# Usage (from this directory):
#   nix-shell --run "./workflow_script.sh"              # vet 1 profile, dry run (no tap)
#   nix-shell --run "./workflow_script.sh --swipe"      # vet 1 profile and tap LIKE/DISLIKE
#   nix-shell --run "./workflow_script.sh --swipe -n 5" # vet + swipe 5 profiles
set -u
cd "$(dirname "$0")"

# All settings live in config.toml (environment variables override; see config.py).
if [ -f .env ]; then
    echo "ERROR: .env is no longer read. Move its settings into config.toml, then delete .env." >&2
    exit 1
fi
CONFIG_VARS=$(python3 config.py --shell) || { echo "ERROR: could not read config.toml" >&2; exit 1; }
eval "$CONFIG_VARS"

APP_PACKAGE="com.facebook.katana"
SHOT_DIR="./screenshots/runs"
LOG_FILE="./execution_log.md"
SWIPE=0
COUNT=1

while [ $# -gt 0 ]; do
    case "$1" in
        --swipe) SWIPE=1 ;;
        -n) COUNT="$2"; shift ;;
        *) echo "unknown arg $1"; exit 1 ;;
    esac
    shift
done

# Choose the ADB device. Waydroid mode uses ADB_DEVICE (the Waydroid address).
# Otherwise one online device is used automatically; with several, the user is asked every run
# (ADB_DEVICE, if set, is the default choice).
select_device() {
    if [ "$WAYDROID_MODE" = "1" ]; then
        if [ -z "${ADB_DEVICE:-}" ]; then
            echo "ERROR: Waydroid mode requires adb_device in config.toml (e.g. \"192.168.240.112:5555\")." >&2
            exit 1
        fi
        DEVICE="$ADB_DEVICE"
        return 0
    fi
    local serials=() labels=() serial state info model
    while read -r serial state info; do
        [ "$state" = "device" ] || continue
        model=$(echo "$info" | sed -n 's/.*model:\([^ ]*\).*/\1/p')
        serials+=("$serial")
        labels+=("$serial  ${model:-unknown model}")
    done < <(timeout 15 adb devices -l | tail -n +2)

    if [ "${#serials[@]}" -eq 0 ]; then
        echo "ERROR: no online ADB device. Connect a phone or start Waydroid, then check 'adb devices'." >&2
        exit 1
    fi
    if [ "${#serials[@]}" -eq 1 ]; then
        DEVICE="${serials[0]}"
        echo "Using the only online ADB device: $DEVICE" >&2
        return 0
    fi
    if [ ! -t 0 ]; then
        echo "ERROR: several ADB devices are online and there is no terminal to ask. Run interactively." >&2
        exit 1
    fi

    local default_idx=0 i choice
    echo "Several ADB devices are online:" >&2
    for i in "${!serials[@]}"; do
        echo "  $((i + 1))) ${labels[$i]}" >&2
        [ "${serials[$i]}" = "${ADB_DEVICE:-}" ] && default_idx=$i
    done
    read -r -p "Choose device [$((default_idx + 1))]: " choice
    choice="${choice:-$((default_idx + 1))}"
    if ! [[ "$choice" =~ ^[0-9]+$ ]] || [ "$choice" -lt 1 ] || [ "$choice" -gt "${#serials[@]}" ]; then
        echo "ERROR: invalid choice '$choice'." >&2
        exit 1
    fi
    DEVICE="${serials[$((choice - 1))]}"
    echo "Selected $DEVICE" >&2
}
select_device

# Every adb call is wrapped in a timeout so a hung device fails fast instead of blocking forever.
ADB="timeout 20 adb -s $DEVICE"
RUN_ID="run_$(date +%Y%m%d_%H%M%S)"
RUN_DIR="$SHOT_DIR/$RUN_ID"
mkdir -p "$RUN_DIR/nav"
log() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$LOG_FILE"; }

capture() { $ADB exec-out screencap -p > "$1"; }
vet() { python3 vet_profile.py "$1" 2>&1 | tee -a "$LOG_FILE" | tail -n 1; }

# Is the ADB device listed as online ('device' state)?
device_ready() {
    $ADB devices | awk -v d="$DEVICE" '$1 == d && $2 == "device" {ok=1} END {exit !ok}'
}

# WAYDROID_MODE=1: make sure the Waydroid session is running and ADB can reach it.
# The container must be started manually as root (see README: sudo waydroid container start).
start_waydroid() {
    [ "$WAYDROID_MODE" = "1" ] || return 0
    if device_ready; then log "Waydroid device $DEVICE already ready"; return 0; fi
    if ! command -v waydroid >/dev/null 2>&1; then
        log "ERROR: 'waydroid' not found on PATH. Install Waydroid or set waydroid = false in config.toml."
        exit 1
    fi
    if [ "$(waydroid status 2>/dev/null | awk '/^Session:/ {print $2}')" != "RUNNING" ]; then
        log "Starting Waydroid session (background)"
        waydroid session start >/dev/null 2>&1 &
    fi
    for i in $(seq 1 30); do
        $ADB connect "$DEVICE" >/dev/null 2>&1
        if device_ready; then log "Waydroid ready at $DEVICE"; return 0; fi
        sleep 1
    done
    log "ERROR: $DEVICE not ready after 30s. Check 'waydroid status' (container must be running: sudo waydroid container start)."
    exit 1
}

log "=== Facebook Dating workflow start ($RUN_ID, swipe=$SWIPE count=$COUNT) ==="
start_waydroid
$ADB connect "$DEVICE" >/dev/null 2>&1

# Pre-flight: fail fast (10s timeout) if the LLM server is down, before touching the phone.
check_llm() {
    [ "$LLM_ENABLED" = 0 ] && return 0
    local url="${LLM_URL%/}" model="$LLM_MODEL"
    if curl -s -m 10 "$url/models" | grep -qF "\"$model\""; then
        log "LLM reachable at $url ($model)"
        return 0
    fi
    log "ERROR: LLM $model not reachable at $url (10s check). Start the server and retry."
    exit 1
}
check_llm

# Lock the display to a fixed portrait size so screenshots/templates are consistent.
# Restored on exit unless keep_display (KEEP_DISPLAY=1).
restore_display() {
    if [ "$KEEP_DISPLAY" != 1 ]; then
        $ADB shell wm size reset; $ADB shell wm density reset
        log "Display restored"
    fi
}
finish() {
    restore_display
    log "=== workflow end ==="
    python3 summarize_run.py "$RUN_DIR" | tee -a "$LOG_FILE"
}
trap finish EXIT
$ADB shell wm size "$SCREEN_SIZE"
$ADB shell wm density "$SCREEN_DENSITY"
$ADB shell settings put system accelerometer_rotation 0
$ADB shell settings put system user_rotation 0
log "Display locked to $SCREEN_SIZE @ ${SCREEN_DENSITY}dpi (portrait)"
$ADB shell cmd statusbar collapse >/dev/null 2>&1

# 1. Open Dating via deep link (confirmed working; opens ImmersiveReactActivity).
log "Opening Dating via fb://dating deep link"
$ADB shell am start -a android.intent.action.VIEW -d "fb://dating" "$APP_PACKAGE" >/dev/null 2>&1
sleep 6

# 2. Navigate to the Dating swipe screen (verified visually by finding the buttons).
navigate() {
    local probe="$RUN_DIR/nav/probe_$(date +%H%M%S).png"
    local result
    for attempt in 1 2 3 4; do
        capture "$probe"
        result=$(vet "$probe")
        [ "$result" = "LIMIT" ] && return 2
        [ "$result" != "NONE" ] && return 0
        log "Not on Dating card screen (attempt $attempt); retrying deep link"
        $ADB shell cmd statusbar collapse >/dev/null 2>&1
        $ADB shell am start -a android.intent.action.VIEW -d "fb://dating" "$APP_PACKAGE" >/dev/null 2>&1
        sleep 5
    done
    return 1
}

navigate
case $? in
    0) ;;
    2) log "Daily like limit reached (Facebook says come back tomorrow); stopping"
       exit 0 ;;
    *) log "ERROR: could not reach the Dating swipe screen"
       exit 1 ;;
esac

# 3. Vet (and optionally swipe) profiles.
for i in $(seq 1 "$COUNT"); do
    SHOT="$RUN_DIR/profile_$(printf %02d "$i")_$(date +%H%M%S).png"
    capture "$SHOT"
    log "[profile $i] captured $SHOT"
    RESULT=$(vet "$SHOT")
    read -r ACTION X Y <<< "$RESULT"
    log "[profile $i] decision: $RESULT (report: ${SHOT%.png}.report.json)"

    case "$ACTION" in
        LIKE|DISLIKE)
            if [ "$SWIPE" = 1 ]; then
                log "[profile $i] tapping $ACTION at $X,$Y"
                $ADB shell input tap "$X" "$Y"
                python3 summarize_run.py --mark "${SHOT%.png}.report.json" "$ACTION"
                sleep 4
            else
                log "[profile $i] dry run - not tapping (use --swipe)"
                break
            fi
            ;;
        SKIP)
            log "[profile $i] LLM unavailable/failed - not tapping; stopping"
            break ;;
        LIMIT)
            log "[profile $i] daily like limit reached (Facebook says come back tomorrow); stopping"
            break ;;
        NONE)
            log "[profile $i] no profile card visible (out of profiles or a popup?); stopping"
            break ;;
        *)
            log "[profile $i] analysis error: $RESULT"; break ;;
    esac
done
