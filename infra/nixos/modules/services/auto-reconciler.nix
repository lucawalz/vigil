{ config, pkgs, lib, ... }:
let
  cfg = config.services.vigilAutoReconciler;
in
{
  options.services.vigilAutoReconciler.enable = lib.mkEnableOption "vigil NixOS auto-reconciler";

  config = lib.mkIf cfg.enable {
    systemd.services.vigil-auto-reconcile = {
      description = "Vigil NixOS auto-reconciler";
      path = [ pkgs.git pkgs.nixos-rebuild pkgs.util-linux ];
      unitConfig.ConditionPathExists = "/etc/vigil/branch";
      serviceConfig = {
        Type = "oneshot";
        RemainAfterExit = false;
      };
      script = ''
        set -euo pipefail
        BRANCH=$(cat /etc/vigil/branch)
        ATTR=$(cat /etc/vigil/flake-attr)
        STATE_FILE="/var/lib/vigil-reconciler/last-sha"
        mkdir -p "$(dirname "$STATE_FILE")"
        git -C /opt/nixos-config fetch origin
        NEW=$(git -C /opt/nixos-config rev-parse "origin/$BRANCH")
        git -C /opt/nixos-config reset --hard "origin/$BRANCH"
        OLD=$(cat "$STATE_FILE" 2>/dev/null || echo "")
        if [ "$NEW" != "$OLD" ]; then
          flock /var/lock/vigil-nixos-rebuild nixos-rebuild switch --flake "/opt/nixos-config#$ATTR"
          echo "$NEW" > "$STATE_FILE"
        fi
      '';
    };

    systemd.timers.vigil-auto-reconcile = {
      description = "Timer for vigil NixOS auto-reconciler";
      wantedBy = [ "multi-user.target" ];
      timerConfig = {
        OnBootSec = "300s";
        OnUnitActiveSec = "300s";
        Unit = "vigil-auto-reconcile.service";
      };
    };
  };
}
