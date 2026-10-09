#!/usr/bin/env bash
# Facebook Dating vetting/swiping prototype (Waydroid + ADB).
#
# Usage (from this directory):
#   nix-shell --run "./workflow_script.sh"              # vet 1 profile, dry run (no tap)
#   nix-shell --run "./workflow_script.sh --swipe"      # vet 1 profile and tap LIKE/DISLIKE
#   nix-shell --run "./workflow_script.sh --swipe -n 5" # vet + swipe 5 profiles
set -u
cd "$(dirname "$0")"

# Load environment variables from .env if it exists
if [ -f .env ]; then
    while IFS='=' read -r key value || [ -n "$key" ]; do
        # Skip comments and empty lines
        [[ "$key" =~ ^#.*$ ]] || [ -z "$key" ] && continue
        # Remove potential carriage returns from Windows-style files
        value=$(echo "$value" | tr -d '\r')
        export "$key=$value"
    done < .env
fi

DEVICE="${ADB_DEVICE:-192.168.240.112:5555}"
WAYDROID_MODE="${WAYDROID_MODE:-0}"
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
        log "ERROR: 'waydroid' not found on PATH. Install Waydroid or set WAYDROID_MODE=0."
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

# Lock the display to a fixed portrait size so screenshots/templates are consistent.
# Restored on exit unless KEEP_DISPLAY=1.
SCREEN_SIZE="${SCREEN_SIZE:-1080x1920}"
SCREEN_DENSITY="${SCREEN_DENSITY:-320}"
restore_display() {
    if [ "${KEEP_DISPLAY:-0}" != 1 ]; then
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
    for attempt in 1 2 3 4; do
        capture "$probe"
        if [ "$(vet "$probe")" != "NONE" ]; then return 0; fi
        log "Not on Dating card screen (attempt $attempt); retrying deep link"
        $ADB shell cmd statusbar collapse >/dev/null 2>&1
        $ADB shell am start -a android.intent.action.VIEW -d "fb://dating" "$APP_PACKAGE" >/dev/null 2>&1
        sleep 5
    done
    return 1
}

if ! navigate; then
    log "ERROR: could not reach the Dating swipe screen"
    exit 1
fi

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
        NONE)
            log "[profile $i] no profile card visible (out of profiles or a popup?); stopping"
            break ;;
        *)
            log "[profile $i] analysis error: $RESULT"; break ;;
    esac
done
