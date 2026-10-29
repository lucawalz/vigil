{ config, lib, pkgs, meta, ... }:
{
  imports = [
    ../common
  ];

  boot.initrd.availableKernelModules = [
    "ahci"
    "sd_mod"
    "sr_mod"
    "virtio_pci"
    "virtio_scsi"
    "virtio_blk"
  ];

  system.stateVersion = "25.05";

  networking.firewall.allowedTCPPorts = [ 22 10250 ];
  networking.firewall.allowedUDPPorts = [ 8472 ];

  services.openssh = {
    enable = true;
    settings = {
      PermitRootLogin = "prohibit-password";
      PasswordAuthentication = false;
    };
  };

  services.vigilAutoReconciler.enable = true;

  # Enable k3s service with proper unit configuration
  services.k3s = {
    enable = true;
    role = "server"; # or "agent" depending on cluster role
  };
}
