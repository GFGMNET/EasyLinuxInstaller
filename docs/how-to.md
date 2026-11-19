# EasyLinux Installer – How-to

Everything is changed in **one place: GitHub**, in your browser.
Open a file → click the **pencil** ✏️ → change it → **Commit changes**.

Changes to profiles take effect **at the next boot of the stick**. No new ISO is needed.
PCs that are already installed are **not** changed.

---

## 1. Add software to a profile

**File:** `profiles/<profile>.yaml` (for example `profiles/games.yaml`)

Add the name to the `software:` line:

```yaml
software: [steam, brave]          # before
software: [steam, brave, vlc]     # after: vlc added
```

That's all. Most programs work like this.

### Where to find the right name

The name must be the **package name of the profile's OS** (`os:` line in the profile):

| Profile has | Look the name up here | Use |
|---|---|---|
| `os: nixos` | https://search.nixos.org/packages (choose the newest channel, e.g. 26.05) | the **name** shown, e.g. `vlc`, `brave`, `libreoffice` (names with a dot, like `python3Packages.x`, need a catalog file, see step 2) |
| `os: debian` | https://packages.debian.org (search, "stable") | the **package name**, e.g. `vlc`, `libreoffice`, `gimp` |

### Check that it worked

1. On GitHub, open **Actions → Check**. The newest run belongs to your change.
2. ✅ green: done, the next stick boot installs it.
3. ❌ red: open the run. It names the problem, usually a typo or a name that doesn't exist for that OS. Fix the name and commit again.

---

## 2. Special software (only if step 1 is not enough)

Some software needs more than a package name. Examples:

- the name is **different** on Debian and NixOS
- it needs an **extra software source** (for example NVIDIA's repository)
- it is **not a normal package** (vLLM: installed with Python's `pip`)
- it needs a **setting** (Steam on NixOS: `programs.steam.enable = true;`)

For these, there is one small file per program in **`catalog/software/`**. The profile then still only lists the name.

**Create a new file:** on GitHub, open the folder `catalog/software/` → **Add file → Create new file** → name it `<name>.yaml`.

You only need a section for the OS that uses it:

```yaml
# catalog/software/example.yaml  — for a NixOS profile
id: example
nixos:
  packages: [example-package]           # normal packages to install
  config: |                             # NixOS settings (optional)
    programs.example.enable = true;
```

```yaml
# catalog/software/example.yaml  — for a Debian profile
id: example
debian:
  packages: [example-package]           # apt packages
  keyring_debs:                         # extra software source (optional)
    - https://example.com/example-keyring.deb
```

Then add `example` to the profile's `software:` list as in step 1.
If unsure, copy an existing file: `catalog/software/steam.yaml` (NixOS) or `catalog/software/vllm.yaml` (Debian).

---

## 3. Change other things in a profile

All in `profiles/<profile>.yaml`:

```yaml
id: games                 # short name: lowercase letters, digits, "-". Used for the PC name: games-<mac>
name: Games               # what the menu shows
os: nixos                 # nixos or debian (always the newest stable version)
requires:
  gpu: any                # nvidia, amd or any. The menu refuses PCs without it. Remove the line if not needed.
system:
  timezone: Europe/Berlin
users:
  - name: admin
    password: admin       # public! The user must set a new password after the first login.
    admin: true           # true = may use sudo
desktop: awesome          # see the list below
drivers: [nvidia]         # see the list below
software: [steam, brave]
```

The **language and keyboard** are not in the profile. They come from the first screen of the stick.

### Available desktops and drivers

| Name | Type | Works with |
|---|---|---|
| `awesome` | desktop | NixOS |
| `kde` | desktop | Debian |
| `nvidia` | driver: NVIDIA, newest version | NixOS, Debian |
| `cuda` | driver: NVIDIA CUDA | Debian |
| `amd` | driver: AMD graphics | NixOS, Debian |
| `gpu-auto` | driver: picks `nvidia` or `amd` for the graphics card in the PC | NixOS, Debian |

A desktop or driver for the other OS can be added the same way as in step 2, in `catalog/desktops/` or `catalog/drivers/`.

> 💡 If a profile has `gpu: any`, use `drivers: [gpu-auto]`. Then a PC with an AMD card gets the AMD driver instead of the NVIDIA one.

---

## 4. Add a new profile

1. Open `profiles/` → open an existing profile → copy its text.
2. **Add file → Create new file** → name it `profiles/<new-id>.yaml`.
3. Paste and change at least `id`, `name`, `os`, `software`.
4. Commit. Check that **Actions → Check** is green.

The new name appears in the menu at the next stick boot.
To **remove** a profile, delete its file.

---

## 5. Make a USB stick

1. Download the newest ISO: https://github.com/GFGMNET/EasyLinuxInstaller/releases/latest/download/easylinux-x86_64.iso
2. Write it with **balenaEtcher**, or **Rufus in DD mode**.
3. On the PC: UEFI boot from the stick, **Secure Boot off**, network **cable** plugged in.
4. Choose a language → click a profile → wait. The PC restarts by itself.

⚠️ Clicking a profile **erases the first internal disk immediately**.

**From another PC:** the bottom of the stick's screen shows `http://<ip>:8080/?token=…`. Open that address to follow the installation.

---

## 6. New ISO versions

GitHub builds a new ISO automatically:

- **monthly**, if newer NixOS/Debian versions or packages exist
- **after every change to the installer code** (not after profile changes, because those don't need a new ISO)
- **manually:** Actions → Build ISO → **Run workflow**

Each build is test-installed (Debian and NixOS) in a virtual machine before it is published under **Releases**.
Old sticks keep working. Only make a new stick if you want the newer live system.

---

## 7. Network boot (PXE)

Instead of a USB stick, PCs can boot the same installer over the network. Setup: see [`pxe/README.md`](../pxe/README.md).

---

## 8. Problems

| Problem | Cause / fix |
|---|---|
| "Profiles could not be downloaded" | No internet. Check the cable, then click **Retry**. |
| "This profile needs an NVIDIA graphics card" | `requires: gpu:` in the profile doesn't match the PC. Change or remove that line. |
| "No internal disk found" | The PC has no internal disk of at least 16 GB (USB disks are never used). |
| "The installation failed" | The details are on the screen. A profile with a wrong software name is the most common cause; check **Actions → Check**. |
| PC doesn't boot the stick | Turn Secure Boot off, and boot in UEFI mode. With Rufus, use DD mode. |
| Login screen doesn't accept the new password | Use the password set in the "Set a new password" window. Until it is changed, the profile's password works. |
