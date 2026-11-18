"""Downloads profiles, catalog and releases.yaml from GitHub as one archive."""

from __future__ import annotations

import io
import shutil
import tarfile
import urllib.request
from pathlib import Path

from . import __version__


class FetchError(Exception):
    pass


def download_repo(url: str, dest: Path, timeout: int = 30) -> Path:
    """Download the repository tarball and unpack it into dest. Returns the repo root."""
    req = urllib.request.Request(url, headers={"User-Agent": f"easylinux-installer/{__version__}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
    except OSError as exc:
        raise FetchError(str(exc)) from exc
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
            tar.extractall(dest, filter="data")
    except (tarfile.TarError, OSError) as exc:
        raise FetchError(f"invalid archive: {exc}") from exc
    roots = [p for p in dest.iterdir() if p.is_dir()]
    if len(roots) != 1:
        raise FetchError("unexpected archive layout")
    return roots[0]


def download_file(url: str, dest: Path, timeout: int = 60) -> Path:
    req = urllib.request.Request(url, headers={"User-Agent": f"easylinux-installer/{__version__}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp, dest.open("wb") as fh:
            shutil.copyfileobj(resp, fh)
    except OSError as exc:
        raise FetchError(f"{url}: {exc}") from exc
    return dest
