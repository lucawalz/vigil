{ nixpkgs, self, disko, agenix, ... }:
{
  mkHetznerMaster = { privateIp ? "10.0.0.10", system ? "x86_64-linux" }:
    nixpkgs.lib.nixosSystem {
      inherit system;
      specialArgs = {
        meta = { hostname = "hetzner-master"; };
        secretsDir = "${self}/secrets";
        inherit privateIp;
      };
      modules = [
        disko.nixosModules.disko
        agenix.nixosModules.default
        ../hosts/hetzner-master
      ];
    };

  mkHetznerWorker = { workerId, privateIp, diskDevice ? "/dev/sda", system ? "x86_64-linux" }:
    let
      hostname = "hetzner-worker-${toString workerId}";
    in
    nixpkgs.lib.nixosSystem {
      inherit system;
      specialArgs = {
        meta = { inherit hostname; };
        secretsDir = "${self}/secrets";
        inherit privateIp diskDevice;
      };
      modules = [
        disko.nixosModules.disko
        agenix.nixosModules.default
        ../hosts/hetzner-worker-${toString workerId}
      ];
    };

  mkHetznerAgent = { privateIp ? "10.0.0.40", system ? "x86_64-linux" }:
    nixpkgs.lib.nixosSystem {
      inherit system;
      specialArgs = {
        meta = { hostname = "hetzner-agent"; };
        secretsDir = "${self}/secrets";
        inherit privateIp;
      };
      modules = [
        disko.nixosModules.disko
        agenix.nixosModules.default
        ../hosts/hetzner-agent
      ];
    };
}
