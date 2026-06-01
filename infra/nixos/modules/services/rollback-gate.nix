{ pkgs, ... }:
{
  systemd.services.rollback-gate = {
    description = "NixOS dead-man's switch: revert unless a staged repair was committed in time";

    serviceConfig = {
      Type = "oneshot";
      ExecStart = pkgs.writeShellScript "rollback-gate-expire" ''
        echo "rollback-gate: confirmation deadline expired without commit; reverting to boot default" >&2
        exit 1
      '';
      FailureAction = "reboot-force";
    };
  };

  systemd.timers.rollback-gate = {
    description = "Dead-man's switch deadline; armed at staging, disarmed on commit";
    timerConfig = {
      OnActiveSec = "180s";
      Unit = "rollback-gate.service";
    };
  };
}
