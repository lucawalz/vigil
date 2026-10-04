{ lib, inventory }:
let
  basePrefixLength = 16;
  nodeThirdOctet = 0;
  nodePrefixLength = 24;
  serviceThirdOctet = 64;
  servicePrefixLength = 18;
  podThirdOctet = 128;
  podPrefixLength = 17;
  apiServerPort = 6443;

  baseParts = lib.splitString "/" inventory.network.base;
  baseOctets = lib.splitString "." (lib.head baseParts);
  prefix = lib.toIntBase10 (lib.last baseParts);
  network = "${lib.elemAt baseOctets 0}.${lib.elemAt baseOctets 1}";
  subnet = thirdOctet: length: "${network}.${toString thirdOctet}.0/${toString length}";
  hostIp = index: "${network}.${toString nodeThirdOctet}.${toString index}";
  controlPlane = lib.findFirst (host: host.role == "control-plane")
    (throw "infra/inventory.json lists no control-plane host")
    inventory.hosts;
in
assert lib.assertMsg (lib.length baseOctets == 4 && prefix == basePrefixLength)
  "infra/inventory.json network.base must be an IPv4 /${toString basePrefixLength}, got ${inventory.network.base}";
{
  inherit (inventory.network) base;
  inherit nodePrefixLength;
  serviceCidr = subnet serviceThirdOctet servicePrefixLength;
  podCidr = subnet podThirdOctet podPrefixLength;
  apiServerUrl = "https://${hostIp controlPlane.index}:${toString apiServerPort}";
  hosts = lib.listToAttrs (map
    (host: lib.nameValuePair host.name {
      inherit (host) role index;
      ip = hostIp host.index;
    })
    inventory.hosts);
}
