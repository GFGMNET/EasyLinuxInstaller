{
  description = "EasyLinux Installer: USB/PXE live system that installs a NixOS or Debian profile";

  # The monthly build switches this to the newest stable release (see releases.yaml).
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";

  outputs = { self, nixpkgs }:
    let
      system = "x86_64-linux";
      pkgs = nixpkgs.legacyPackages.${system};
      live = module: nixpkgs.lib.nixosSystem { inherit system; modules = [ module ]; };
    in
    {
      nixosConfigurations.iso = live ./live-image/iso.nix;
      nixosConfigurations.netboot = live ./live-image/netboot.nix;

      packages.${system} = rec {
        iso = self.nixosConfigurations.iso.config.system.build.isoImage;
        netboot =
          let b = self.nixosConfigurations.netboot.config.system.build;
          in pkgs.runCommand "easylinux-netboot" { } ''
            mkdir -p $out
            cp ${b.kernel}/bzImage $out/bzImage
            cp ${b.netbootRamdisk}/initrd $out/initrd
            cp ${b.netbootIpxeScript}/netboot.ipxe $out/netboot.ipxe
          '';
        default = iso;
      };
    };
}
