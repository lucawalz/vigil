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

  services.k3s.serverAddr = "https://10.0.0.10:6443";

  networking.firewall.allowedTCPPorts = [ 22 10250 ];
  networking.firewall.allowedUDPPorts = [ 8472 ];

  services.openssh = {
    enable = true;
    settings = {
      PermitRootLogin = "prohibit-password";
      PasswordAuthentication = false;
    };
  };

  services.vigilAutoReconciler = {
    enable = true;
    branch = "chore/eval-cluster-baseline";
  };
}
