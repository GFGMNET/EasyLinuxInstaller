# EasyLinux Install — Design Document

**Status:** Draft v0.5 · **Date:** 2026-11-16

---

## 0. Decisions log

| # | Decision | Consequence |
|---|---|---|
| D1 | **Public** GitHub repo | No token needed to download; Pages, Releases and standard Actions runners are free; **no secrets or password hashes in the repo** |
| D2 | **UEFI only** | GPT + EFI system partition; **systemd-boot** on both OSes |
| D3 | **Secure Boot is off** on clients | The live system is built with **NixOS** |
| D4 | Profiles choose the OS: **NixOS or Debian** | Profiles + software catalog + one installer backend per OS |
| D5 | NVIDIA GPUs are **RTX 20xx or newer** | Open NVIDIA kernel module |
| D6 | **Newest NVIDIA driver** | NixOS `nvidiaPackages.latest`; Debian uses NVIDIA's official repo (driver + CUDA) |
| D7 | **Internet is always available** during installation | Everything is downloaded at install time |
| D8 | **1–5 clients** at a time | No local mirror needed |
| D9 | vLLM on Debian: **Python environment** (`/opt/vllm`) + systemd service | — |
| D10 | **Graphical menu = profile selection** | Kiosk web UI: choose a profile, then click Install |
| D11 | **No disk encryption** | The password would have to be public in the profile, so it gives no real protection |
| D12 | **Unattended mode installs immediately** | No countdown, no extra confirmation |
| D13 | **No `extra:` section** in profiles | Only names; unknown names install as normal packages |
| D14 | **AMD GPUs** supported + `gpu-auto` | — |
| D15 | **Remote UI with token** | The same menu in another PC's browser |
| D16 | **Only PXE is deferred** | Phase B |
| D17 | **No signing** of ISO or profiles | Simpler; HTTPS from GitHub is the trust anchor |
| D18 | **Profiles and catalog are always downloaded from GitHub** at boot | No copy in the ISO; changing a profile needs **no new ISO** |
| D19 | **Always the newest versions** | NixOS installs from the newest nixpkgs of the current stable release at install time (not pinned); Debian always uses current `stable` |
| D20 | **Disk: always the first internal disk**, automatically | No disk selection screen |
| D21 | **ISO builds:** monthly, **only if updates exist**, plus on push of code changes | See 3.8 |
| D22 | **Newest stable** versions | NixOS: current stable release (for example 26.05, then 26.11); Debian: current `stable` |
| D23 | **Wired network only** | No Wi-Fi screen; DHCP on cable |
| D24 | **No network checks** | Just try to download the profiles; on failure show a clear error message (with a Retry button) |
| D25 | Profile changes are **used immediately** (`main` branch) | CI checks still run after each push, but they don't block anything. A broken profile is visible right away. |
| D26 | **Menu in English and German** | Language switch on the first screen; all texts in translation files |
| D27 | **One stick holds all profiles** | The profile is chosen in the menu |
| D28 | **Two screens: 1. Language → 2. Profile names (click = install)**; the language also applies to the installed system | No other screens; after Install everything runs automatically. This replaces the separate zero-touch unattended boot entries. |
| D29 | **Hostname = `<profile>-<mac>`**, for example `games-a1b2c3d4e5f6` | Unique per PC; a hyphen instead of `_`, because underscores are not allowed in hostnames |
| D30 | **Username and password are defined in the profile** (for example `admin` / `admin`) | They are visible in the public repo, so the **password must be changed at first login** (through a window shown right after the first login, see F1) and SSH password login is off |
| D31 | **No settings file on the stick** | Everything comes from the profile; the stick is just the ISO written with Rufus, Etcher or `dd`; no `prepare-stick` tool needed |

---

## 1. Goal

A UEFI USB stick (PXE later). It boots, shows a **graphical profile selection**, and installs the chosen profile onto the **first internal disk**. It can also run **fully unattended**. Profiles decide the **OS (NixOS or Debian)**, desktop, drivers and software. Profiles live on GitHub and are **always downloaded fresh** at boot.

| Profile | OS | Desktop | Drivers | Software |
|---|---|---|---|---|
| **Games** | NixOS | Awesome WM | NVIDIA | Steam |
| **AI** | Debian | KDE Plasma | NVIDIA + CUDA | vLLM |

**Non-goals:** dual-boot, keeping existing data, other distros, managing PCs after installation. **PXE comes in phase B.**

---

## 2. Architecture

```
 GitHub (public)                                  Client PC (UEFI)
 ┌─────────────────────────┐                      ┌──────────────────────────────────┐
 │ installer/ live-image/  │── code push/monthly ─►│ USB stick: live system (in RAM)  │
 │   → Actions → ISO       │      (Release)        │                                  │
 │                         │                       │  Menu (kiosk) ◄─► Installer      │
 │ profiles/ catalog/      │── downloaded at boot ─►│  Remote UI    ◄─► daemon + API   │
 │   (no ISO rebuild)      │                       │  Answer file  ──►     │          │
 └─────────────────────────┘                      │              Debian / NixOS       │
                                                  └───────────────────────┼──────────┘
                                                                          ▼
                                                                  first internal disk
```

- Profiles say *what*, the catalog says *how* for each OS, and the backends do the work.
- The installer is a **daemon with an API**. The menu, remote UI and unattended mode all use it.

---

## 3. Components

### 3.1 Live system (the USB stick)
- Built with **NixOS**, UEFI only, runs from RAM (the stick can be removed after boot)
- Basic graphics that work on any GPU (no NVIDIA driver needed for the menu)
- Boot menu: `EasyLinux` (default) · `Safe graphics` · `Shell`
- At startup: connects to the network, then **downloads profiles and catalog from GitHub** (`main` branch)

### 3.2 Graphical menu + remote UI
- Full-screen web UI in a kiosk browser
- **Two screens:** 1. **Language** (English / German) → 2. **Profile**: a plain list of **profile names only**; click a name to install. After that only a progress bar is shown, then the PC reboots. Nothing else is asked.
- **The chosen language is used for the menu and for the installed system** (system language and keyboard). Timezone comes from the profile.
- If the hardware does not fit the chosen profile (3.9), an error message is shown instead of installing.
- **Remote UI:** `http://<client-ip>:8080`, works only with the **token shown on the client's screen**

### 3.3 Profile format
```yaml
# profiles/games.yaml
id: games
name: "Gaming PC"
os: nixos                    # nixos | debian — always newest stable (D19)
requires: { gpu: nvidia }
system: { locale: de_DE.UTF-8, timezone: Europe/Berlin, keyboard: de }   # hostname is always games-<mac> (D29)
users:
  - { name: admin, password: admin, admin: true }   # must be changed at first login (D30)
desktop: awesome
drivers: [nvidia]
software: [steam]
```
```yaml
# profiles/ai.yaml
id: ai
name: "AI Workstation"
os: debian
requires: { gpu: nvidia, min_ram_gb: 32 }
system: { locale: de_DE.UTF-8, timezone: Europe/Berlin, keyboard: de }   # hostname: ai-<mac>
users:
  - { name: admin, password: admin, admin: true }
desktop: kde
drivers: [nvidia, cuda]
software: [vllm]
```
All values come from the profile; nothing is asked. To add software, add a name to `software:`.
**First login:** the password is marked as expired (`chage -d 0` on Debian, the same expiry set at install time on NixOS), so the user must set a new one. SSH, if installed, only allows key login.

### 3.4 Software catalog (special cases only)
A catalog entry only needs sections for the OSes of the profiles that actually use it.
Most software needs **no catalog entry**. `htop` installs `htop` on both OSes. A catalog entry is only needed when an item:
- has **different names** on Debian and NixOS (`firefox-esr` vs `firefox`)
- needs **extra repositories** (NVIDIA repo, Debian `non-free`, 32-bit packages for Steam)
- is **not a package** (vLLM through pip, a service, a setting such as gamemode)

```yaml
# catalog/software/steam.yaml
id: steam
unfree: true
nixos:  { config: "programs.steam.enable = true;" }
# only a NixOS section: only the Games profile (NixOS) uses Steam
```
```yaml
# catalog/software/vllm.yaml
id: vllm
depends: [nvidia, cuda]
debian: { method: python-venv, venv: /opt/vllm, pip: [vllm], service: vllm.service }
# only a Debian section: only the AI profile (Debian) uses vLLM
```
```yaml
# catalog/drivers/nvidia.yaml
id: nvidia
unfree: true
nixos:
  config: |
    services.xserver.videoDrivers = [ "nvidia" ];
    hardware.graphics.enable = true;
    hardware.nvidia.open = true;
    hardware.nvidia.modesetting.enable = true;
    hardware.nvidia.branch = "latest";   # newest of production/new_feature (default would be "stable")
debian:
  repos: [ { name: nvidia-cuda, url: "https://developer.download.nvidia.com/compute/cuda/repos/debian13/x86_64/", keyring: cuda-keyring } ]
  components: [contrib]
  packages: [nvidia-open, linux-headers-amd64]   # never mix with Debian's own nvidia-driver packages
```
Also included: `cuda` (Debian only, used by AI), `amd` and `gpu-auto` (D14), desktop `awesome` (NixOS only, used by Games) and desktop `kde` (Debian only, used by AI). `nvidia` has both sections because both profiles use it.

### 3.5 Installer
1. Download profiles and catalog from GitHub
2. Hardware check (3.9)
3. Take the **first internal disk** (3.7), wipe it, create GPT + 1 GiB EFI partition + root (ext4)
4. **Debian:** debootstrap `stable` → apt sources (including NVIDIA repo if needed) → install desktop, drivers, software → users, locale → systemd-boot
5. **NixOS:** generate config from profile and catalog → `nixos-install` from the **newest nixpkgs** of the current stable release → systemd-boot
6. Write the log, then reboot

### 3.6 Automatic installation
After the user clicks **Install**, everything runs without questions: disk, hostname (`<profile>-<mac>`), users, software, reboot. There is no settings file on the stick (D31).
⚠️ Clicking Install wipes the first internal disk immediately, with no second confirmation.

### 3.7 Disk rule
Always the **first internal disk**: NVMe first, then SATA. **The USB stick itself and other USB or removable drives are always excluded.** There is no selection screen. If no internal disk is found, the installer stops with an error.

### 3.8 Build pipeline (GitHub Actions)
| Trigger | What happens |
|---|---|
| **Monthly** (1st of the month) | Check for updates (new NixOS packages, kernel, drivers). **Build a new ISO only if something changed.** |
| **Push of code changes** (`installer/`, `live-image/`, `flake.nix`) | Build a new ISO immediately |
| **Push of profile or catalog changes** | Run the checks only. **No new ISO is needed**, because profiles are downloaded at boot. |
| Manual button | Build now |

Each run: **checks** (3.10) → build ISO → test install in a VM → publish a GitHub Release + download page.

### 3.9 Hardware check
Before installing, the live system looks at the PC's GPU, RAM and disk. If a profile needs something the PC doesn't have, for example `requires: { gpu: nvidia }` on a PC without an NVIDIA card, the profile shows a warning in the menu, or the unattended install stops. This prevents an install that "works" but leaves a broken desktop or a vLLM that cannot run.

### 3.10 Automatic checks (CI)
Before anything is published, GitHub checks:
1. Every profile is written correctly (no missing fields, no typos in keys)
2. Every software name exists for its OS, as a catalog entry or a real package
3. Every NixOS profile actually builds
4. Every Debian package can be installed
5. A real test install of one NixOS and one Debian profile in a virtual machine boots afterwards

Without the GPU parts, because GitHub has no GPU.

---

## 4. Repository structure
```
easylinux-install/
├── flake.nix                 # builds the live ISO
├── profiles/                 # games.yaml, ai.yaml  → downloaded at boot
├── catalog/                  # special cases        → downloaded at boot
├── schema/                   # format rules for profiles, catalog, answer file
├── installer/                # daemon, backends (debian, nixos), web UI
├── live-image/               # USB live system config
├── tools/                    # prepare-stick script (see 3.11)
├── docs/                     # GitHub Pages download page
└── .github/workflows/
```

### 3.11 Tools
None needed. Write the ISO to the stick with Rufus, balenaEtcher or `dd`.

---

## 5. Security
- Profiles and the catalog run as root and wipe disks. Require pull request review and branch protection on GitHub.
- Default passwords in profiles are **public** (D30). They are therefore forced to change at first login, and SSH password login is disabled.
- The remote UI only works with the on-screen token.
- No signing (D17). Downloads are protected by HTTPS from GitHub only.

---

## 6. Roadmap
| Phase | Scope |
|---|---|
| **A – Complete USB installer** | Everything in this document except PXE |
| **B – PXE** | Network boot |

**No code is written until every open question below is answered.**

## 7. Open questions
1. GitHub repo: not created yet. This is needed before the first build, not for the design.

**Fact-check findings resolved within the existing decisions (no new features):**
| Finding | Resolution | Based on |
|---|---|---|
| F1 KDE login can't handle an expired password | Keep D30's rule ("password must be changed at first login"). Enforce it with a **"set new password" window that opens right after login and comes back at every login until the password has been changed**, instead of `chage -d 0`. This works the same with KDE (SDDM) and Awesome (LightDM), because the password is never marked as expired. | D30 |
| F2 vLLM in NixOS is old and compiles for hours | Not relevant: vLLM is only in the AI profile (Debian) | D9 |
| F6 Hybrid-GPU laptops need extra setup | No action. Onboard GPUs work with the kernel's built-in drivers. Only on a laptop with onboard + NVIDIA could the NVIDIA chip stay unused; the screen still works. | — |
| F8 Debian only ships `firefox-esr` | Not relevant: no profile installs Firefox. If one ever does, its catalog entry uses Mozilla's apt repo (newest) | D19 |

---

## 8. Fact-check (2026-11-18)

### ❌ Problems found (design must change)
| # | Finding | Impact |
|---|---|---|
| F1 | **SDDM (KDE login screen) does not support expired passwords.** With `chage -d 0` the user just gets "login failed"; it only works on the text console. The upstream fix (SDDM PR 776) is unmerged. LightDM's support is also unreliable. | D30 "change password at first login" **breaks the AI profile's login** and is risky for Games |
| F2 | **vLLM in NixOS 26.05 is version 0.16.0**, while PyPI has 0.34.0. CUDA builds are **not in the official NixOS cache**; the community cache `cache.nixos-cuda.org` has gaps. | Not the newest version, and the install could **compile for hours** |

### ⚠️ Corrections (already applied above)
| # | Finding |
|---|---|
| F3 | NixOS: the newest driver is selected with `hardware.nvidia.branch = "latest"`; the default is `"stable"` |
| F4 | Debian: NVIDIA's repo needs `contrib` enabled; never mix NVIDIA's repo with Debian's own `nvidia-driver` packages |
| F5 | Steam on Debian: not relevant, because Steam is only in the Games profile (NixOS) |
| F6 | Laptops with hybrid graphics (Optimus) need extra PRIME configuration with PCI bus IDs, otherwise the NVIDIA GPU may not work |
| F7 | `hardware.amdgpu.initrd.enable` exists but is only cosmetic (boot-screen resolution); it can be left out |
| F8 | Debian 13 only ships `firefox-esr`, not `firefox`. The newest Firefox needs Mozilla's own apt repo |
| F9 | Profiles from GitHub: raw files are cached for about **5 minutes**, so a change can take that long to appear. GitHub limits unauthenticated downloads per IP (tightened in 2025). Download **one archive** per boot, not many single files. |
| F10 | GitHub runners have about **14 GB** of documented disk space. The ISO build job needs a "free disk space" step. |

### ✅ Confirmed
- NixOS **26.05** is the current stable (released 2026-05-30, supported until 2026-12-31); **26.11** is in preparation, date not fixed yet. The installer must detect the current stable release automatically.
- Debian **13 "trixie"** is stable, current point release **13.7** (2026-09-12)
- NVIDIA's **debian13 repo** exists (`cuda-keyring_1.1-1_all.deb`); `apt install nvidia-open` is NVIDIA's documented way; the current driver is **620.70.06**, and the repo tracks the newest branch unless pinned
- Open NVIDIA module: RTX 20xx / GTX 16xx and newer
- vLLM from PyPI supports Python **3.11–3.14**, so Debian 13's Python 3.13 works
- `steam-installer` is in Debian 13 `contrib`
- NixOS options `hardware.nvidia.open`, `modesetting.enable`, `hardware.graphics.enable`, `services.xserver.videoDrivers` are current
- GitHub: standard runners are free and unlimited for public repos; scheduled workflows are disabled after **60 days without activity** (the monthly commit keeps them alive); scheduled runs can be delayed under load
- GitHub Releases: each file must be **under 2 GiB**, up to 1000 files, no total or bandwidth limit
- Hostnames: no underscores allowed (hence `games-<mac>`)

### Still unverified (to test during the build, not blocking)
- `/dev/kvm` on standard GitHub runners for the test install (documented for Android emulation; needs a udev rule)
- The kiosk menu on basic framebuffer graphics (expected to work, at firmware resolution)
- Rufus needs "DD mode" for the NixOS ISO
