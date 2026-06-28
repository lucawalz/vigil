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

  networking.hostName = "hetzner-worker-2";
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

  # Add kubelet disk pressure management
  services.k3s.extraFlags = [
    "--node-label=node.kubernetes.io/role=worker"
    # Adjust disk pressure thresholds to be more tolerant
    "--eviction-hard=memory.available<100Mi,nodefs.available<5%,nodefs.inodesFree<5%,imagefs.available<5%"
    "--eviction-soft=memory.available<300Mi,nodefs.available<10%,nodefs.inodesFree<10%,imagefs.available<10%"
    "--eviction-soft-grace-period=memory.available=2m,nodefs.available=2m,nodefs.inodesFree=2m,imagefs.available=2m"
    "--eviction-minimum-reclaim=memory.available=0Mi,nodefs.available=500Mi,nodefs.inodesFree=1000,imagefs.available=500Mi"
    # Configure image garbage collection
    "--image-gc-high-threshold=85"
    "--image-gc-low-threshold=80"
  ];
}