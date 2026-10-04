{ ... }:
{
  imports = [
    ./disko.nix
    ./boot.nix
    ./locale.nix
    ./networking.nix
    ./nix-settings.nix
    ./packages.nix
    ./users.nix
  ];
}
