{
  description = "NixOS configuration for Hetzner cloud cluster";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    disko = {
      url = "github:nix-community/disko";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    agenix = {
      url = "github:ryantm/agenix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, disko, agenix, ... }:
  let
    lib = import ./lib { inherit nixpkgs self disko agenix; };
  in {
    nixosConfigurations = {
      hetzner-master   = lib.mkHetznerMaster {};
      hetzner-worker-1 = lib.mkHetznerWorker { workerId = 1; privateIp = "10.0.0.20"; };
      hetzner-worker-2 = lib.mkHetznerWorker { workerId = 2; privateIp = "10.0.0.30"; };
      hetzner-agent    = lib.mkHetznerAgent {};
    };
  };
}
