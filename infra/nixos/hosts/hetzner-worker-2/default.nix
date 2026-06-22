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

  # Add kubelet garbage collection settings to manage disk pressure
  services.k3s.extraFlags = lib.mkAfter [
    "--node-label=node.kubernetes.io/role=worker"
    "--kubelet-arg=image-gc-high-threshold=85"
    "--kubelet-arg=image-gc-low-threshold=80"
    "--kubelet-arg=eviction-hard=imagefs.available<15%,nodefs.available<10%,nodefs.inodesFree<5%"
    "--kubelet-arg=eviction-soft=imagefs.available<30%,nodefs.available<20%,nodefs.inodesFree<10%"
    "--kubelet-arg=eviction-soft-grace-period=imagefs.available=2m,nodefs.available=2m,nodefs.inodesFree=2m"
    "--kubelet-arg=eviction-minimum-reclaim=imagefs.available=500Mi,nodefs.available=500Mi,nodefs.inodesFree=1000"
  ];
}