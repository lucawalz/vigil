{ ... }:
{
  documentation.enable = false;

  nixpkgs.overlays = [(final: prev: {
    python312 = prev.python312.override { enableDoc = false; };
  })];

  nix.settings = {
    experimental-features = [ "nix-command" "flakes" ];
    trusted-users = [ "root" "@wheel" ];
  };

  programs.ssh.extraConfig = ''
    Host github.com
      IdentityFile /etc/ssh/ssh_host_ed25519_key
      IdentitiesOnly yes
  '';
}
