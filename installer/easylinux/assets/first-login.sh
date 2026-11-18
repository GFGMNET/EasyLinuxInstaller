#!/bin/sh
# EasyLinux first login: the default password from the profile is public, so the
# user must set a new one. This window opens after every login until that is done.
# (The password is not marked as expired, because KDE's login screen cannot handle that.)

FLAG=/var/lib/easylinux/must-change-password
SETPW="${EASYLINUX_SETPW:-/usr/local/sbin/easylinux-set-password}"
ME="$(id -un)"

grep -qx "$ME" "$FLAG" 2>/dev/null || exit 0

# only one window at a time
exec 9>"${XDG_RUNTIME_DIR:-/tmp}/easylinux-first-login.lock"
flock -n 9 || exit 0

case "${LANG:-}" in
  de*)
    TITLE="Neues Passwort festlegen"
    TEXT="Das Standardpasswort ist öffentlich bekannt.\nBitte jetzt ein eigenes Passwort festlegen."
    P1="Neues Passwort"; P2="Passwort wiederholen"
    MISMATCH="Die Passwörter sind leer oder stimmen nicht überein."
    SHORT="Das Passwort muss mindestens 8 Zeichen haben und darf nicht das Standardpasswort sein."
    MUST="Ein neues Passwort ist erforderlich."
    OK="Das Passwort wurde geändert."
    FAIL="Das Passwort konnte nicht geändert werden."
    ;;
  *)
    TITLE="Set a new password"
    TEXT="The default password is publicly known.\nPlease set your own password now."
    P1="New password"; P2="Repeat password"
    MISMATCH="The passwords are empty or do not match."
    SHORT="The password must have at least 8 characters and must not be the default password."
    MUST="A new password is required."
    OK="Your password has been changed."
    FAIL="The password could not be changed."
    ;;
esac

SEP="$(printf '\037')"
sleep 3   # let the desktop finish starting
while grep -qx "$ME" "$FLAG" 2>/dev/null; do
  out="$(zenity --forms --title="$TITLE" --text="$TEXT" \
          --add-password="$P1" --add-password="$P2" --separator="$SEP")" || {
    zenity --warning --title="$TITLE" --text="$MUST"
    continue
  }
  p1="${out%%"$SEP"*}"
  p2="${out#*"$SEP"}"
  if [ -z "$p1" ] || [ "$p1" != "$p2" ]; then
    zenity --error --title="$TITLE" --text="$MISMATCH"
    continue
  fi
  if printf '%s\n' "$p1" | sudo -n "$SETPW"; then rc=0; else rc=$?; fi
  if [ "$rc" -eq 0 ]; then
    zenity --info --title="$TITLE" --text="$OK"
  elif [ "$rc" -eq 2 ]; then
    zenity --error --title="$TITLE" --text="$SHORT"
  else
    zenity --error --title="$TITLE" --text="$FAIL"
  fi
done
