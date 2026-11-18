# Software catalog

Most software needs **no entry here**. If a name in a profile's `software:` list is
not in the catalog, it is installed as a normal package with that name
(`apt install <name>` on Debian, `pkgs.<name>` on NixOS). The automatic check
fails if that package does not exist.

An entry is only needed when an item has different names per OS, needs extra
repositories, or is not a plain package. An entry only needs a section for the
OS of the profiles that use it.

```yaml
id: example
unfree: false              # true → allowUnfree (NixOS) — Debian always enables all components
depends: [other-item]      # added automatically
nixos:
  packages: [pkgname]      # added to environment.systemPackages
  config: |                # NixOS module body; `config`, `pkgs` and `lib` are available
    programs.example.enable = true;
debian:
  keyring_debs: [https://…/keyring.deb]   # {debian} = Debian major version, e.g. 13
  foreign_arch: [i386]
  packages: [pkgname]
  venv: { path: /opt/x, pip: [x] }        # Python environment with pip packages
  files: [ { path: /etc/x.conf, content: "…", mode: "0644" } ]
  enable_services: [x.service]
```

Folders: `software/`, `drivers/`, `desktops/`. All names share one namespace.
