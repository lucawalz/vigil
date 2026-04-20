let
  hetzner-master   = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIPMFTeq/tkT6dvcziehcnKshBLG1B01+plMgyKA+VP9S root@hetzner-master";
  hetzner-worker-1 = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIMZFQUHzGUhI+vm6M0153OLL9ThGqN1qsR8b5uwHSXm3 root@hetzner-worker-1";
  hetzner-worker-2 = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOZ3+QlsQkg50pFKBcaazKxjbJltkWmME2X+2hJNoC8k root@hetzner-worker-2";
  hetzner-agent    = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIEqOi1LXojz2GHRnaIY5Avk8LvKHEMEXjdQtneCBVrSW root@hetzner-agent";

  luca = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIHoKFFTFmJR1CSAq55TwXHbUPTxSK847qZL0W6r/ZUV9 luca@macbook";
in
{
  "k3s-token.age".publicKeys = [
    hetzner-master hetzner-worker-1 hetzner-worker-2 hetzner-agent
    luca
  ];
}
