"""The installer state machine: load profiles, then install one."""

from __future__ import annotations

import shutil
import subprocess
import threading
import time
import traceback
from pathlib import Path

from . import disks, hardware
from .backends import Context, get_backend
from .fetch import FetchError, download_repo
from .model import ValidationError, load_catalog, load_profiles, load_releases
from .resolver import ResolveError, resolve
from .settings import Settings
from .util import LANGUAGES, CommandError, Log, run

MNT = Path("/mnt")


class Installer:
    def __init__(self, settings: Settings):
        self.s = settings
        self.log = Log(settings.workdir / "install.log")
        self.lock = threading.Lock()
        self.phase = "loading"          # loading | ready | error | installing | done | failed
        self.error: tuple[str, dict] | None = None
        self.detail = ""
        self.progress = 0
        self.step = ""
        self.profiles = []
        self.catalog: dict = {}
        self.releases: dict = {}

    # ---------- state for the UI ----------
    def state(self) -> dict:
        with self.lock:
            return {
                "phase": self.phase,
                "error": {"key": self.error[0], "params": self.error[1]} if self.error else None,
                "detail": self.detail,
                "progress": self.progress,
                "step": self.step,
                "profiles": [{"id": p.id, "name": p.name} for p in self.profiles],
                "log": self.log.tail(12),
            }

    def _set(self, **kw):
        with self.lock:
            for k, v in kw.items():
                setattr(self, k, v)

    # ---------- loading ----------
    def load(self) -> None:
        self._set(phase="loading", error=None, detail="")
        self.log(f"Downloading profiles from {self.s.archive_url}")
        last_exc: Exception | None = None
        for attempt in range(3):            # the network may still be coming up
            try:
                root = download_repo(self.s.archive_url, self.s.workdir / "repo")
                break
            except FetchError as exc:
                last_exc = exc
                self.log(f"Download failed: {exc}")
                time.sleep(5)
        else:
            self._set(phase="error", error=("err_download", {}), detail=str(last_exc))
            return
        try:
            profiles, perr = load_profiles(root / self.s.profiles_path)
            catalog, cerr = load_catalog(root / "catalog")
            releases = load_releases(root / "releases.yaml")
        except ValidationError as exc:
            self._set(phase="error", error=("err_profiles", {}), detail=str(exc))
            return
        for e in perr + cerr:
            self.log(f"WARNING: {e}")
        if not profiles:
            self._set(phase="error", error=("err_profiles", {}), detail="\n".join(perr + cerr))
            return
        self._set(profiles=profiles, catalog=catalog, releases=releases, phase="ready")
        self.log(f"{len(profiles)} profiles loaded; NixOS {releases['nixos']}, Debian {releases['debian']}")

    # ---------- installing ----------
    def start(self, profile_id: str, lang_code: str) -> bool:
        with self.lock:
            if self.phase != "ready":
                return False
            profile = next((p for p in self.profiles if p.id == profile_id), None)
            if profile is None or lang_code not in LANGUAGES:
                return False
            self.phase, self.progress, self.step, self.error, self.detail = "installing", 0, "step_check", None, ""
        threading.Thread(target=self._install, args=(profile, lang_code), daemon=True).start()
        return True

    def _progress(self, pct: int, step: str) -> None:
        self._set(progress=pct, step=step)
        self.log(f"== {step} ({pct}%)")

    def _fail(self, key: str, params: dict | None = None, detail: str = "") -> None:
        self._set(phase="failed" if key.startswith("err_install") else "ready",
                  error=(key, params or {}), detail=detail)

    def _install(self, profile, lang_code: str) -> None:
        log = self.log
        try:
            # 1. hardware check
            gpus, ram = hardware.detect_gpus(), hardware.ram_gb()
            log(f"Profile {profile.id} ({profile.os}); GPUs: {sorted(gpus) or 'none'}; RAM: {ram} GB")
            problems = hardware.check_requirements(profile, gpus, ram)
            if problems:
                self._fail(*problems[0])
                return
            plan = resolve(profile, self.catalog, gpus)

            # 2. disk
            self._progress(5, "step_disk")
            disk = disks.first_internal_disk(self.s.boot_label, self.s.min_disk_gb)
            if not disk:
                self._fail("err_no_disk", {"gb": self.s.min_disk_gb})
                return
            dev = disk["path"]
            log(f"Target disk: {dev} {disk.get('model') or ''} {int(disk['size']) // 10**9} GB")
            esp, root = disks.partition_path(dev, 1), disks.partition_path(dev, 2)

            # 3. partition + format
            self._progress(8, "step_partition")
            run(["umount", "-R", "-l", str(MNT)], log, check=False)
            run(["wipefs", "-a", dev], log)
            run(["sgdisk", "--zap-all", dev], log)
            run(["sgdisk", "-n1:0:+1G", "-t1:ef00", "-c1:EFI", "-n2:0:0", "-t2:8300", "-c2:root", dev], log)
            run(["partprobe", dev], log, check=False)
            run(["udevadm", "settle"], log)
            run(["mkfs.fat", "-F32", "-n", "EFI", esp], log)
            run(["mkfs.ext4", "-F", "-L", "root", root], log)
            MNT.mkdir(exist_ok=True)
            run(["mount", root, str(MNT)], log)

            # 4. OS
            ctx = Context(
                profile=profile, plan=plan, lang=LANGUAGES[lang_code],
                hostname=hardware.make_hostname(profile.id, hardware.primary_mac()),
                releases=self.releases, disk=dev, esp=esp, root=root, mnt=MNT,
                log=log, progress=self._progress,
            )
            log(f"Hostname: {ctx.hostname}")
            get_backend(profile.os).install(ctx)

            # 5. finish
            self._progress(98, "step_finish")
            target_log = MNT / "var/log/easylinux-install.log"
            target_log.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(self.log.path, target_log)
            subprocess.run(["sync"])
            run(["umount", "-R", str(MNT)], log, check=False)
            self._set(phase="done", progress=100, step="step_done")
            log("Installation finished")
            self._after_install()
        except (CommandError, ResolveError, FetchError, OSError) as exc:
            log(traceback.format_exc())
            self._fail("err_install", detail=str(exc))
        except Exception as exc:  # noqa: BLE001 - show anything unexpected
            log(traceback.format_exc())
            self._fail("err_install", detail=repr(exc))

    def _after_install(self) -> None:
        action = self.s.after_install
        if action in ("reboot", "poweroff"):
            time.sleep(10)
            subprocess.run(["systemctl", action])
