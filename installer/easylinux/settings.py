"""Runtime settings.

Defaults can be overridden by kernel parameters (``easylinux.<key>=<value>``),
for example on a PXE server, or by QEMU fw_cfg entries (``opt/easylinux/<key>``),
which the automatic test in GitHub Actions uses.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

FW_CFG_DIR = Path("/sys/firmware/qemu_fw_cfg/by_name/opt/easylinux")


@dataclass
class Settings:
    repo: str = "GFGMNET/EasyLinuxInstaller"
    ref: str = "main"
    profiles_path: str = "profiles"
    port: int = 8080
    token: str | None = None            # None → random token at start
    after_install: str = "reboot"       # reboot | poweroff | stay
    boot_label: str = "EASYLINUX"       # volume label of the USB stick (excluded as target)
    min_disk_gb: int = 16
    workdir: Path = field(default_factory=lambda: Path(os.environ.get("EASYLINUX_WORKDIR", "/run/easylinux")))

    @property
    def archive_url(self) -> str:
        return f"https://codeload.github.com/{self.repo}/tar.gz/{self.ref}"


def parse_cmdline(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for word in text.split():
        if word.startswith("easylinux.") and "=" in word:
            key, value = word[len("easylinux."):].split("=", 1)
            out[key] = value
    return out


def _fw_cfg() -> dict[str, str]:
    out: dict[str, str] = {}
    if FW_CFG_DIR.is_dir():
        for entry in FW_CFG_DIR.iterdir():
            raw = entry / "raw"
            if raw.is_file():
                out[entry.name] = raw.read_text().strip()
    return out


def load() -> Settings:
    s = Settings()
    overrides: dict[str, str] = {}
    try:
        overrides.update(parse_cmdline(Path("/proc/cmdline").read_text()))
    except OSError:
        pass
    overrides.update(_fw_cfg())
    for key, value in overrides.items():
        if not hasattr(s, key):
            continue
        current = getattr(s, key)
        if isinstance(current, int):
            value = int(value)
        elif isinstance(current, Path):
            value = Path(value)
        setattr(s, key, value)
    return s
