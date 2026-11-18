# USB stick image (UEFI, runs from RAM).
{ modulesPath, lib, ... }:
{
  imports = [ (modulesPath + "/installer/cd-dvd/installation-cd-minimal.nix") ./common.nix ];

  image.baseName = lib.mkForce "easylinux-x86_64";
  isoImage.volumeID = "EASYLINUX";           # the installer never touches the disk with this label
  isoImage.makeEfiBootable = true;
  isoImage.makeUsbBootable = true;
  isoImage.makeBiosBootable = false;         # UEFI only
  boot.kernelParams = [ "copytoram" ];       # the stick can be removed after boot
}
