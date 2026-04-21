{ privateIp, ... }:
{
  services.k3s.extraFlags = [
    "--flannel-iface=enp7s0"
    "--node-ip=${privateIp}"
  ];
}
