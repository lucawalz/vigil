{ ... }:
{
  imports = [
    ./boot.nix
    ./locale.nix
    ./networking.nix
    ./nix-settings.nix
    ./packages.nix
    ./users.nix
    ../../modules/services/cloud-keys.nix
  ];
}
