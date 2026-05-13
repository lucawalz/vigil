{ pkgs, ... }:
{
  systemd.services.cloud-keys = {
    description = "Inject operator SSH keys from Hetzner metadata";
    wantedBy = [ "multi-user.target" ];
    wants = [ "network-online.target" ];
    after = [ "network-online.target" ];
    serviceConfig = {
      Type = "oneshot";
      RemainAfterExit = true;
      Restart = "on-failure";
      RestartSec = "5";
      StartLimitBurst = 10;
      StartLimitIntervalSec = 600;
    };
    script = ''
      set -Eeuo pipefail

      install -m 700 -d /root/.ssh
      touch /root/.ssh/authorized_keys
      chmod 600 /root/.ssh/authorized_keys

      RAW=$(mktemp)
      PARSED=$(mktemp)
      trap 'rm -f "$RAW" "$PARSED"' EXIT

      HTTP_CODE=$(${pkgs.curl}/bin/curl -sS -o "$RAW" \
        -w '%{http_code}' \
        --connect-timeout 5 --max-time 10 --retry 3 --retry-delay 2 \
        http://169.254.169.254/hetzner/v1/metadata/public-keys)

      RAW_BYTES=$(${pkgs.coreutils}/bin/wc -c < "$RAW")
      echo "cloud-keys: metadata http_code=$HTTP_CODE bytes=$RAW_BYTES"

      if [ "$HTTP_CODE" != "200" ]; then
        echo "cloud-keys: metadata fetch failed" >&2
        exit 1
      fi

      cp "$RAW" "$PARSED"

      PARSED_LINES=$(${pkgs.coreutils}/bin/wc -l < "$PARSED")
      echo "cloud-keys: parsed_keys=$PARSED_LINES"

      while IFS= read -r KEY; do
        FP=$(echo "$KEY" | ${pkgs.openssh}/bin/ssh-keygen -lf - 2>/dev/null || echo "fingerprint-failed")
        echo "cloud-keys: fingerprint $FP"
      done < "$PARSED"

      if [ "$PARSED_LINES" -lt 1 ]; then
        echo "cloud-keys: no keys in metadata response" >&2
        exit 1
      fi

      cat "$PARSED" >> /root/.ssh/authorized_keys
      ${pkgs.coreutils}/bin/sort -u /root/.ssh/authorized_keys -o /root/.ssh/authorized_keys

      FINAL_LINES=$(${pkgs.coreutils}/bin/wc -l < /root/.ssh/authorized_keys)
      echo "cloud-keys: authorized_keys lines=$FINAL_LINES"
    '';
  };
}
