#!/usr/bin/env bash
# Test install in QEMU (UEFI): boot the ISO, install a test profile, then boot
# the installed disk and wait for a login prompt. GitHub Actions only.
# Usage: ci-vm-test.sh <test-profile> <git-ref> <iso>
set -euo pipefail

PROFILE="$1"; REF="$2"; ISO="$3"
TOKEN="CI$(date +%s)"

# Errors are also written as GitHub annotations (readable without logging in).
annotate() {   # annotate <title> <file>: last lines of a file as one annotation
  local text
  text=$(tail -n 25 "$2" 2>/dev/null | tr -d '\r' | sed -e 's/%/%25/g' | awk '{printf "%s%%0A", $0}')
  echo "::error title=$1::${text:-<empty>}"
}
fail() { echo "::error title=VM test ($PROFILE)::$*"; exit 1; }
trap 'fail "line $LINENO: $BASH_COMMAND"' ERR

# OVMF file names differ between Ubuntu versions → search.
OVMF_CODE=$(ls /usr/share/OVMF/OVMF_CODE_4M.fd /usr/share/OVMF/OVMF_CODE.fd /usr/share/ovmf/OVMF.fd 2>/dev/null | head -n1 || true)
OVMF_VARS=$(ls /usr/share/OVMF/OVMF_VARS_4M.fd /usr/share/OVMF/OVMF_VARS.fd 2>/dev/null | head -n1 || true)
if [ -z "$OVMF_CODE" ] || [ -z "$OVMF_VARS" ]; then
  fail "OVMF not found: $(ls /usr/share/OVMF /usr/share/ovmf 2>&1 | tr '\n' ' ')"
fi
[ -f "$ISO" ] || fail "ISO not found: $ISO"
echo "OVMF: $OVMF_CODE / $OVMF_VARS"

qemu-img create -f qcow2 disk.qcow2 40G
cp "$OVMF_VARS" vars.fd

if [ -w /dev/kvm ]; then ACCEL=(-enable-kvm -cpu host); echo "KVM: yes"; else ACCEL=(-cpu max); echo "KVM: no (slow)"; fi
COMMON=(-machine q35 "${ACCEL[@]}" -m 6144 -smp 4 -display none
  -drive "if=pflash,format=raw,readonly=on,file=$OVMF_CODE"
  -drive "if=pflash,format=raw,file=vars.fd"
  -drive "file=disk.qcow2,if=virtio,format=qcow2")

echo "::group::Install $PROFILE"
qemu-system-x86_64 "${COMMON[@]}" -cdrom "$ISO" \
  -netdev user,id=n0,hostfwd=tcp:127.0.0.1:8080-:8080 -device virtio-net-pci,netdev=n0 \
  -fw_cfg "name=opt/easylinux/token,string=$TOKEN" \
  -fw_cfg "name=opt/easylinux/ref,string=$REF" \
  -fw_cfg "name=opt/easylinux/profiles_path,string=tests/profiles" \
  -fw_cfg "name=opt/easylinux/after_install,string=poweroff" \
  -serial file:install-serial.log 2> qemu-stderr.log &
QEMU=$!
trap - ERR
rc=0
python3 tools/ci-install.py --profile "$PROFILE" --token "$TOKEN" --pid "$QEMU" --timeout 9000 > install-api.log 2>&1 || rc=$?
cat install-api.log
if [ "$rc" -ne 0 ]; then
  kill "$QEMU" 2>/dev/null || true
  annotate "Install $PROFILE failed" install-api.log
  annotate "VM console during install ($PROFILE)" install-serial.log
  [ -s qemu-stderr.log ] && annotate "QEMU errors ($PROFILE)" qemu-stderr.log
  exit 1
fi
wait "$QEMU" || true      # the installer powers the VM off
echo "::endgroup::"

echo "::group::Boot installed system"
qemu-system-x86_64 "${COMMON[@]}" -netdev user,id=n0 -device virtio-net-pci,netdev=n0 \
  -serial file:boot-serial.log &
QEMU=$!
for _ in $(seq 1 180); do      # up to 30 minutes
  if grep -q "login:" boot-serial.log 2>/dev/null; then
    echo "login prompt reached"; kill "$QEMU" || true; echo "::endgroup::"; exit 0
  fi
  sleep 10
done
kill "$QEMU" 2>/dev/null || true
annotate "Boot $PROFILE failed (no login prompt)" boot-serial.log
exit 1
