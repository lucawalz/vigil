{ nixpkgs, self, disko, ... }:
let
  inherit (nixpkgs) lib;
  inventory = lib.importJSON ../../inventory.json;
  addresses = import ./addresses.nix { inherit lib inventory; };
  roleModules = {
    control-plane = [
      ../modules/k3s/server.nix
      ../modules/services/monitoring.nix
      ../modules/services/storage.nix
      ../modules/services/rollback-gate.nix
    ];
    worker = [
      ../modules/k3s/agent.nix
      ../modules/services/monitoring.nix
      ../modules/services/storage.nix
      ../modules/services/rollback-gate.nix
      ../modules/services/auto-reconciler.nix
    ];
    agent = [ ];
  };
  flakeAttr = { name, target, system }:
    if target == "hetzner" then name else "${name}-lab-${lib.head (lib.splitString "-" system)}";
  labSystems = [ "x86_64-linux" "aarch64-linux" ];
  labHosts = lib.filter (host: host.role != "agent") inventory.hosts;
  labMacPrefix = "52:54:00:fa:00";
  macOctetDigits = 2;
  hubMac = index: "${labMacPrefix}:${lib.fixedWidthNumber macOctetDigits index}";
  labPlan = addresses // {
    hosts = addresses.hosts // lib.listToAttrs (map
      (host: lib.nameValuePair host.name (addresses.hosts.${host.name} // {
        hubMac = hubMac host.index;
        labFlakeAttrs = lib.genAttrs labSystems (system: flakeAttr { inherit (host) name; inherit system; target = "lab"; });
      }))
      labHosts);
  };
  mkHost = { name, target, system }:
    nixpkgs.lib.nixosSystem {
      inherit system;
      specialArgs = {
        meta.hostname = name;
        privateIp = addresses.hosts.${name}.ip;
        inherit addresses self;
      } // lib.optionalAttrs (target == "lab") {
        inherit (labPlan.hosts.${name}) hubMac;
      };
      modules = [
        disko.nixosModules.disko
        ../hosts/${name}
      ] ++ roleModules.${addresses.hosts.${name}.role} ++ [
        ../profiles/${target}.nix
        {
          networking.hostName = name;
          environment.etc."vigil/flake-attr".text = flakeAttr { inherit name target system; };
        }
      ];
    };
in
{
  inherit inventory addresses flakeAttr mkHost labSystems labHosts labPlan;
}
