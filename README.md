# EasyLinux Installer

A bootable UEFI USB stick (or PXE network boot) that installs a Linux profile onto the **first internal disk**:

1. Pick a language (English / Deutsch)
2. Click a profile name, and the installation starts. **The first internal disk is erased.**

| Profile | OS | Desktop | Drivers | Software |
|---|---|---|---|---|
| Games | NixOS | Awesome | NVIDIA | Steam |
| AI | Debian | KDE Plasma | NVIDIA + CUDA | vLLM |

**Download:** [newest ISO](https://github.com/GFGMNET/EasyLinuxInstaller/releases/latest/download/easylinux-x86_64.iso)
Write it with balenaEtcher, or with Rufus in **DD mode**. UEFI only, Secure Boot off, network cable required.

## How it works

- `profiles/`: one YAML file per profile. They are **downloaded at every boot**, so a change works without a new ISO.
- `catalog/`: only for special cases (extra repositories, settings, non-package software). Any other name in `software:` installs as a normal package.
- `releases.yaml`: newest stable NixOS and Debian versions (updated monthly by CI).
- `installer/`: menu server + Debian/NixOS installers (Python).
- `live-image/`, `flake.nix`: the NixOS live system (USB ISO and PXE).
- `pxe/`: network boot setup.

**Default users from the profile** (for example `admin` / `admin`) are public. A window asks for a new password after every login until it has been changed.

**Remote UI:** the PC's screen shows `http://<ip>:8080/?token=…`. Open it from another PC to follow or start an installation.

## GitHub Actions

- **Check** (every push): profiles, catalog and installer tests; Debian packages exist; NixOS configs evaluate.
- **Build ISO**: monthly (only if updates exist), on code changes, or manually. It builds, test-installs NixOS and Debian in a VM, then publishes a Release.

Design: [docs/design-document.md](docs/design-document.md)
