{ pkgs, ... }:
let
  metadataUrl = "http://169.254.169.254/hetzner/v1/metadata";
in
{
  systemd.services.cloud-keys = {
    description = "Inject operator SSH keys from Hetzner metadata";
    wantedBy = [ "multi-user.target" ];
    before = [ "sshd.service" ];
    wants = [ "network-online.target" ];
    after = [ "network-online.target" ];
    serviceConfig = {
      Type = "oneshot";
      RemainAfterExit = true;
      Restart = "on-failure";
      RestartSec = "5";
    };
    script = ''
      install -m 700 -d /root/.ssh
      touch /root/.ssh/authorized_keys
      chmod 600 /root/.ssh/authorized_keys
      TMPKEYS=$(mktemp)
      ${pkgs.curl}/bin/curl -sf --connect-timeout 5 --max-time 10 --retry 3 --retry-delay 2 \
        ${metadataUrl} \
        | ${pkgs.gnugrep}/bin/grep -E '^- (ssh-|ecdsa-)' \
        | ${pkgs.gnused}/bin/sed 's/^- //' \
        > "$TMPKEYS"
      if [[ -s "$TMPKEYS" ]]; then
        cat "$TMPKEYS" >> /root/.ssh/authorized_keys
        ${pkgs.coreutils}/bin/sort -u /root/.ssh/authorized_keys -o /root/.ssh/authorized_keys
      fi
      rm -f "$TMPKEYS"
    '';
  };
}
