#!/bin/sh
# Runs as root via sudo (NOPASSWD rule). Changes the password of the calling user,
# but only while that user is still listed as "must change password".
# Exit codes: 0 ok, 1 not allowed, 2 password too short or still the default.
set -eu

FLAG=/var/lib/easylinux/must-change-password
DEFAULTS=/var/lib/easylinux/default-passwords   # "user:defaultpassword", root-only
user="${SUDO_USER:-}"

[ -n "$user" ] || exit 1
grep -qx "$user" "$FLAG" 2>/dev/null || exit 1

IFS= read -r pw || true
[ "${#pw}" -ge 8 ] || exit 2
if grep -qxF "$user:$pw" "$DEFAULTS" 2>/dev/null; then
  exit 2
fi

printf '%s:%s\n' "$user" "$pw" | chpasswd

grep -vx "$user" "$FLAG" > "$FLAG.new" || true
mv "$FLAG.new" "$FLAG"
grep -v "^$user:" "$DEFAULTS" > "$DEFAULTS.new" || true
mv "$DEFAULTS.new" "$DEFAULTS"
chmod 600 "$DEFAULTS"
