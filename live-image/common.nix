# Shared by the USB image (iso.nix) and the network boot image (netboot.nix):
# the installer service plus the full-screen menu (kiosk browser).
{ config, pkgs, lib, ... }:
let
  python = pkgs.python3.withPackages (ps: [ ps.pyyaml ]);

  installer = pkgs.runCommand "easylinux-installer" { } ''
    mkdir -p $out/lib
    cp -r ${../installer/easylinux} $out/lib/easylinux
  '';

  # tools the installer calls
  installerPath = with pkgs; [
    coreutils util-linux gptfdisk dosfstools e2fsprogs parted pciutils iproute2
    gnutar gzip gnugrep gnused systemd debootstrap
    config.nix.package
    config.system.build.nixos-install
    config.system.build.nixos-generate-config
    pkgs.nixos-enter
  ];

  # wait until the menu server answers, then open it full-screen
  kiosk = pkgs.writeShellScript "easylinux-kiosk" ''
    until ${pkgs.curl}/bin/curl -fsS -o /dev/null http://127.0.0.1:8080/; do sleep 1; done
    exec ${config.programs.firefox.package}/bin/firefox --kiosk --private-window http://127.0.0.1:8080/
  '';
in
{
  system.nixos.distroName = "EasyLinux";
  networking.hostName = "easylinux";
  networking.firewall.allowedTCPPorts = [ 8080 ];   # remote UI (token protected)
  boot.kernelModules = [ "qemu_fw_cfg" ];           # settings for the automatic test (harmless elsewhere)
  nix.settings.experimental-features = [ "nix-command" "flakes" ];
  documentation.enable = lib.mkForce false;

  systemd.services.easylinux-installer = {
    description = "EasyLinux installer (menu server)";
    wantedBy = [ "multi-user.target" ];
    wants = [ "network-online.target" ];
    after = [ "network-online.target" ];
    path = installerPath;
    environment = {
      PYTHONPATH = "${installer}/lib";
      PYTHONUNBUFFERED = "1";
      EASYLINUX_DEBIAN_KEYRING = "${pkgs.debian-archive-keyring}/share/keyrings/debian-archive-keyring.gpg";
    };
    serviceConfig = {
      ExecStart = "${python}/bin/python3 -m easylinux.main";
      Restart = "on-failure";
      RestartSec = 3;
    };
  };

  # full-screen menu on tty1 (other consoles: Ctrl+Alt+F2 = shell)
  users.users.kiosk = { isNormalUser = true; };
  services.cage = {
    enable = true;
    user = "kiosk";
    program = "${kiosk}";
    environment = { MOZ_ENABLE_WAYLAND = "1"; };
  };
  programs.firefox = {
    enable = true;
    policies = {
      DisableTelemetry = true;
      DisableFirefoxStudies = true;
      DisablePocket = true;
      DontCheckDefaultBrowser = true;
      OverrideFirstRunPage = "";
      OverridePostUpdatePage = "";
      NoDefaultBookmarks = true;
      DisableAppUpdate = true;
      UserMessaging = { WhatsNew = false; ExtensionRecommendations = false; FeatureRecommendations = false; SkipOnboarding = true; };
    };
  };
}
