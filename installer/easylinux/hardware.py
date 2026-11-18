"""Hardware detection (GPU, RAM, network MAC) and profile requirement checks."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from .model import Profile

GPU_VENDORS = {"10de": "nvidia", "1002": "amd", "8086": "intel"}


def parse_lspci(text: str) -> set[str]:
    """Parse `lspci -mm -n` output and return the GPU vendors found."""
    vendors: set[str] = set()
    for line in text.splitlines():
        fields = re.findall(r'"([^"]*)"', line)
        if len(fields) >= 2 and fields[0].startswith("03"):   # display controller classes
            vendors.add(GPU_VENDORS.get(fields[1].lower(), "other"))
    return vendors


def detect_gpus() -> set[str]:
    try:
        out = subprocess.run(["lspci", "-mm", "-n"], capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return set()
    return parse_lspci(out)


def ram_gb() -> int:
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal:"):
                return round(int(line.split()[1]) / 1024 / 1024)
    except OSError:
        pass
    return 0


def check_requirements(profile: Profile, gpus: set[str], ram: int) -> list[tuple[str, dict]]:
    """Return a list of (message-key, params) for unmet requirements."""
    problems: list[tuple[str, dict]] = []
    req = profile.requires_gpu
    if req == "any" and not (gpus & {"nvidia", "amd"}):
        problems.append(("err_need_gpu_any", {}))
    elif req in ("nvidia", "amd") and req not in gpus:
        problems.append(("err_need_gpu", {"gpu": req.upper() if req == "amd" else "NVIDIA"}))
    if profile.min_ram_gb and ram < profile.min_ram_gb:
        problems.append(("err_need_ram", {"need": profile.min_ram_gb, "have": ram}))
    return problems


def primary_mac() -> str:
    """MAC address of the interface with the default route (fallback: first wired NIC)."""
    dev = None
    try:
        out = subprocess.run(["ip", "-o", "route", "show", "default"], capture_output=True, text=True).stdout
        m = re.search(r"\bdev (\S+)", out)
        dev = m.group(1) if m else None
    except OSError:
        pass
    candidates = [Path("/sys/class/net") / dev] if dev else []
    candidates += sorted(Path("/sys/class/net").glob("*"))
    for iface in candidates:
        if iface.name == "lo":
            continue
        try:
            mac = (iface / "address").read_text().strip()
        except OSError:
            continue
        if mac and mac != "00:00:00:00:00:00":
            return mac
    return "000000000000"


def make_hostname(profile_id: str, mac: str) -> str:
    """<profile>-<mac without colons>, valid per RFC 1123 (max 63 chars)."""
    mac_part = re.sub(r"[^0-9a-f]", "", mac.lower())
    prefix = re.sub(r"[^a-z0-9-]", "-", profile_id.lower()).strip("-")
    prefix = prefix[: 63 - len(mac_part) - 1].strip("-")
    return f"{prefix}-{mac_part}" if prefix else mac_part
