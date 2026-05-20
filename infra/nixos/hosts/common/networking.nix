{ ... }:
{
  networking.useDHCP = true;

  services.resolved.enable = true;

  networking.firewall = {
    enable = true;
    allowedTCPPorts = [ 22 ];
  };
}
