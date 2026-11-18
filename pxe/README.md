# Network boot (PXE)

The PXE image contains the same installer and menu as the USB stick. Every
Release has three files for it: `bzImage`, `initrd` and `netboot.ipxe`.

## What you need

- A small Linux server in the same network (it can be a VM)
- Its existing DHCP server stays untouched: dnsmasq runs in **proxy-DHCP** mode and only adds the boot information

## Setup (Debian/Ubuntu server)

```sh
sudo apt install dnsmasq ipxe nginx
sudo mkdir -p /srv/tftp /var/www/html/easylinux
sudo cp /usr/lib/ipxe/ipxe.efi /srv/tftp/

# newest release files
cd /var/www/html/easylinux
for f in bzImage initrd netboot.ipxe; do
  sudo curl -fLO "https://github.com/GFGMNET/EasyLinuxInstaller/releases/latest/download/$f"
done
sudo cp /path/to/repo/pxe/boot.ipxe /var/www/html/easylinux/boot.ipxe

sudo cp /path/to/repo/pxe/dnsmasq-easylinux.conf /etc/dnsmasq.d/easylinux.conf
sudo nano /etc/dnsmasq.d/easylinux.conf   # set your network and server IP
sudo systemctl restart dnsmasq
```

Then set the clients to **UEFI network boot** (Secure Boot off).

To update monthly, re-run the `curl` loop (for example from a cron job).

## Files

- `dnsmasq-easylinux.conf`: proxy-DHCP + TFTP for iPXE
- `boot.ipxe`: loaded by iPXE; it starts the EasyLinux kernel and initrd over HTTP
