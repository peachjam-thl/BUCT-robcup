#!/usr/bin/env bash
# Restore only the confirmed Ubuntu 22.04 arm64 main source list.
# Default: read-only checks. --apply: back up first, then atomic replacement.
# No apt update/install/upgrade, key changes, or robot/network service changes.
set -euo pipefail
apt_restore_mode="${1:---check}"
if [ "$#" -gt 1 ]; then printf 'One option only: --check, --apply, --help\n' >&2; exit 2; fi
case "$apt_restore_mode" in
  --help|-h)
    printf 'Usage: bash restore_apt_sources.sh [--check | --apply]\n'
    printf 'Ubuntu jammy arm64 only. --apply requires sudo, preserves sources.list.d, and keeps a backup.\n'
    exit 0 ;;
  --check|--apply) ;;
  *) printf 'Unknown option: %s\n' "$apt_restore_mode" >&2; exit 2 ;;
esac
if [ "$apt_restore_mode" = --apply ] && [ "$EUID" -ne 0 ]; then
  printf 'Use sudo bash restore_apt_sources.sh --apply\n' >&2; exit 1
fi
[ "$(dpkg --print-architecture)" = arm64 ] || { printf 'STOP: expected arm64.\n' >&2; exit 1; }
apt_restore_codename=$(awk -F= '$1=="VERSION_CODENAME" {gsub(/"/,"",$2); print $2}' /etc/os-release)
[ "$apt_restore_codename" = jammy ] || { printf 'STOP: expected Ubuntu jammy.\n' >&2; exit 1; }
[ -f /etc/apt/sources.list ] && [ ! -L /etc/apt/sources.list ] || {
  printf 'STOP: main sources.list must be a regular non-symlink file.\n' >&2; exit 1;
}
[ -s /usr/share/keyrings/ubuntu-archive-keyring.gpg ] || {
  printf 'STOP: Ubuntu archive keyring missing or empty; no sources changed.\n' >&2; exit 1;
}
[ -d /etc/apt/sources.list.d ] || { printf 'STOP: sourceparts directory missing.\n' >&2; exit 1; }
printf 'Target: Ubuntu jammy arm64. Main sources.list: %s bytes.\n' "$(stat -c %s /etc/apt/sources.list)"
printf 'Base/updates: HTTPS TUNA ubuntu-ports; security: HTTPS official Ubuntu ports.\n'
printf 'ROS/RDK sourceparts and keyrings stay unchanged. No package operation is performed.\n'
if [ "$apt_restore_mode" = --check ]; then
  printf 'CHECK OK. To back up and replace the main file: sudo bash %q --apply\n' "$0"
  exit 0
fi

apt_restore_backup=$(mktemp -d "/etc/apt/sources-backup-$(date +%Y%m%d-%H%M%S)-XXXXXX")
cp -a -- /etc/apt/sources.list "$apt_restore_backup/sources.list"
cp -a -- /etc/apt/sources.list.d "$apt_restore_backup/sources.list.d"
printf 'BACKUP: %s\n' "$apt_restore_backup"
sha256sum -- "$apt_restore_backup/sources.list"

apt_restore_staging=$(mktemp /etc/apt/sources.list.restore-XXXXXX)
trap 'rm -f -- "$apt_restore_staging"' EXIT
cat > "$apt_restore_staging" <<'APT_SOURCES'
# Restored for Ubuntu 22.04 jammy arm64. Original files are backed up under /etc/apt/sources-backup-*.
deb [arch=arm64 signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] https://mirrors.tuna.tsinghua.edu.cn/ubuntu-ports/ jammy main restricted universe multiverse
deb [arch=arm64 signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] https://mirrors.tuna.tsinghua.edu.cn/ubuntu-ports/ jammy-updates main restricted universe multiverse
deb [arch=arm64 signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] https://ports.ubuntu.com/ubuntu-ports/ jammy-security main restricted universe multiverse
APT_SOURCES
chmod 0644 "$apt_restore_staging"
sync -f "$apt_restore_staging"
mv -T -- "$apt_restore_staging" /etc/apt/sources.list
sync -f /etc/apt/sources.list
printf 'RESTORED: /etc/apt/sources.list\n'
printf 'Backup retained: %s\n' "$apt_restore_backup"
printf 'Next: sudo apt-get update. Stop and share any errors; do not bypass signatures/TLS or upgrade the system.\n'
