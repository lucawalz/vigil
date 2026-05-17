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

  networking.extraHosts = ''
    10.0.0.10 hetzner-master
    10.0.0.20 hetzner-worker-1
    10.0.0.30 hetzner-worker-2
  '';

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
      GOCACHE = "/root/.cache/go-build";
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
        ${pkgs.uv}/bin/uv sync --locked --all-packages
        mkdir -p /usr/local/bin
        ln -sf /root/vigil/.venv/bin/vigil-eval /usr/local/bin/vigil-eval
        CGO_ENABLED=0 ${pkgs.go}/bin/go build \
          -o /usr/local/bin/kubectl-mcp ./mcp-servers/kubectl-mcp/
        CGO_ENABLED=0 ${pkgs.go}/bin/go build \
          -o /usr/local/bin/flux-mcp ./mcp-servers/flux-mcp/
        CGO_ENABLED=0 ${pkgs.go}/bin/go build \
          -o /usr/local/bin/ssh-mcp ./mcp-servers/ssh-mcp/
        CGO_ENABLED=0 ${pkgs.go}/bin/go build \
          -o /usr/local/bin/nixos-mcp ./mcp-servers/nixos-mcp/
        CGO_ENABLED=0 ${pkgs.go}/bin/go build \
          -o /usr/local/bin/git-mcp ./mcp-servers/git-mcp/
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
      KUBECONFIG = "/etc/vigil/kubeconfig-eval-runner";
      PATH = lib.mkForce "${pkgs.git}/bin:/run/current-system/sw/bin:/usr/local/bin:/root/vigil/.venv/bin";
    };
    serviceConfig = {
      WorkingDirectory = "/root/vigil";
      ExecStart = "${pkgs.uv}/bin/uv run --frozen --package vigil-orchestrator uvicorn orchestrator.main:app --host 0.0.0.0 --port 9099";
      EnvironmentFile = "/etc/vigil/env";
      Restart = "on-failure";
      RestartSec = "5s";
    };
  };

  programs.bash.loginShellInit = ''
    if [ -f /etc/vigil/env ]; then
      set -a
      . /etc/vigil/env
      set +a
    fi
    if [ -f /etc/vigil/kubeconfig-eval-runner ]; then
      export KUBECONFIG="/etc/vigil/kubeconfig-eval-runner"
    fi
    export PATH="/usr/local/bin:/root/vigil/.venv/bin:$PATH"
  '';

  services.openssh = {
    enable = true;
    settings = {
      PermitRootLogin = "prohibit-password";
      PasswordAuthentication = false;
    };
  };
}
