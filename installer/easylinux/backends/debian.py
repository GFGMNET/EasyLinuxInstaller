"""Debian backend: debootstrap the newest stable release, then apt."""

from __future__ import annotations

import os
from pathlib import Path

from ..fetch import download_file
from ..util import run, write_file
from . import ASSETS, DEFAULT_PASSWORDS, KERNEL_CONSOLE, PASSWORD_FLAG, Context

MIRROR = "http://deb.debian.org/debian"
SECURITY = "http://security.debian.org/debian-security"
COMPONENTS = "main contrib non-free non-free-firmware"   # always all (unfree drivers/firmware)
LIVE_KEYRING = os.environ.get(
    "EASYLINUX_DEBIAN_KEYRING", "/usr/share/keyrings/debian-archive-keyring.gpg")
APT_ENV = {"DEBIAN_FRONTEND": "noninteractive", "LC_ALL": "C.UTF-8"}
BASE_PACKAGES = [
    "linux-image-amd64", "linux-headers-amd64", "firmware-linux", "network-manager",
    "sudo", "locales", "console-setup", "keyboard-configuration", "ca-certificates",
]


def plan_summary(ctx_plan, debian_version: str) -> dict:
    """What apt needs for a plan (also used by the automatic check)."""
    keyrings, arches, packages = [], [], []
    for _, sec in ctx_plan.items:
        keyrings += [u.replace("{debian}", debian_version) for u in sec.get("keyring_debs", []) or []]
        arches += sec.get("foreign_arch", []) or []
        packages += sec.get("packages", []) or []
    packages += ctx_plan.packages
    dedup = lambda xs: list(dict.fromkeys(xs))
    return {"keyring_debs": dedup(keyrings), "foreign_arch": dedup(arches), "packages": dedup(packages)}


def sources_deb822() -> str:
    return (
        f"Types: deb\nURIs: {MIRROR}\nSuites: stable stable-updates\nComponents: {COMPONENTS}\n"
        "Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg\n\n"
        f"Types: deb\nURIs: {SECURITY}\nSuites: stable-security\nComponents: {COMPONENTS}\n"
        "Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg\n"
    )


class Chroot:
    def __init__(self, ctx: Context):
        self.ctx = ctx
        self.mnt = ctx.mnt
        self.mounted: list[str] = []

    def __enter__(self):
        m = str(self.mnt)
        for args, point in (
            (["--rbind", "/dev"], f"{m}/dev"),
            (["-t", "proc", "proc"], f"{m}/proc"),
            (["--rbind", "/sys"], f"{m}/sys"),
            (["-t", "tmpfs", "tmpfs"], f"{m}/run"),
        ):
            os.makedirs(point, exist_ok=True)
            run(["mount", *args, point], self.ctx.log)
            if "--rbind" in args:
                run(["mount", "--make-rslave", point], self.ctx.log)
            self.mounted.append(point)
        # keep services from starting inside the chroot
        write_file(self.mnt / "usr/sbin/policy-rc.d", "#!/bin/sh\nexit 101\n", 0o755)
        return self

    def __exit__(self, *exc):
        (self.mnt / "usr/sbin/policy-rc.d").unlink(missing_ok=True)
        for point in reversed(self.mounted):
            run(["umount", "-R", "-l", point], self.ctx.log, check=False)

    def __call__(self, *cmd: str, input: str | None = None, env: dict | None = None, quiet=False):
        return run(["chroot", str(self.mnt), *cmd], self.ctx.log, input=input,
                   env={**APT_ENV, **(env or {})}, quiet=quiet)

    def apt_install(self, packages: list[str]):
        if packages:
            self("apt-get", "install", "-y", "-o", "Dpkg::Options::=--force-confold", *packages)


def _uuid(dev: str, log) -> str:
    return run(["blkid", "-s", "UUID", "-o", "value", dev], log).strip()


def install(ctx: Context) -> None:
    log, mnt = ctx.log, ctx.mnt
    summary = plan_summary(ctx.plan, ctx.releases["debian"])

    ctx.progress(16, "step_base_system")
    esp_dir = mnt / "boot/efi"
    esp_dir.mkdir(parents=True, exist_ok=True)
    run(["mount", ctx.esp, str(esp_dir)], log)
    run(["debootstrap", "--arch=amd64", f"--components={COMPONENTS.replace(' ', ',')}",
         f"--keyring={LIVE_KEYRING}", "stable", str(mnt), MIRROR], log)

    ctx.progress(40, "step_configure")
    (mnt / "etc/apt/sources.list").unlink(missing_ok=True)
    write_file(mnt / "etc/apt/sources.list.d/debian.sources", sources_deb822())
    try:
        write_file(mnt / "etc/resolv.conf", Path("/etc/resolv.conf").read_text(encoding="utf-8"))
    except OSError:
        pass
    write_file(mnt / "etc/hostname", ctx.hostname + "\n")
    write_file(mnt / "etc/hosts", f"127.0.0.1\tlocalhost\n127.0.1.1\t{ctx.hostname}\n"
               "::1\tlocalhost ip6-localhost ip6-loopback\n")
    root_uuid, esp_uuid = _uuid(ctx.root, log), _uuid(ctx.esp, log)
    write_file(mnt / "etc/fstab", f"UUID={root_uuid}\t/\text4\terrors=remount-ro\t0 1\n"
               f"UUID={esp_uuid}\t/boot/efi\tvfat\tumask=0077\t0 2\n")
    locale, kb = ctx.lang["locale"], ctx.lang["keyboard"]
    write_file(mnt / "etc/locale.gen", f"{locale} UTF-8\n" + ("" if locale.startswith("en_US") else "en_US.UTF-8 UTF-8\n"))
    write_file(mnt / "etc/default/locale", f"LANG={locale}\n")
    write_file(mnt / "etc/default/keyboard",
               f'XKBMODEL="pc105"\nXKBLAYOUT="{kb}"\nXKBVARIANT=""\nXKBOPTIONS=""\nBACKSPACE="guess"\n')
    write_file(mnt / "etc/timezone", ctx.profile.timezone + "\n")
    localtime = mnt / "etc/localtime"
    localtime.unlink(missing_ok=True)
    localtime.symlink_to(f"/usr/share/zoneinfo/{ctx.profile.timezone}")
    write_file(mnt / "etc/kernel/cmdline", " ".join([f"root=UUID={root_uuid}", "rw", "quiet", *KERNEL_CONSOLE]) + "\n")

    with Chroot(ctx) as ch:
        ch("systemd-machine-id-setup")
        ch("locale-gen")
        for arch in summary["foreign_arch"]:
            ch("dpkg", "--add-architecture", arch)
        ch("apt-get", "update")

        ctx.progress(45, "step_bootloader")
        ch.apt_install(["systemd-boot"])
        ch("bootctl", "install", "--esp-path=/boot/efi")

        ctx.progress(50, "step_kernel")
        ch.apt_install(BASE_PACKAGES + (["zenity"] if ctx.has_desktop else []))

        if summary["keyring_debs"]:
            ctx.progress(60, "step_repos")
            for i, url in enumerate(summary["keyring_debs"]):
                download_file(url, mnt / f"tmp/keyring-{i}.deb")
                ch("dpkg", "-i", f"/tmp/keyring-{i}.deb")
            ch("apt-get", "update")

        ctx.progress(65, "step_software")
        ch.apt_install(summary["packages"])

        for item_id, sec in ctx.plan.items:
            venv = sec.get("venv")
            if venv:
                ctx.progress(85, "step_python")
                ch("python3", "-m", "venv", venv["path"])
                ch(f"{venv['path']}/bin/pip", "install", "--upgrade", "pip")
                if venv.get("pip"):
                    ch(f"{venv['path']}/bin/pip", "install", *venv["pip"])
            for f in sec.get("files", []) or []:
                write_file(mnt / f["path"].lstrip("/"), f["content"], int(str(f.get("mode", "0644")), 8))
            for svc in sec.get("enable_services", []) or []:
                ch("systemctl", "enable", svc)

        ctx.progress(92, "step_users")
        _create_users(ctx, ch)
        ch("systemctl", "enable", "NetworkManager")
        ch("apt-get", "clean")


def _create_users(ctx: Context, ch: Chroot) -> None:
    mnt = ctx.mnt
    for u in ctx.profile.users:
        groups = ["sudo"] if u.admin else []
        ch("useradd", "-m", "-s", "/bin/bash", *(["-G", ",".join(groups)] if groups else []), u.name)
        ch("chpasswd", input=f"{u.name}:{u.password}\n", quiet=True)
        if not ctx.has_desktop:
            ch("chage", "-d", "0", u.name)   # console login handles expired passwords fine

    if ctx.has_desktop:
        names = "".join(f"{u.name}\n" for u in ctx.profile.users)
        write_file(mnt / PASSWORD_FLAG.lstrip("/"), names, 0o644)
        write_file(mnt / DEFAULT_PASSWORDS.lstrip("/"),
                   "".join(f"{u.name}:{u.password}\n" for u in ctx.profile.users), 0o600)
        write_file(mnt / "usr/local/bin/easylinux-first-login", (ASSETS / "first-login.sh").read_text(encoding="utf-8"), 0o755)
        write_file(mnt / "usr/local/sbin/easylinux-set-password", (ASSETS / "set-password.sh").read_text(encoding="utf-8"), 0o755)
        write_file(mnt / "etc/xdg/autostart/easylinux-first-login.desktop",
                   (ASSETS / "easylinux-first-login.desktop").read_text(encoding="utf-8"))
        write_file(mnt / "etc/sudoers.d/easylinux-first-login",
                   "ALL ALL=(root) NOPASSWD: /usr/local/sbin/easylinux-set-password\n", 0o440)
