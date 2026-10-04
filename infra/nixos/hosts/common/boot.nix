{ diskDevice, pkgs, ... }:
{
  boot.loader.grub = {
    enable = true;
    device = if pkgs.stdenv.hostPlatform.isx86 then diskDevice else "nodev";
    efiSupport = true;
    efiInstallAsRemovable = true;
  };
}
