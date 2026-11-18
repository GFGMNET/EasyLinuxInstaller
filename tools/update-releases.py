#!/usr/bin/env python3
"""Monthly: find the newest *released* stable versions of NixOS and Debian
(endoflife.date) and update releases.yaml and flake.nix. Keeps the current
values if the lookup fails."""

from __future__ import annotations

import datetime
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def newest(product: str, pattern: str) -> str | None:
    req = urllib.request.Request(f"https://endoflife.date/api/{product}.json",
                                 headers={"User-Agent": "easylinux-ci"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            cycles = json.loads(resp.read())
    except OSError as exc:
        print(f"warning: {product}: {exc}", file=sys.stderr)
        return None
    today = datetime.date.today().isoformat()
    released = [c["cycle"] for c in cycles
                if re.fullmatch(pattern, str(c.get("cycle", ""))) and str(c.get("releaseDate", "9999")) <= today]
    key = lambda v: tuple(int(x) for x in v.split("."))
    return max(released, key=key) if released else None


def main() -> int:
    rel_file = ROOT / "releases.yaml"
    text = rel_file.read_text(encoding="utf-8")
    nixos = newest("nixos", r"\d\d\.(05|11)")
    debian = newest("debian", r"\d+")
    if nixos:
        text = re.sub(r'^nixos: ".*"$', f'nixos: "{nixos}"', text, flags=re.M)
        flake = ROOT / "flake.nix"
        flake.write_text(re.sub(r"nixos-\d\d\.\d\d", f"nixos-{nixos}", flake.read_text(encoding="utf-8")),
                         encoding="utf-8")
    if debian:
        text = re.sub(r'^debian: ".*"$', f'debian: "{debian}"', text, flags=re.M)
    rel_file.write_text(text, encoding="utf-8")
    print(f"nixos={nixos} debian={debian}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
