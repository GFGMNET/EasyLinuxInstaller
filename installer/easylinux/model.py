"""Loading and validating profiles, catalog items and releases.yaml."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

OSES = ("nixos", "debian")
GPU_REQUIREMENTS = ("nvidia", "amd", "any")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")

PROFILE_KEYS = {"id", "name", "os", "requires", "system", "users", "desktop", "drivers", "software"}
CATALOG_KEYS = {"id", "unfree", "depends", "nixos", "debian"}
NIXOS_KEYS = {"config", "packages"}
DEBIAN_KEYS = {"keyring_debs", "foreign_arch", "packages", "venv", "files", "enable_services"}


class ValidationError(Exception):
    pass


@dataclass
class User:
    name: str
    password: str
    admin: bool = False


@dataclass
class Profile:
    id: str
    name: str
    os: str
    timezone: str = "UTC"
    requires_gpu: str | None = None
    min_ram_gb: int | None = None
    users: list[User] = field(default_factory=list)
    desktop: str | None = None
    drivers: list[str] = field(default_factory=list)
    software: list[str] = field(default_factory=list)

    @property
    def wanted(self) -> list[str]:
        """All catalog/package names in install order."""
        return ([self.desktop] if self.desktop else []) + self.drivers + self.software


def _str_list(value, where: str, errors: list[str]) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(v, str) and v for v in value):
        errors.append(f"{where}: must be a list of names")
        return []
    return list(value)


def parse_profile(data: dict, source: str = "profile") -> Profile:
    errors: list[str] = []
    if not isinstance(data, dict):
        raise ValidationError(f"{source}: not a YAML mapping")
    for key in data:
        if key not in PROFILE_KEYS:
            errors.append(f"{source}: unknown key '{key}'")
    pid = data.get("id")
    if not isinstance(pid, str) or not ID_RE.match(pid):
        errors.append(f"{source}: 'id' must be lowercase letters, digits and '-'")
    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        errors.append(f"{source}: 'name' is required")
    os_name = data.get("os")
    if os_name not in OSES:
        errors.append(f"{source}: 'os' must be one of {', '.join(OSES)}")

    requires = data.get("requires") or {}
    if not isinstance(requires, dict):
        errors.append(f"{source}: 'requires' must be a mapping")
        requires = {}
    gpu = requires.get("gpu")
    if gpu is not None and gpu not in GPU_REQUIREMENTS:
        errors.append(f"{source}: requires.gpu must be one of {', '.join(GPU_REQUIREMENTS)}")
    ram = requires.get("min_ram_gb")
    if ram is not None and not (isinstance(ram, int) and ram > 0):
        errors.append(f"{source}: requires.min_ram_gb must be a positive number")
    for key in requires:
        if key not in ("gpu", "min_ram_gb"):
            errors.append(f"{source}: unknown key 'requires.{key}'")

    system = data.get("system") or {}
    if not isinstance(system, dict):
        errors.append(f"{source}: 'system' must be a mapping")
        system = {}
    for key in system:
        if key != "timezone":
            errors.append(f"{source}: unknown key 'system.{key}' (language and keyboard come from the menu)")
    timezone = system.get("timezone", "UTC")
    if not isinstance(timezone, str) or not re.match(r"^[A-Za-z0-9_+\-/]+$", timezone):
        errors.append(f"{source}: system.timezone is invalid")

    users: list[User] = []
    raw_users = data.get("users") or []
    if not isinstance(raw_users, list) or not raw_users:
        errors.append(f"{source}: 'users' must list at least one user")
        raw_users = []
    for i, u in enumerate(raw_users):
        if not isinstance(u, dict):
            errors.append(f"{source}: users[{i}] must be a mapping")
            continue
        uname, upw = u.get("name"), u.get("password")
        if not isinstance(uname, str) or not re.match(r"^[a-z_][a-z0-9_-]{0,30}$", uname):
            errors.append(f"{source}: users[{i}].name is invalid")
            continue
        if not isinstance(upw, str) or not upw or "\n" in upw or ":" in upw:
            errors.append(f"{source}: users[{i}].password is required (no ':' or newline)")
            continue
        for key in u:
            if key not in ("name", "password", "admin"):
                errors.append(f"{source}: unknown key 'users[{i}].{key}'")
        users.append(User(uname, upw, bool(u.get("admin", False))))

    desktop = data.get("desktop")
    if desktop is not None and not isinstance(desktop, str):
        errors.append(f"{source}: 'desktop' must be a name")
        desktop = None
    drivers = _str_list(data.get("drivers"), f"{source}: drivers", errors)
    software = _str_list(data.get("software"), f"{source}: software", errors)

    if errors:
        raise ValidationError("\n".join(errors))
    return Profile(
        id=pid, name=name.strip(), os=os_name, timezone=timezone,
        requires_gpu=gpu, min_ram_gb=ram, users=users,
        desktop=desktop, drivers=drivers, software=software,
    )


def validate_catalog_item(data: dict, source: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return [f"{source}: not a YAML mapping"]
    for key in data:
        if key not in CATALOG_KEYS:
            errors.append(f"{source}: unknown key '{key}'")
    if not isinstance(data.get("id"), str) or not ID_RE.match(data["id"]):
        errors.append(f"{source}: 'id' is required (lowercase letters, digits, '-')")
    if not isinstance(data.get("depends", []), list):
        errors.append(f"{source}: 'depends' must be a list")
    if "nixos" not in data and "debian" not in data:
        errors.append(f"{source}: needs a 'nixos' or 'debian' section")
    nix = data.get("nixos")
    if nix is not None:
        if not isinstance(nix, dict):
            errors.append(f"{source}: 'nixos' must be a mapping")
        else:
            errors += [f"{source}: unknown key 'nixos.{k}'" for k in nix if k not in NIXOS_KEYS]
    deb = data.get("debian")
    if deb is not None:
        if not isinstance(deb, dict):
            errors.append(f"{source}: 'debian' must be a mapping")
        else:
            errors += [f"{source}: unknown key 'debian.{k}'" for k in deb if k not in DEBIAN_KEYS]
            venv = deb.get("venv")
            if venv is not None and (not isinstance(venv, dict) or not str(venv.get("path", "")).startswith("/")):
                errors.append(f"{source}: debian.venv needs an absolute 'path'")
            for f in deb.get("files", []) or []:
                if not isinstance(f, dict) or not str(f.get("path", "")).startswith("/") or "content" not in f:
                    errors.append(f"{source}: debian.files entries need 'path' (absolute) and 'content'")
    return errors


def load_yaml(path: Path):
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_profiles(directory: Path) -> tuple[list[Profile], list[str]]:
    profiles: list[Profile] = []
    errors: list[str] = []
    seen: set[str] = set()
    for path in sorted(directory.glob("*.yaml")):
        try:
            p = parse_profile(load_yaml(path), path.name)
        except (ValidationError, yaml.YAMLError) as exc:
            errors.append(str(exc))
            continue
        if p.id in seen:
            errors.append(f"{path.name}: duplicate profile id '{p.id}'")
            continue
        seen.add(p.id)
        profiles.append(p)
    return profiles, errors


def load_catalog(directory: Path) -> tuple[dict[str, dict], list[str]]:
    items: dict[str, dict] = {}
    errors: list[str] = []
    if not directory.is_dir():
        return items, errors
    for path in sorted(directory.rglob("*.yaml")):
        try:
            data = load_yaml(path)
        except yaml.YAMLError as exc:
            errors.append(f"{path.name}: {exc}")
            continue
        errs = validate_catalog_item(data, str(path.relative_to(directory)))
        if errs:
            errors += errs
            continue
        if data["id"] in items:
            errors.append(f"{path.name}: duplicate catalog id '{data['id']}'")
            continue
        items[data["id"]] = data
    return items, errors


def load_releases(path: Path) -> dict[str, str]:
    data = load_yaml(path) if path.is_file() else {}
    nixos = str((data or {}).get("nixos", "26.05"))
    debian = str((data or {}).get("debian", "13"))
    if not re.match(r"^\d\d\.(05|11)$", nixos) or not debian.isdigit():
        raise ValidationError("releases.yaml: invalid versions")
    return {"nixos": nixos, "debian": debian}
