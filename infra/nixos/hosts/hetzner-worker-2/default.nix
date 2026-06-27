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

  services.k3s = {
    enable = true;
    role = "agent";
    serverAddr = "https://10.0.0.10:6443";
    tokenFile = "/etc/k3s/token";
    extraFlags = [ 
      "--node-label=node.kubernetes.io/role=worker"
      "--flannel-iface=enp7s0"
    ];
  };

  boot.kernel.sysctl."net.bridge.bridge-nf-call-iptables" = lib.mkDefault 1;

  # Additional configuration from the common modules
  boot.loader.grub = {
    enable = true;
    device = "/dev/sda";
    efiSupport = true;
    efiInstallAsRemovable = true;
  };

  time.timeZone = "Europe/Berlin";
  i18n.defaultLocale = "en_US.UTF-8";
  console = {
    font = "Lat2-Terminus16";
    keyMap = "de";
  };

  networking.useDHCP = true;
  services.resolved.enable = true;

  nix.settings = {
    experimental-features = [ "nix-command" "flakes" ];
    trusted-users = [ "root" "@wheel" ];
  };

  programs.ssh.extraConfig = ''
    Host github.com
      IdentityFile /etc/ssh/ssh_host_ed25519_key
      IdentitiesOnly yes
  '';

  environment.systemPackages = with pkgs; [
    neovim
    k3s
    cifs-utils
    nfs-utils
    git
    age
    htop
    tmux
    tree
  ];

  users.users.${meta.hostname} = {
    isNormalUser = true;
    extraGroups = [ "wheel" ];
  };

  security.sudo.wheelNeedsPassword = false;
}