{ config, lib, pkgs, meta, ... }:
{
  imports = [
    ./disko-config.nix
    ../common
  ];

  boot.initrd.availableKernelModules = [
    "ahci"
    "sd_mod"
    "sr_mod"
    "virtio_pci"
    "virtio_scsi"
    "virtio_blk"
  ];

  networking.hostName = "hetzner-agent";
  system.stateVersion = "25.05";

  networking.firewall.allowedTCPPorts = [ 22 9099 ];

  environment.systemPackages = with pkgs; [
    uv
    kubectl
    jq
    curl
    go
    git
  ];

  system.activationScripts.vigil-ssh-key = lib.stringAfter [ "users" ] ''
    if [ ! -f /root/.ssh/id_ed25519 ]; then
      mkdir -p /root/.ssh
      chmod 700 /root/.ssh
      ${pkgs.openssh}/bin/ssh-keygen -t ed25519 -f /root/.ssh/id_ed25519 -N ""
    fi
  '';

  systemd.services.vigil-setup = {
    description = "Clone vigil repo and build MCP servers";
    after = [ "network-online.target" ];
    wants = [ "network-online.target" ];
    wantedBy = [ "multi-user.target" ];
    unitConfig.ConditionPathExists = "/etc/vigil/branch";
    environment = {
      UV_PYTHON = "${pkgs.python312}/bin/python3.12";
      UV_PYTHON_PREFERENCE = "only-system";
      GOPATH = "/root/go";
    };
    serviceConfig = {
      Type = "oneshot";
      RemainAfterExit = true;
      ExecStart = pkgs.writeShellScript "vigil-setup" ''
        set -euo pipefail
        BRANCH=$(cat /etc/vigil/branch)
        if [ ! -d /root/vigil/.git ]; then
          ${pkgs.git}/bin/git clone --branch "$BRANCH" \
            https://github.com/lucawalz/vigil /root/vigil
        else
          cd /root/vigil
          ${pkgs.git}/bin/git fetch origin "$BRANCH"
          ${pkgs.git}/bin/git checkout "$BRANCH"
          ${pkgs.git}/bin/git reset --hard "origin/$BRANCH"
        fi
        cd /root/vigil
        ${pkgs.uv}/bin/uv sync --locked
        CGO_ENABLED=0 ${pkgs.go}/bin/go build \
          -o /usr/local/bin/kubectl-mcp ./mcp-servers/kubectl-mcp/
        CGO_ENABLED=0 ${pkgs.go}/bin/go build \
          -o /usr/local/bin/flux-mcp ./mcp-servers/flux-mcp/
        CGO_ENABLED=0 ${pkgs.go}/bin/go build \
          -o /usr/local/bin/ssh-mcp ./mcp-servers/ssh-mcp/
        CGO_ENABLED=0 ${pkgs.go}/bin/go build \
          -o /usr/local/bin/nixos-mcp ./mcp-servers/nixos-mcp/
      '';
    };
  };

  systemd.services.vigil-orchestrator = {
    description = "Vigil Orchestrator";
    after = [ "vigil-setup.service" ];
    requires = [ "vigil-setup.service" ];
    wantedBy = [ "multi-user.target" ];
    unitConfig.ConditionPathExists = "/etc/vigil/env";
    environment = {
      KUBECTL_MCP_CMD = "/usr/local/bin/kubectl-mcp";
      FLUX_MCP_CMD = "/usr/local/bin/flux-mcp";
      SSH_MCP_CMD = "/usr/local/bin/ssh-mcp";
      NIXOS_MCP_CMD = "/usr/local/bin/nixos-mcp";
      UV_PYTHON = "${pkgs.python312}/bin/python3.12";
      UV_PYTHON_PREFERENCE = "only-system";
    };
    serviceConfig = {
      WorkingDirectory = "/root/vigil";
      ExecStart = "${pkgs.uv}/bin/uv run --frozen --package vigil-orchestrator uvicorn orchestrator.main:app --host 0.0.0.0 --port 9099";
      EnvironmentFile = "/etc/vigil/env";
      Restart = "on-failure";
      RestartSec = "5s";
    };
  };

  services.openssh = {
    enable = true;
    settings = {
      PermitRootLogin = "prohibit-password";
      PasswordAuthentication = false;
    };
  };
}
