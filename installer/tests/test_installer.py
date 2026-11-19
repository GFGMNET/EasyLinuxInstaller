import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "installer"))

from easylinux import disks, hardware  # noqa: E402
from easylinux.backends import debian, nixos  # noqa: E402
from easylinux.model import ValidationError, load_catalog, load_profiles, parse_profile  # noqa: E402
from easylinux.resolver import ResolveError, resolve  # noqa: E402
from easylinux.settings import parse_cmdline  # noqa: E402
from easylinux.util import LANGUAGES  # noqa: E402

CATALOG, CAT_ERRORS = load_catalog(ROOT / "catalog")

# Fixed example profiles: the tests must not depend on what is in profiles/ (that can change any time).
USERS = [{"name": "admin", "password": "admin", "admin": True}]
PROFILES = {
    "games": parse_profile({"id": "games", "name": "Games", "os": "nixos", "requires": {"gpu": "nvidia"},
                            "system": {"timezone": "Europe/Berlin"}, "users": USERS,
                            "desktop": "awesome", "drivers": ["nvidia"], "software": ["steam"]}),
    "ai": parse_profile({"id": "ai", "name": "AI", "os": "debian", "requires": {"gpu": "nvidia"},
                         "users": USERS, "desktop": "kde", "drivers": ["nvidia", "cuda"], "software": ["vllm"]}),
}


def test_repo_profiles_and_catalog_load():
    """Whatever is in profiles/ must load and resolve (content is not checked)."""
    assert CAT_ERRORS == []
    profiles, errors = load_profiles(ROOT / "profiles")
    assert errors == [] and profiles
    for prof in profiles:
        resolve(prof, CATALOG, None)


def test_games_plan():
    plan = resolve(PROFILES["games"], CATALOG, {"nvidia"})
    assert plan.os == "nixos"
    assert plan.item_ids == ["awesome", "nvidia", "steam"]
    assert plan.packages == [] and plan.unfree


def test_ai_plan_dependencies_once():
    plan = resolve(PROFILES["ai"], CATALOG, {"nvidia"})
    assert plan.item_ids == ["kde", "nvidia", "cuda", "vllm"]
    s = debian.plan_summary(plan, "13")
    assert s["keyring_debs"] == [
        "https://developer.download.nvidia.com/compute/cuda/repos/debian13/x86_64/cuda-keyring_1.1-1_all.deb"]
    assert "nvidia-open" in s["packages"] and "cuda-toolkit" in s["packages"]


def test_unknown_name_is_plain_package():
    p = parse_profile({"id": "x", "name": "X", "os": "debian", "users": [{"name": "a", "password": "b"}],
                       "software": ["htop"]})
    assert resolve(p, CATALOG).packages == ["htop"]


def test_missing_os_section_fails():
    p = parse_profile({"id": "x", "name": "X", "os": "debian", "users": [{"name": "a", "password": "b"}],
                       "software": ["steam"]})   # steam only has a nixos section
    with pytest.raises(ResolveError):
        resolve(p, CATALOG)


def test_gpu_auto():
    p = parse_profile({"id": "x", "name": "X", "os": "nixos", "users": [{"name": "a", "password": "b"}],
                       "drivers": ["gpu-auto"]})
    assert resolve(p, CATALOG, {"amd", "intel"}).item_ids == ["amd"]
    assert resolve(p, CATALOG, {"intel"}).item_ids == []
    assert resolve(p, CATALOG, None).item_ids == ["nvidia", "amd"]


def test_profile_validation_errors():
    with pytest.raises(ValidationError):
        parse_profile({"id": "Bad Id", "name": "", "os": "windows", "users": []})
    with pytest.raises(ValidationError):   # locale comes from the menu, not the profile
        parse_profile({"id": "x", "name": "X", "os": "debian", "system": {"locale": "de_DE"},
                       "users": [{"name": "a", "password": "b"}]})


def test_requirements():
    games = PROFILES["games"]
    assert hardware.check_requirements(games, {"nvidia"}, 16) == []
    assert hardware.check_requirements(games, {"intel"}, 16)[0][0] == "err_need_gpu"


def test_lspci_parse():
    out = ('00:02.0 "0300" "8086" "3e92" -r00 "1028" "085a"\n'
           '01:00.0 "0300" "10de" "2684" -ra1 "10de" "16f3"\n'
           '00:1f.3 "0403" "8086" "a348" -r10 "1028" "085a"\n')
    assert hardware.parse_lspci(out) == {"intel", "nvidia"}


def test_hostname():
    assert hardware.make_hostname("games", "52:54:00:AB:cd:01") == "games-525400abcd01"
    assert len(hardware.make_hostname("x" * 80, "525400abcd01")) <= 63


def lsblk(*devs):
    return {"blockdevices": list(devs)}


def test_first_internal_disk():
    stick = {"name": "sda", "path": "/dev/sda", "type": "disk", "size": 32 * 10**9, "rm": True, "ro": False,
             "tran": "usb", "children": [{"name": "sda1", "label": "EASYLINUX"}]}
    sata = {"name": "sdb", "path": "/dev/sdb", "type": "disk", "size": 500 * 10**9, "rm": False, "ro": False, "tran": "sata"}
    nvme = {"name": "nvme0n1", "path": "/dev/nvme0n1", "type": "disk", "size": 1000 * 10**9, "rm": False, "ro": False, "tran": "nvme"}
    small = {"name": "sdc", "path": "/dev/sdc", "type": "disk", "size": 8 * 10**9, "rm": False, "ro": False, "tran": "sata"}
    cd = {"name": "sr0", "path": "/dev/sr0", "type": "rom", "size": 10**9, "rm": True, "ro": False}
    found = disks.candidates(lsblk(stick, sata, small, cd, nvme))
    assert [d["name"] for d in found] == ["nvme0n1", "sdb"]
    # stick not marked as USB/removable is still excluded by its label
    stick2 = dict(stick, rm=False, tran="sata")
    assert disks.candidates(lsblk(stick2)) == []


def test_partition_path():
    assert disks.partition_path("/dev/sda", 1) == "/dev/sda1"
    assert disks.partition_path("/dev/nvme0n1", 2) == "/dev/nvme0n1p2"


def test_cmdline():
    assert parse_cmdline("quiet easylinux.ref=abc easylinux.port=9 foo=bar") == {"ref": "abc", "port": "9"}


def test_nixos_render_games():
    p = PROFILES["games"]
    files = nixos.render(p, resolve(p, CATALOG, {"nvidia"}), LANGUAGES["de"], "games-525400abcd01", "26.05")
    conf = files["configuration.nix"]
    assert 'networking.hostName = "games-525400abcd01";' in conf
    assert 'i18n.defaultLocale = "de_DE.UTF-8";' in conf
    assert "nixpkgs.config.allowUnfree = true;" in conf
    assert "./easylinux-first-login.nix" in conf
    assert "programs.steam.enable = true;" in files["easylinux-items.nix"]
    assert "https://channels.nixos.org/nixos-26.05/nixexprs.tar.xz" in files["flake.nix"]
    assert conf.count("{") == conf.count("}")
    items = files["easylinux-items.nix"]
    assert items.count("{") == items.count("}")


def test_nix_string_escaping():
    assert nixos.nix_str('a"b${c}') == '"a\\"b\\${c}"'
