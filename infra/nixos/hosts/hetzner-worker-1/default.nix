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
    ../../modules/services/auto-reconciler.nix
  ];

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

  services.vigilAutoReconciler = {
    enable = true;
    branch = "chore/eval-cluster-baseline";
  };

  # Fix: Explicitly configure k3s service ExecStart to ensure valid systemd unit
  systemd.services.k3s = {
    enable = true;
    description = "Lightweight Kubernetes Agent";
    wantedBy = [ "multi-user.target" ];
    wants = [ "network-online.target" ];
    after = [ "network-online.target" ];
    serviceConfig = {
      Type = "notify";
      ExecStart = "${pkgs.k3s}/bin/k3s agent --server https://10.0.0.10:6443";
      Restart = "always";
    };
  };
}