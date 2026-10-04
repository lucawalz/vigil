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
    appSystems = [ "aarch64-darwin" "x86_64-linux" ];
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

    apps = lib.genAttrs appSystems (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        labSource = builtins.path { name = "vigil-lab-source"; path = ../lab/src; };
        lab = pkgs.writeShellApplication {
          name = "lab";
          runtimeInputs = (with pkgs; [ qemu openssh nixos-anywhere kubectl fluxcd git python312 uv ])
            ++ builtins.attrValues self.packages.${system};
          text = ''
            export VIGIL_LAB_FLAKE="path:${self.sourceInfo.outPath}?dir=infra/nixos"
            export VIGIL_LAB_SOURCE=${self.sourceInfo.outPath}
            export VIGIL_LAB_COMMAND="$0"
            export VIGIL_LAB_SSH=${pkgs.openssh}/bin/ssh
            export VIGIL_LAB_FIRMWARE=${pkgs.qemu}/share/qemu
            export PYTHONPATH=${labSource}
            exec python3 -m vigil_lab "$@"
          '';
        };
      in {
        lab = {
          type = "app";
          program = "${lab}/bin/lab";
          meta.description = "Local VM lab for the vigil hosts";
        };
      });

    lib.addresses = vigil.labPlan;
  };
}
