"""OS backends. Each backend installs a resolved plan onto the mounted target."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ..model import Profile
from ..resolver import Plan
from ..util import Log

ASSETS = Path(__file__).resolve().parent.parent / "assets"
PASSWORD_FLAG = "/var/lib/easylinux/must-change-password"
DEFAULT_PASSWORDS = "/var/lib/easylinux/default-passwords"
KERNEL_CONSOLE = ["console=ttyS0,115200", "console=tty0"]   # screen stays primary; serial for tests


@dataclass
class Context:
    profile: Profile
    plan: Plan
    lang: dict             # util.LANGUAGES entry
    hostname: str
    releases: dict         # {"nixos": "26.05", "debian": "13"}
    disk: str
    esp: str               # partition paths
    root: str
    mnt: Path
    log: Log
    progress: Callable[[int, str], None]

    @property
    def has_desktop(self) -> bool:
        return bool(self.profile.desktop)


def get_backend(os_name: str):
    if os_name == "debian":
        from . import debian
        return debian
    if os_name == "nixos":
        from . import nixos
        return nixos
    raise ValueError(os_name)
