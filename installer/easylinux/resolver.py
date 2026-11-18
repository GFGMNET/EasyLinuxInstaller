"""Turns a profile into an install plan for its OS.

A name is either a catalog item (with a section for the profile's OS) or, if it
is not in the catalog, a plain package with that name.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .model import Profile

GPU_AUTO = "gpu-auto"


class ResolveError(Exception):
    pass


@dataclass
class Plan:
    os: str
    items: list[tuple[str, dict]] = field(default_factory=list)   # (id, OS section)
    packages: list[str] = field(default_factory=list)             # plain packages (fallback)
    unfree: bool = False

    @property
    def item_ids(self) -> list[str]:
        return [i for i, _ in self.items]


def expand_gpu_auto(names: list[str], gpu_vendors: set[str] | None) -> list[str]:
    """Replace 'gpu-auto' by the driver for the detected GPU.

    gpu_vendors=None means "check mode": keep every possible driver so that
    all of them are validated.
    """
    out: list[str] = []
    for n in names:
        if n != GPU_AUTO:
            out.append(n)
        elif gpu_vendors is None:
            out += ["nvidia", "amd"]
        else:
            out += [v for v in ("nvidia", "amd") if v in gpu_vendors]
    return out


def resolve(profile: Profile, catalog: dict[str, dict], gpu_vendors: set[str] | None = None) -> Plan:
    plan = Plan(os=profile.os)
    errors: list[str] = []
    visiting: set[str] = set()
    done: set[str] = set()

    def add(name: str, chain: tuple[str, ...]) -> None:
        if name in done:
            return
        if name in visiting:
            errors.append(f"{profile.id}: circular 'depends': {' -> '.join(chain + (name,))}")
            return
        item = catalog.get(name)
        if item is None:
            if chain:
                errors.append(f"{profile.id}: '{chain[-1]}' depends on unknown item '{name}'")
            elif name not in plan.packages:
                plan.packages.append(name)
            done.add(name)
            return
        section = item.get(profile.os)
        if section is None:
            errors.append(
                f"{profile.id}: catalog item '{name}' has no '{profile.os}' section "
                f"(add one to the catalog file)"
            )
            done.add(name)
            return
        visiting.add(name)
        for dep in item.get("depends", []) or []:
            add(dep, chain + (name,))
        visiting.discard(name)
        plan.items.append((name, section or {}))
        plan.unfree = plan.unfree or bool(item.get("unfree"))
        done.add(name)

    for name in expand_gpu_auto(profile.wanted, gpu_vendors):
        add(name, ())
    if errors:
        raise ResolveError("\n".join(errors))
    return plan
