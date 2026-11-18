#!/usr/bin/env bash
# Test install in QEMU (UEFI): boot the ISO, install a test profile, then boot
# the installed disk and wait for a login prompt. GitHub Actions only.
# Usage: ci-vm-test.sh <test-profile> <git-ref> <iso>
set -euo pipefail

PROFILE="$1"; REF="$2"; ISO="$3"
TOKEN="CI$(date +%s)"
OVMF_CODE=/usr/share/OVMF/OVMF_CODE_4M.fd
OVMF_VARS=/usr/share/OVMF/OVMF_VARS_4M.fd

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
  -serial file:install-serial.log &
QEMU=$!
rc=0
python3 tools/ci-install.py --profile "$PROFILE" --token "$TOKEN" --timeout 9000 || rc=$?
if [ "$rc" -ne 0 ]; then tail -n 100 install-serial.log || true; kill "$QEMU" || true; exit "$rc"; fi
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
tail -n 100 boot-serial.log || true
kill "$QEMU" || true
echo "no login prompt"; exit 1
