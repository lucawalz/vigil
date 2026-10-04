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
  mkHost = { name, target, system }:
    nixpkgs.lib.nixosSystem {
      inherit system;
      specialArgs = {
        meta.hostname = name;
        privateIp = addresses.hosts.${name}.ip;
        inherit addresses self;
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
  inherit inventory addresses flakeAttr mkHost;
}
