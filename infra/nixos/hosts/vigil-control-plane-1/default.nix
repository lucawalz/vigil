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

  environment.systemPackages = [ pkgs.fluxcd pkgs.sops ];
  environment.variables.KUBECONFIG = "/etc/rancher/k3s/k3s.yaml";

  networking.firewall.allowedTCPPorts = [ 22 6443 10250 ];
  networking.firewall.allowedUDPPorts = [ 8472 ];

  services.openssh = {
    enable = true;
    settings = {
      PermitRootLogin = "prohibit-password";
      PasswordAuthentication = false;
    };
  };
}
