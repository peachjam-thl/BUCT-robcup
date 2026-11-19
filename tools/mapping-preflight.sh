#!/usr/bin/env bash
# Read-only mapping inventory. No launches, installs, parameter changes, or cmd_vel publications.
# Usage: bash mapping-preflight.sh [--observe]
# Optional: SCAN_TOPIC, ODOM_FRAME, BASE_FRAME, LIDAR_FRAME. Defaults are candidates, not verified.
set +e
export LC_ALL=C
observe=0
case "${1:-}" in
  "") ;;
  --observe) observe=1 ;;
  -h|--help)
    printf 'Usage: bash mapping-preflight.sh [--observe]\nNo motion or readiness approval. See docs/示例场地建图准备.md.\n'
    exit 0 ;;
  *) printf 'Unknown option: %s\n' "$1" >&2; exit 2 ;;
esac
if [ "$#" -gt 1 ]; then
  printf 'Only --observe or --help is accepted.\n' >&2
  exit 2
fi
if ! command -v timeout >/dev/null 2>&1 || ! command -v ros2 >/dev/null 2>&1; then
  printf 'Missing timeout or ros2. Load the already installed ROS environment first; nothing was changed.\n' >&2
  exit 1
fi
run() {
  local result
  printf '\n$'; printf ' %q' "$@"; printf '\n'
  "$@" 2>&1
  result=$?
  printf '[exit=%s; timeout=124; not a readiness result]\n' "$result"
}
printf 'Mapping inventory: %s\n' "$(date -Iseconds)"
printf 'ROS_DISTRO=%s ROS_DOMAIN_ID=%s\n' "${ROS_DISTRO:-unset}" "${ROS_DOMAIN_ID:-default}"
printf 'No robot drivers or mapping nodes are launched. Empty graph / missing packages are evidence only.\n'

for package in turn_on_wheeltec_robot wheeltec_robot_slam lslidar_driver slam_toolbox nav2_map_server robot_localization; do
  printf '\n--- package: %s ---\n' "$package"
  prefix=$(timeout 5s ros2 pkg prefix "$package" 2>/dev/null)
  result=$?
  if [ "$result" -ne 0 ] || [ -z "$prefix" ]; then
    printf 'Not resolved in current shell (exit=%s). Not an installation diagnosis.\n' "$result"
    continue
  fi
  printf 'prefix=%s\n' "$prefix"
  # Read installed launch/config names only; do not import or execute their contents.
  find "$prefix/share/$package" -maxdepth 4 \( -type f -o -type l \) \
    \( -name '*.launch.py' -o -name '*.launch.xml' -o -name '*.yaml' \) -print 2>/dev/null | head -n 35
done
run timeout 8s ros2 node list
run timeout 8s ros2 topic list -t
run timeout 8s ros2 service list -t

if [ "$observe" -eq 1 ]; then
  scan_topic="${SCAN_TOPIC:-/scan}"
  odom_frame="${ODOM_FRAME:-odom_combined}"
  base_frame="${BASE_FRAME:-base_footprint}"
  printf '\nCandidate scan=%s odom_frame=%s base_frame=%s lidar_frame=%s\n' \
    "$scan_topic" "$odom_frame" "$base_frame" "${LIDAR_FRAME:-not-specified}"
  printf 'Inspect actual headers and TF. This does not prove freshness, correct extrinsics, or unique TF ownership.\n'
  run timeout 5s ros2 topic info "$scan_topic" --verbose
  run timeout 5s ros2 topic echo "$scan_topic" --field header --once
  run timeout 5s ros2 topic echo /odom --field header --once
  run timeout 5s ros2 run tf2_ros tf2_echo "$odom_frame" "$base_frame"
  if [ -n "${LIDAR_FRAME:-}" ]; then
    run timeout 5s ros2 run tf2_ros tf2_echo "$base_frame" "$LIDAR_FRAME"
  else
    printf '\nLIDAR_FRAME not specified: base-to-lidar query skipped; read the LaserScan header first.\n'
  fi
fi
printf '\nInventory finished. No automatic PASS. Physical stop, scan quality, TF and mapping remain manual checks.\n'
exit 0
