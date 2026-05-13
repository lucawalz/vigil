{ pkgs, ... }:
{
  systemd.services.cloud-keys = {
    description = "Inject operator SSH keys from Hetzner metadata";
    wantedBy = [ "multi-user.target" ];
    before = [ "sshd.service" ];
    after = [ "network.target" ];
    serviceConfig = {
      Type = "oneshot";
      RemainAfterExit = true;
      Restart = "on-failure";
      RestartSec = "5";
    };
    script = ''
      install -m 700 -d /root/.ssh
      TMPKEYS=$(mktemp)
      ${pkgs.curl}/bin/curl -sf --connect-timeout 5 --max-time 10 --retry 3 --retry-delay 2 \
        http://169.254.169.254/hetzner/v1/metadata \
        | ${pkgs.gnugrep}/bin/grep -E '^- (ssh-|ecdsa-)' \
        | ${pkgs.gnused}/bin/sed 's/^- //' \
        > "$TMPKEYS"
      if [[ -s "$TMPKEYS" ]]; then
        install -m 600 "$TMPKEYS" /root/.ssh/authorized_keys
      fi
      rm -f "$TMPKEYS"
    '';
  };
}
