"""Choosing the target disk: always the first internal disk.

Excluded: the USB stick we booted from, USB/removable devices, read-only
devices, CD drives, loop/zram devices, and disks smaller than the minimum.
Order: NVMe first, then everything else, each sorted by kernel name.
"""

from __future__ import annotations

import json
import re
import subprocess

LSBLK_COLUMNS = "NAME,PATH,TYPE,SIZE,RM,RO,TRAN,MODEL,SERIAL,LABEL"


def _flag(value) -> bool:
    return value in (True, 1, "1", "true")


def _labels(dev: dict) -> set[str]:
    labels = {dev.get("label") or ""}
    for child in dev.get("children", []) or []:
        labels |= _labels(child)
    return labels - {""}


def candidates(lsblk: dict, boot_label: str = "EASYLINUX", min_bytes: int = 16 * 10**9) -> list[dict]:
    out = []
    for dev in lsblk.get("blockdevices", []):
        name = dev.get("name", "")
        if dev.get("type") != "disk":
            continue
        if re.match(r"^(loop|zram|ram|sr|fd)", name):
            continue
        if _flag(dev.get("rm")) or _flag(dev.get("ro")):
            continue
        if (dev.get("tran") or "").lower() == "usb":
            continue
        if boot_label in _labels(dev):
            continue
        if int(dev.get("size") or 0) < min_bytes:
            continue
        out.append(dev)
    nvme_first = lambda d: (0 if d.get("name", "").startswith("nvme") or d.get("tran") == "nvme" else 1, d.get("name", ""))
    return sorted(out, key=nvme_first)


def first_internal_disk(boot_label: str = "EASYLINUX", min_gb: int = 16) -> dict | None:
    out = subprocess.run(
        ["lsblk", "-J", "-b", "-o", LSBLK_COLUMNS], capture_output=True, text=True, check=True
    ).stdout
    found = candidates(json.loads(out), boot_label, min_gb * 10**9)
    return found[0] if found else None


def partition_path(disk: str, number: int) -> str:
    """/dev/sda + 1 → /dev/sda1, /dev/nvme0n1 + 1 → /dev/nvme0n1p1."""
    return f"{disk}p{number}" if disk[-1].isdigit() else f"{disk}{number}"
