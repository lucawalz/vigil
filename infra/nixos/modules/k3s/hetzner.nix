{ privateIp, ... }:
{
  services.k3s.extraFlags = [
    "--flannel-iface=eth0"
    "--node-ip=${privateIp}"
  ];
}
