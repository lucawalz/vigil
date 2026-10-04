{ config, lib, privateIp, ... }:
{
  imports = [ ../modules/services/cloud-keys.nix ];
  _module.args.diskDevice = "/dev/sda";

  services.k3s.extraFlags = lib.mkIf config.services.k3s.enable [
    "--flannel-iface=enp7s0"
    "--node-ip=${privateIp}"
  ];
}
