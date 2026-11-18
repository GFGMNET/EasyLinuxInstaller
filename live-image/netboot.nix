# Network boot image (PXE / iPXE): same installer and menu as the USB stick.
{ modulesPath, ... }:
{
  imports = [ (modulesPath + "/installer/netboot/netboot-minimal.nix") ./common.nix ];
}
