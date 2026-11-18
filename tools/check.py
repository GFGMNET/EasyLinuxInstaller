#!/usr/bin/env python3
"""Automatic checks for profiles and catalog (used by GitHub Actions).

  check.py validate            profiles + catalog are valid, every name resolves for its OS
  check.py debian-plan         JSON with what apt needs for all Debian profiles
  check.py nixos-render DIR    write a flake per NixOS profile into DIR (for `nix eval`)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "installer"))

from easylinux.backends import debian, nixos  # noqa: E402
from easylinux.model import load_catalog, load_profiles, load_releases  # noqa: E402
from easylinux.resolver import ResolveError, resolve  # noqa: E402
from easylinux.util import LANGUAGES  # noqa: E402

PROFILE_DIRS = [ROOT / "profiles", ROOT / "tests/profiles"]

FAKE_HARDWARE = """{ lib, modulesPath, ... }: {
  imports = [ (modulesPath + "/installer/scan/not-detected.nix") ];
  fileSystems."/" = { device = "/dev/disk/by-label/root"; fsType = "ext4"; };
  fileSystems."/boot" = { device = "/dev/disk/by-label/EFI"; fsType = "vfat"; };
  nixpkgs.hostPlatform = "x86_64-linux";
}
"""


def load_all():
    catalog, errors = load_catalog(ROOT / "catalog")
    profiles = []
    for d in PROFILE_DIRS:
        ps, errs = load_profiles(d)
        profiles += ps
        errors += errs
    return profiles, catalog, errors


def cmd_validate() -> int:
    profiles, catalog, errors = load_all()
    load_releases(ROOT / "releases.yaml")
    for p in profiles:
        try:
            plan = resolve(p, catalog, None)
            print(f"ok   {p.id:14} {p.os:7} items={plan.item_ids} packages={plan.packages}")
        except ResolveError as exc:
            errors.append(str(exc))
    for e in errors:
        print(f"ERROR {e}")
    return 1 if errors else 0


def cmd_debian_plan() -> int:
    profiles, catalog, _ = load_all()
    version = load_releases(ROOT / "releases.yaml")["debian"]
    total = {"keyring_debs": [], "foreign_arch": [], "packages": list(debian.BASE_PACKAGES) + ["systemd-boot", "zenity"]}
    for p in profiles:
        if p.os != "debian":
            continue
        s = debian.plan_summary(resolve(p, catalog, None), version)
        for k in total:
            total[k] += s[k]
    print(json.dumps({k: list(dict.fromkeys(v)) for k, v in total.items()}))
    return 0


def cmd_nixos_render(outdir: str) -> int:
    profiles, catalog, _ = load_all()
    version = load_releases(ROOT / "releases.yaml")["nixos"]
    out = Path(outdir)
    hosts = []
    for p in profiles:
        if p.os != "nixos":
            continue
        host = f"{p.id}-000000000000"
        d = out / p.id
        d.mkdir(parents=True, exist_ok=True)
        for name, content in nixos.render(p, resolve(p, catalog, None), LANGUAGES["de"], host, version).items():
            (d / name).write_text(content, encoding="utf-8")
        (d / "hardware-configuration.nix").write_text(FAKE_HARDWARE, encoding="utf-8")
        hosts.append({"dir": str(d), "host": host})
    print(json.dumps(hosts))
    return 0


def main(argv: list[str]) -> int:
    if argv[:1] == ["validate"]:
        return cmd_validate()
    if argv[:1] == ["debian-plan"]:
        return cmd_debian_plan()
    if argv[:1] == ["nixos-render"] and len(argv) == 2:
        return cmd_nixos_render(argv[1])
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
