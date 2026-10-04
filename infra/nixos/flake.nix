{
  description = "NixOS configuration for the vigil hosts";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    disko = {
      url = "github:nix-community/disko";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, disko, ... }:
  let
    inherit (nixpkgs) lib;
    vigil = import ./lib { inherit nixpkgs self disko; };
    hetznerSystem = "x86_64-linux";
    packageSystems = [ "x86_64-linux" "aarch64-linux" "aarch64-darwin" ];
    hostConfig = target: system: host:
      let args = { inherit (host) name; inherit target system; };
      in lib.nameValuePair (vigil.flakeAttr args) (vigil.mkHost args);
  in {
    nixosConfigurations = lib.listToAttrs (
      map (hostConfig "hetzner" hetznerSystem) vigil.inventory.hosts
      ++ lib.concatMap (system: map (hostConfig "lab" system) vigil.labHosts) vigil.labSystems
    );

    packages = lib.genAttrs packageSystems (system: import ./pkgs/mcp-servers.nix {
      pkgs = nixpkgs.legacyPackages.${system};
      inherit self;
    });

    lib.addresses = vigil.labPlan;
  };
}
