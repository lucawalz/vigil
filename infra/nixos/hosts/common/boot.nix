{ ... }:
{
  boot.loader.systemd-boot.enable = false;
  boot.loader.grub = {
    enable = true;
    devices = [ "/dev/sda" ];
    forceInstall = true;
  };
}
