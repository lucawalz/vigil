{ config, lib, pkgs, meta, ... }:
{
  imports = [
    ./disko-config.nix
    ../common
  ];

  boot.loader.systemd-boot.enable = lib.mkForce false;
  boot.loader.grub = {
    enable = true;
    devices = lib.mkForce [ "/dev/sda" ];
    efiSupport = lib.mkForce false;
    efiInstallAsRemovable = lib.mkForce false;
  };
  boot.loader.efi.canTouchEfiVariables = lib.mkForce false;

  boot.initrd.availableKernelModules = [
    "ahci"
    "sd_mod"
    "sr_mod"
    "virtio_pci"
    "virtio_scsi"
    "virtio_blk"
  ];

  networking.hostName = "hetzner-agent";
  system.stateVersion = "25.05";

  networking.firewall.allowedTCPPorts = [ 22 9099 ];

  services.openssh = {
    enable = true;
    settings = {
      PermitRootLogin = "prohibit-password";
      PasswordAuthentication = false;
    };
  };
}
