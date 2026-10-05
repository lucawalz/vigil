{ config, lib, privateIp, addresses, hubMac, ... }:
let
  hubInterface = "hub0";
  isServer = config.services.k3s.role == "server";
in
{
  _module.args.diskDevice = "/dev/vda";

  systemd.network.links."10-vigil-hub" = {
    matchConfig.MACAddress = hubMac;
    linkConfig.Name = hubInterface;
  };

  networking.interfaces.${hubInterface} = {
    useDHCP = false;
    ipv4.addresses = [
      { address = privateIp; prefixLength = addresses.nodePrefixLength; }
    ];
  };

  services.k3s.extraFlags = lib.mkIf config.services.k3s.enable ([
    "--flannel-iface=${hubInterface}"
    "--node-ip=${privateIp}"
  ] ++ lib.optional isServer "--tls-san=127.0.0.1");
}
