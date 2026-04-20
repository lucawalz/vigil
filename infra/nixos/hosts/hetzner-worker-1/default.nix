{ config, lib, pkgs, meta, ... }:
{
  imports = [
    ./disko-config.nix
    ../common
    ../../modules/k3s/agent.nix
    ../../modules/k3s/hetzner.nix
    ../../modules/services/monitoring.nix
    ../../modules/services/storage.nix
    ../../modules/services/rollback-gate.nix
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

  networking.hostName = "hetzner-worker-1";
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
}
