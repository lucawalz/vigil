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
    vigil = import ./lib { inherit nixpkgs self disko; };
    hetznerSystem = "x86_64-linux";
    hetznerHost = host: nixpkgs.lib.nameValuePair host.name (vigil.mkHost {
      inherit (host) name;
      target = "hetzner";
      system = hetznerSystem;
    });
  in {
    nixosConfigurations = nixpkgs.lib.listToAttrs (map hetznerHost vigil.inventory.hosts);

    packages.x86_64-linux = import ./pkgs/mcp-servers.nix {
      pkgs = nixpkgs.legacyPackages.x86_64-linux;
      inherit self;
    };

    lib.addresses = vigil.addresses;
  };
}
