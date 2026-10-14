#!/usr/bin/env bash
# Offline tests for select_device() in workflow_script.sh. No phone, no adb server needed.
# A fake `adb` on PATH prints whatever device list the test provides.
#
# Run from the project root:  nix-shell --run "bash tests/test_device_select.sh"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT="$ROOT/workflow_script.sh"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
failures=0

# Fake adb: `adb devices -l` prints the file named in $FAKE_DEVICES.
cat > "$TMP/adb" <<'EOF'
#!/usr/bin/env bash
[ "$1" = devices ] && cat "$FAKE_DEVICES"
EOF
chmod +x "$TMP/adb"

# Load the real function body from the script.
sed -n '/^select_device()/,/^}/p' "$SCRIPT" > "$TMP/select_device.sh"

write_devices() {  # $1 = path; remaining args = adb devices -l lines
    local path="$1"; shift
    { echo "List of devices attached"; printf '%s\n' "$@"; echo; } > "$path"
}

# run_case NAME EXPECT_RC EXPECT_TEXT [env assignments...] -- devices lines
# Runs select_device with stdin from $STDIN_MODE (tty-less by default).
run_case() {
    local name="$1" want_rc="$2" want_text="$3"; shift 3
    local envs=() devs=()
    while [ $# -gt 0 ] && [ "$1" != "--" ]; do envs+=("$1"); shift; done
    shift
    devs=("$@")
    write_devices "$TMP/devices.txt" "${devs[@]}"

    local out rc
    out=$(env -u ADB_DEVICE -u WAYDROID_MODE "${envs[@]}" FAKE_DEVICES="$TMP/devices.txt" \
          PATH="$TMP:$PATH" bash -c 'source "$1"; select_device; echo "DEVICE=$DEVICE"' _ "$TMP/select_device.sh" < /dev/null 2>&1)
    rc=$?
    if [ "$rc" = "$want_rc" ] && [[ "$out" == *"$want_text"* ]]; then
        echo "  [PASS] $name"
    else
        echo "  [FAIL] $name (rc=$rc want=$want_rc)"; echo "$out" | sed 's/^/         /'
        failures=$((failures + 1))
    fi
}

echo "Device picker (select_device)"

run_case "0 devices -> error" 1 "no online ADB device" -- \
    "" 

run_case "1 device -> used automatically" 0 "DEVICE=R5CX41TYPSR" -- \
    "R5CX41TYPSR            device usb:1-2 product:e3qsqw model:SM_S928U device:e3q transport_id:31"

run_case "offline/unauthorized ignored -> 1 usable device" 0 "DEVICE=192.168.240.112:5555" -- \
    "R5CX41TYPSR            offline" \
    "192.168.240.112:5555   device product:lineage_waydroid_x86_64 model:WayDroid_x86_64_Device device:waydroid_x86_64 transport_id:1" \
    "ABC123                 unauthorized usb:1-3 transport_id:4"

run_case "2 devices, no terminal -> error" 1 "no terminal to ask" -- \
    "R5CX41TYPSR            device usb:1-2 model:SM_S928U transport_id:31" \
    "192.168.240.112:5555   device model:WayDroid_x86_64_Device transport_id:1"

run_case "Waydroid mode without ADB_DEVICE -> error" 1 "requires adb_device" WAYDROID_MODE=1 -- \
    "192.168.240.112:5555   device model:WayDroid_x86_64_Device transport_id:1"

run_case "Waydroid mode uses ADB_DEVICE, no picker" 0 "DEVICE=192.168.240.112:5555" WAYDROID_MODE=1 ADB_DEVICE=192.168.240.112:5555 -- \
    "R5CX41TYPSR            device model:SM_S928U transport_id:31" \
    "192.168.240.112:5555   device model:WayDroid_x86_64_Device transport_id:1"

echo
if [ "$failures" = 0 ]; then echo "ALL PASSED"; else echo "$failures FAILURE(S)"; fi
exit "$failures"
