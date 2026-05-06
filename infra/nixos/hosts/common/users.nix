{ meta, ... }:
{
  users.users.${meta.hostname} = {
    isNormalUser = true;
    extraGroups = [ "wheel" ];
  };

  security.sudo.wheelNeedsPassword = false;

  services.openssh.enable = true;
}
